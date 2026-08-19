"""Ranking-factor audit engine — the in-house SEMrush/Ahrefs/Moz.

Audits any page (a prospect's current site, not just a GEO-generated one)
against `docs/RANKING_FACTORS_CATALOG.md` and produces a client-facing scorecard
with a number, a threshold, and a plain-English gap per factor.

Two invariants carried over from `audit_engine`:
  - every check reads a real artifact and branches on what it finds;
  - anything that cannot be measured honestly is `not_measured` and excluded
    from the denominator, never assumed to pass and never scored as zero.

The parsers are imported from `audit_engine`, not reimplemented, so the two
engines can never disagree about what a page contains.

The factor registry is data-driven: a new row in the catalog is a new `Factor`
entry plus a weight, not a rewrite.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

# Deliberate reuse of the audit engine's parsers (SPEC_RANKING_INTELLIGENCE
# deliverable 3: do not duplicate the JSON-LD/DOM parsers).
from ..audit_engine import (
    _El,
    _extract_jsonld,
    _find_local_business,
    _has_noindex,
    _main_content,
    _parse_html,
    _types_of,
    _words,
)

STATUS_MEASURED = "measured"
STATUS_NOT_MEASURED = "not_measured"

AXIS_SEO = "seo"
AXIS_GEO = "geo"
AXIS_BOTH = "both"

# Core Web Vitals "good" thresholds (web.dev).
LCP_GOOD_S = 2.5
INP_GOOD_MS = 200.0
CLS_GOOD = 0.1

# Catalog targets.
THIN_CONTENT_MIN_WORDS = 300
FACT_DENSITY_TARGET = 1.0        # verifiable facts per 100 words
EARLY_FACT_SHARE_TARGET = 0.30   # share of facts inside the first 30% of the text
EARLY_WINDOW = 0.30
# A ratio alone is not evidence: one capitalised phrase on a 20-word page reads
# as 5 facts per 100 words. Both GEO fact checks require a real sample.
MIN_FACTS = 3

_STAT_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?\s*(?:%|percent|x|mg|ml|kg|lbs?|hours?|minutes?|days?|weeks?|months?|years?|patients?|sessions?|clinics?|studies)\b", re.I)
_DATE_RE = re.compile(r"\b(?:19|20)\d{2}\b|\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b", re.I)
_ENTITY_RE = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+\b")
_TEL_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_POSTAL_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")
_AUTHOR_HINT_RE = re.compile(r"author|byline|written[-_ ]?by|reviewed[-_ ]?by", re.I)
_CREDENTIAL_RE = re.compile(r"\b(?:M\.?D|D\.?O|D\.?C|D\.?D\.?S|R\.?N|Ph\.?D|N\.?P|P\.?A|DPT|L\.?Ac)\b\.?")


# ---------------------------------------------------------------------------
# Parsed context handed to every check
# ---------------------------------------------------------------------------

@dataclass
class _Ctx:
    dom: _El
    main: _El
    text: str
    words: list[str]
    jsonld: list[Any]
    jsonld_errors: list[str]
    metrics: dict


def _meta(dom: _El, name: str) -> str:
    for m in dom.find_all("meta"):
        if m.attrs.get("name", "").strip().lower() == name.lower():
            return m.attrs.get("content", "").strip()
    return ""


def _link_href(dom: _El, rel: str) -> str:
    for link in dom.find_all("link"):
        rels = link.attrs.get("rel", "").strip().lower().split()
        if rel.lower() in rels:
            return link.attrs.get("href", "").strip()
    return ""


def _all_urls(dom: _El) -> list[str]:
    urls: list[str] = []
    for el in dom.iter():
        for attr in ("href", "src", "action"):
            value = el.attrs.get(attr, "").strip()
            if value:
                urls.append(value)
    return urls


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _fact_tokens(text: str) -> list[tuple[int, str]]:
    """(offset, kind) for every verifiable statistic, date, or named entity."""
    found: list[tuple[int, str]] = []
    for match in _STAT_RE.finditer(text):
        found.append((match.start(), "stat"))
    for match in _DATE_RE.finditer(text):
        found.append((match.start(), "date"))
    for match in _ENTITY_RE.finditer(text):
        found.append((match.start(), "entity"))
    return sorted(found)


# ---------------------------------------------------------------------------
# Checks. Each returns (measured, passed_or_None, gap_note).
# passed_or_None is None when the factor could not be measured honestly.
# ---------------------------------------------------------------------------

def _check_author(ctx: _Ctx):
    hits: list[str] = []
    for el in ctx.dom.iter():
        blob = f"{el.attrs.get('class', '')} {el.attrs.get('id', '')} {el.attrs.get('rel', '')} {el.attrs.get('itemprop', '')}"
        if _AUTHOR_HINT_RE.search(blob):
            hits.append(el.tag)
    for node in ctx.jsonld:
        if isinstance(node, dict) and node.get("author"):
            hits.append("json-ld author")
    credentials = _CREDENTIAL_RE.findall(ctx.text)
    ok = bool(hits) and bool(credentials)
    measured = f"author markup: {len(hits)}, credentials in text: {len(credentials)}"
    note = ("No named author with a credential. E-E-A-T rewards a real, "
            "credentialed person behind health content; add a byline with the "
            "practitioner's name and qualification.")
    return measured, ok, note


def _check_contact_nap(ctx: _Ctx):
    has_tel_link = any(u.lower().startswith("tel:") for u in _all_urls(ctx.dom))
    has_phone = bool(_TEL_RE.search(ctx.text)) or has_tel_link
    has_postal = bool(_POSTAL_RE.search(ctx.text))
    schema_address = any(
        isinstance(n, dict) and (n.get("address") or n.get("telephone"))
        for n in ctx.jsonld
    )
    ok = has_phone and (has_postal or schema_address)
    measured = (f"phone: {'yes' if has_phone else 'no'}, "
                f"address: {'yes' if has_postal or schema_address else 'no'}")
    note = ("Contact and address (NAP) are trust signals and the basis of local "
            "matching. Publish a consistent name, address, and phone on the page.")
    return measured, ok, note


def _check_thin_content(ctx: _Ctx):
    count = len(ctx.words)
    ok = count >= THIN_CONTENT_MIN_WORDS
    measured = f"{count} words"
    note = (f"Thin page: {count} words against a {THIN_CONTENT_MIN_WORDS}-word "
            f"working floor. Helpful-content scoring structurally disadvantages "
            f"pages with little original substance.")
    return measured, ok, note


def _check_indexable(ctx: _Ctx):
    noindex = _has_noindex(ctx.dom)
    robots = _meta(ctx.dom, "robots") or "(none)"
    ok = not noindex
    measured = f"robots meta: {robots}"
    note = ("The page declares noindex, so it cannot appear in search at all. "
            "Remove the directive before any other optimisation matters.")
    return measured, ok, note


def _check_canonical(ctx: _Ctx):
    canonical = _link_href(ctx.dom, "canonical")
    ok = bool(canonical)
    measured = canonical or "(none)"
    note = ("No canonical URL. Without one, duplicate paths compete with each "
            "other and crawl signals are split.")
    return measured, ok, note


def _check_https(ctx: _Ctx):
    canonical = _link_href(ctx.dom, "canonical")
    insecure = [u for u in _all_urls(ctx.dom) if u.lower().startswith("http://")]
    if canonical.lower().startswith("http://"):
        insecure.append(canonical)
    ok = not insecure
    measured = (f"{_plural(len(insecure), 'insecure http:// reference')}" if insecure
                else "no insecure references")
    note = (f"{_plural(len(insecure), 'resource')} load over plain http://, which "
            f"breaks the secure-page signal and can trigger mixed-content warnings.")
    return measured, ok, note


def _check_viewport(ctx: _Ctx):
    viewport = _meta(ctx.dom, "viewport")
    ok = "width=device-width" in viewport.replace(" ", "").lower()
    measured = viewport or "(none)"
    note = ("No responsive viewport declared. Indexing is mobile-first, so a "
            "page that does not adapt is judged on its mobile rendering.")
    return measured, ok, note


def _check_sitemap_reference(ctx: _Ctx):
    refs = [u for u in _all_urls(ctx.dom) if "sitemap" in u.lower()]
    if _link_href(ctx.dom, "sitemap"):
        refs.append(_link_href(ctx.dom, "sitemap"))
    ok = bool(refs)
    measured = (f"{len(refs)} sitemap reference(s)" if refs
                else "no sitemap reference on this page")
    note = ("No sitemap is discoverable from this page. This is a page-level "
            "check: a sitemap may still exist at the site root, so confirm "
            "/sitemap.xml directly before reporting it to the client.")
    return measured, ok, note


def _cwv_check(key: str, label: str, unit: str, limit: float, lower_is_better=True):
    def check(ctx: _Ctx):
        if key not in ctx.metrics or ctx.metrics.get(key) is None:
            return "not measured", None, (
                f"No field data for {label}. Collect it from CrUX or RUM; it is "
                f"excluded from the score rather than assumed."
            )
        try:
            value = float(ctx.metrics[key])
        except (TypeError, ValueError):
            return "not measured", None, (
                f"{label} was supplied but is not a number, so it is excluded "
                f"rather than guessed."
            )
        ok = value <= limit if lower_is_better else value >= limit
        measured = f"{value:g}{unit}"
        note = (f"{label} is {value:g}{unit} against a {limit:g}{unit} threshold. "
                f"This is a measured page-experience signal a client can verify.")
        return measured, ok, note
    return check


def _check_jsonld_valid(ctx: _Ctx):
    ok = bool(ctx.jsonld) and not ctx.jsonld_errors
    if ctx.jsonld_errors:
        measured = f"{len(ctx.jsonld)} node(s), {len(ctx.jsonld_errors)} parse error(s)"
    else:
        measured = f"{len(ctx.jsonld)} JSON-LD node(s)"
    note = ("No valid JSON-LD on the page. Structured data is how engines read "
            "the business as an entity and how rich results are earned.")
    return measured, ok, note


def _check_business_schema(ctx: _Ctx):
    node, specific = _find_local_business(ctx.jsonld)
    ok = node is not None and specific
    if node is None:
        measured = "no LocalBusiness node"
    else:
        measured = f"@type: {', '.join(_types_of(node)) or '(untyped)'}"
    note = ("No specific business type in the structured data. A precise subtype "
            "(for example MedicalClinic) identifies the entity far better than "
            "the generic LocalBusiness.")
    return measured, ok, note


def _check_supporting_schema(ctx: _Ctx):
    wanted = {"Service", "FAQPage", "Question", "Review", "AggregateRating"}
    present = sorted({t for node in ctx.jsonld for t in _types_of(node) if t in wanted})
    ok = len(present) >= 2
    measured = ", ".join(present) if present else "none"
    note = ("Few supporting schema types. Service, FAQPage, and Review markup "
            "are what make individual answers eligible to be surfaced.")
    return measured, ok, note


def _check_entity_completeness(ctx: _Ctx):
    node, _specific = _find_local_business(ctx.jsonld)
    if node is None:
        return "no business node to inspect", False, (
            "Entity completeness cannot be earned without a business node; add "
            "LocalBusiness structured data first."
        )
    fields = ("name", "address", "telephone", "openingHours", "openingHoursSpecification")
    present = [f for f in fields if node.get(f)]
    has_hours = any(f in present for f in ("openingHours", "openingHoursSpecification"))
    core = [f for f in ("name", "address", "telephone") if f in present]
    ok = len(core) == 3 and has_hours
    measured = f"{', '.join(present) if present else 'none'}"
    note = ("Incomplete entity: name, address, telephone, and hours should all be "
            "expressed as structured fields, not only as page text.")
    return measured, ok, note


def _check_fact_density(ctx: _Ctx):
    total_words = len(ctx.words)
    if total_words == 0:
        return "no body text", False, "The page has no readable body text to assess."
    facts = _fact_tokens(ctx.text)
    density = len(facts) * 100.0 / total_words
    ok = density >= FACT_DENSITY_TARGET and len(facts) >= MIN_FACTS
    measured = (f"{_plural(len(facts), 'fact')} in {total_words} words "
                f"({density:.2f} per 100)")
    if len(facts) < MIN_FACTS:
        note = (f"The page carries only {_plural(len(facts), 'verifiable fact')}. "
                f"There is nothing substantive for an answer engine to cite, "
                f"whatever the ratio works out to on a page this short.")
    else:
        note = (f"Fact density is {density:.2f} per 100 words against a target of "
                f"{FACT_DENSITY_TARGET:g}. AI answer engines cite pages that carry "
                f"verifiable statistics, named entities, and dates.")
    return measured, ok, note


def _check_early_facts(ctx: _Ctx):
    facts = _fact_tokens(ctx.text)
    if len(facts) < MIN_FACTS:
        return f"{_plural(len(facts), 'fact')} on the page", False, (
            f"With only {_plural(len(facts), 'verifiable fact')} there is nothing "
            f"to place early. Add concrete statistics or named specifics, then "
            f"lead with them."
        )
    cutoff = len(ctx.text) * EARLY_WINDOW
    early = [f for f in facts if f[0] <= cutoff]
    share = len(early) / len(facts)
    ok = share >= EARLY_FACT_SHARE_TARGET
    measured = f"{share:.0%} of facts in the first {EARLY_WINDOW:.0%} of the page"
    note = (f"Only {share:.0%} of this page's facts appear in the opening "
            f"{EARLY_WINDOW:.0%}. A large share of AI citations are drawn from "
            f"the top of the page, so lead with the key facts.")
    return measured, ok, note


def _check_structured_blocks(ctx: _Ctx):
    lists = len(ctx.main.find_all("ul", "ol"))
    quotes = len(ctx.main.find_all("blockquote", "q"))
    stats = len(_STAT_RE.findall(ctx.text))
    present = sum(1 for n in (lists, quotes, stats) if n > 0)
    ok = present >= 2
    measured = f"lists: {lists}, quotes: {quotes}, statistics: {stats}"
    note = ("Little scannable structure. Lists, pull quotes, and explicit "
            "statistics are the blocks answer engines lift into a response.")
    return measured, ok, note


def _check_ai_crawler_file(ctx: _Ctx):
    refs = [u for u in _all_urls(ctx.dom) if "llms.txt" in u.lower()]
    ok = bool(refs)
    measured = f"{len(refs)} llms.txt reference(s)" if refs else "no llms.txt reference"
    note = ("No llms.txt reference. This is table stakes rather than a lever: no "
            "file alone earns AI visibility, but its absence is a cheap fix.")
    return measured, ok, note


# ---------------------------------------------------------------------------
# The registry. A new catalog row is a new entry here plus a weight.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Factor:
    id: str
    family: str
    axis: str
    label: str
    threshold: str
    source: str
    check: Callable[[_Ctx], tuple[str, bool | None, str]]


FAMILY_CONTENT = "A. Content & E-E-A-T"
FAMILY_TECHNICAL = "B. Technical & crawlability"
FAMILY_CWV = "C. Core Web Vitals"
FAMILY_SCHEMA = "D. Structured data"
FAMILY_GEO = "E. GEO / AI-answer visibility"

SRC_HELPFUL = "Google, Creating Helpful, Reliable, People-First Content"
SRC_ESSENTIALS = "Google, Search Essentials"
SRC_VITALS = "web.dev, Web Vitals"
SRC_SCHEMA = "Schema.org, Getting started"
SRC_GEO = "ranking-factors-seo-geo-2026-07-26 brief"

FACTORS: tuple[Factor, ...] = (
    Factor("A1", FAMILY_CONTENT, AXIS_SEO, "Named author with credentials",
           "byline + credential present", SRC_HELPFUL, _check_author),
    Factor("A2", FAMILY_CONTENT, AXIS_SEO, "Contact / NAP present",
           "phone + address discoverable", SRC_HELPFUL, _check_contact_nap),
    Factor("A3", FAMILY_CONTENT, AXIS_SEO, "Content depth (not thin)",
           f">= {THIN_CONTENT_MIN_WORDS} words", SRC_HELPFUL, _check_thin_content),

    Factor("B1", FAMILY_TECHNICAL, AXIS_SEO, "Indexable (no noindex)",
           "no noindex directive", SRC_ESSENTIALS, _check_indexable),
    Factor("B2", FAMILY_TECHNICAL, AXIS_SEO, "Canonical URL declared",
           "rel=canonical present", SRC_ESSENTIALS, _check_canonical),
    Factor("B3", FAMILY_TECHNICAL, AXIS_SEO, "HTTPS throughout",
           "no http:// references", SRC_ESSENTIALS, _check_https),
    Factor("B4", FAMILY_TECHNICAL, AXIS_SEO, "Mobile viewport",
           "width=device-width", SRC_ESSENTIALS, _check_viewport),
    Factor("B5", FAMILY_TECHNICAL, AXIS_SEO, "Sitemap discoverable from page",
           "sitemap reference present", SRC_ESSENTIALS, _check_sitemap_reference),

    Factor("C1", FAMILY_CWV, AXIS_SEO, "Largest Contentful Paint",
           f"<= {LCP_GOOD_S:g}s", SRC_VITALS,
           _cwv_check("lcp_s", "LCP", "s", LCP_GOOD_S)),
    Factor("C2", FAMILY_CWV, AXIS_SEO, "Interaction to Next Paint",
           f"<= {INP_GOOD_MS:g}ms", SRC_VITALS,
           _cwv_check("inp_ms", "INP", "ms", INP_GOOD_MS)),
    Factor("C3", FAMILY_CWV, AXIS_SEO, "Cumulative Layout Shift",
           f"<= {CLS_GOOD:g}", SRC_VITALS,
           _cwv_check("cls", "CLS", "", CLS_GOOD)),

    Factor("D1", FAMILY_SCHEMA, AXIS_BOTH, "Valid JSON-LD present",
           "parses with no errors", SRC_SCHEMA, _check_jsonld_valid),
    Factor("D2", FAMILY_SCHEMA, AXIS_BOTH, "Specific business type",
           "LocalBusiness subtype", SRC_SCHEMA, _check_business_schema),
    Factor("D3", FAMILY_SCHEMA, AXIS_BOTH, "Service / FAQ / Review markup",
           ">= 2 supporting types", SRC_SCHEMA, _check_supporting_schema),
    Factor("D4", FAMILY_SCHEMA, AXIS_BOTH, "Entity completeness",
           "name + address + phone + hours", SRC_SCHEMA, _check_entity_completeness),

    Factor("E1", FAMILY_GEO, AXIS_GEO, "Fact density",
           f">= {FACT_DENSITY_TARGET:g} per 100 words, min {MIN_FACTS} facts",
           SRC_GEO, _check_fact_density),
    Factor("E2", FAMILY_GEO, AXIS_GEO, "Key facts placed early",
           f">= {EARLY_FACT_SHARE_TARGET:.0%} in the first {EARLY_WINDOW:.0%}",
           SRC_GEO, _check_early_facts),
    Factor("E3", FAMILY_GEO, AXIS_GEO, "Lists, quotes, statistics",
           ">= 2 of the 3 present", SRC_GEO, _check_structured_blocks),
    Factor("E4", FAMILY_GEO, AXIS_GEO, "llms.txt referenced",
           "reference present", SRC_GEO, _check_ai_crawler_file),
)

DEFAULT_WEIGHTS: dict[str, float] = {
    "A1": 8, "A2": 7, "A3": 8,
    "B1": 6, "B2": 5, "B3": 5, "B4": 6, "B5": 4,
    "C1": 7, "C2": 6, "C3": 6,
    "D1": 8, "D2": 7, "D3": 5, "D4": 5,
    "E1": 9, "E2": 8, "E3": 7, "E4": 3,
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_over(rows: list[dict]) -> int | None:
    measured = [r for r in rows if r["status"] == STATUS_MEASURED]
    available = sum(r["weight"] for r in measured)
    if available <= 0:
        return None
    earned = sum(r["weight"] for r in measured if r["pass"])
    return round(earned / available * 100)


def audit_ranking(html: str, *, metrics: dict | None = None,
                  weights: dict | None = None) -> dict:
    """Audit a page against the ranking-factor catalog.

    `metrics` carries measured field data (`lcp_s`, `inp_ms`, `cls`); absent
    metrics make their factors `not_measured` and drop them from the denominator.
    `weights` overrides the catalog defaults per factor id.
    """
    if not (html or "").strip():
        return {
            "overall_score": None,
            "seo_score": None,
            "geo_score": None,
            "factors": [],
            "top_gaps": [],
            "not_measured": [],
            "error": "empty input: no HTML supplied, so nothing was measured",
        }

    effective = dict(DEFAULT_WEIGHTS)
    if weights:
        effective.update(weights)

    dom = _parse_html(html)
    main = _main_content(dom)
    text = main.text()
    jsonld, jsonld_errors = _extract_jsonld(dom)
    ctx = _Ctx(
        dom=dom, main=main, text=text, words=_words(text),
        jsonld=jsonld, jsonld_errors=jsonld_errors, metrics=metrics or {},
    )

    rows: list[dict] = []
    for factor in FACTORS:
        measured, passed, note = factor.check(ctx)
        status = STATUS_NOT_MEASURED if passed is None else STATUS_MEASURED
        rows.append({
            "id": factor.id,
            "family": factor.family,
            "axis": factor.axis,
            "label": factor.label,
            "measured": measured,
            "threshold": factor.threshold,
            "pass": passed,
            "weight": float(effective.get(factor.id, 0)),
            "status": status,
            "source": factor.source,
            "gap_note": "" if passed else note,
        })

    seo_rows = [r for r in rows if r["axis"] in (AXIS_SEO, AXIS_BOTH)]
    geo_rows = [r for r in rows if r["axis"] in (AXIS_GEO, AXIS_BOTH)]

    failures = [r for r in rows if r["status"] == STATUS_MEASURED and not r["pass"]]
    top_gaps = sorted(failures, key=lambda r: (-r["weight"], r["id"]))

    return {
        "overall_score": _score_over(rows),
        "seo_score": _score_over(seo_rows),
        "geo_score": _score_over(geo_rows),
        "factors": rows,
        "top_gaps": top_gaps,
        "not_measured": [r["id"] for r in rows if r["status"] == STATUS_NOT_MEASURED],
    }


# ---------------------------------------------------------------------------
# Client-facing scorecard
# ---------------------------------------------------------------------------

def _fmt_score(value: int | None) -> str:
    return "not measured" if value is None else f"{value}/100"


def scorecard_markdown(result: dict, *, business_name: str) -> str:
    """Render the scorecard a rep shows a prospect. Never invents a number."""
    name = business_name or "This business"
    if not result or not result.get("factors"):
        reason = (result or {}).get("error", "no factors were evaluated")
        return (f"# Search & AI Visibility Scorecard - {name}\n\n"
                f"No scorecard could be produced: {reason}.\n")

    lines: list[str] = [
        f"# Search & AI Visibility Scorecard - {name}",
        "",
        f"- **Overall:** {_fmt_score(result.get('overall_score'))}",
        f"- **Traditional search (SEO):** {_fmt_score(result.get('seo_score'))}",
        f"- **AI answer engines (GEO):** {_fmt_score(result.get('geo_score'))}",
        "",
        "Scores cover only what could be measured on the page supplied. Factors "
        "we could not measure are listed at the end and are excluded from the "
        "score rather than counted against it.",
        "",
        "## Where you stand, factor by factor",
        "",
        "| Factor | Measured | Target | Result |",
        "|---|---|---|---|",
    ]

    for row in result["factors"]:
        if row["status"] == STATUS_NOT_MEASURED:
            verdict = "not measured"
        else:
            verdict = "pass" if row["pass"] else "gap"
        lines.append(
            f"| {row['id']} {row['label']} | {row['measured']} | "
            f"{row['threshold']} | {verdict} |"
        )

    lines += ["", "## The three biggest opportunities", ""]
    top = result.get("top_gaps") or []
    if not top:
        lines.append("No measured factor is currently failing on this page.")
    else:
        for index, row in enumerate(top[:3], 1):
            lines.append(f"**{index}. {row['label']}** - measured {row['measured']}, "
                         f"target {row['threshold']}.")
            lines.append(f"   {row['gap_note']}")
            lines.append(f"   *Source: {row['source']}.*")
            lines.append("")

    not_measured = [r for r in result["factors"] if r["status"] == STATUS_NOT_MEASURED]
    if not_measured:
        lines += ["## Not measured (excluded from the score)", ""]
        for row in not_measured:
            lines.append(f"- **{row['label']}** - {row['gap_note']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def visibility_gap_from_ranking(result: dict) -> float:
    """The visibility-gap axis the HBOT lead scorer consumes (gap = 100 - overall).

    Delegates the scaling to the lead scorer so the two cannot drift apart.
    """
    from ..sales.lead_scorer import visibility_gap_from_audit_score

    score = result.get("overall_score") if isinstance(result, dict) else None
    if score is None:
        return 0.0
    return visibility_gap_from_audit_score(score)
