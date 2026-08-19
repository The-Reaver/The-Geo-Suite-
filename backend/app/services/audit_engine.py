"""
The AI-Search Readiness audit engine (Sprint days 3-5).

This REPLACES the quarantined stub that hardcoded a passing 95 and inspected
nothing. The governing rule (SPEC_GEO_D3 §0): **every check reads a real artifact
and branches on what it finds.** A check that returns the same result regardless of
input is a defect. Anything that cannot be measured honestly is marked
`not_measured` and excluded from the denominator — never assumed to pass.

Entry point: `run_audit(site_dir, *, cwv=None) -> AuditResult`. It takes a directory
of generated site files (index.html, other *.html, robots.txt, sitemap.xml,
llms.txt, llms-full.txt), not a URL and not a DB row, so it is testable today —
before the site engine (days 6-8) exists to produce such a directory.

The legacy `run_ai_readiness_audit(site_id)` remains fail-loud: auditing by site id
requires the site engine to first materialize the site directory, and that engine is
still quarantined. See STATUS.md.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from uuid import UUID
from xml.etree import ElementTree as ET

from ..core import rubric

# =============================================================================
# Result objects
# =============================================================================


@dataclass
class CategoryResult:
    id: int
    name: str
    weight: int
    earned: float
    tier: str                       # documented | hypothesis (dominant label)
    status: str                     # "measured" | "not_measured"
    findings: list[str] = field(default_factory=list)
    not_measured_reason: str | None = None
    documented_earned: float = 0.0  # earned points that came from documented sub-checks


@dataclass
class AuditResult:
    normalized_score: int           # 0-100 over measured categories
    points_earned: float
    points_available: float         # sum of weights of MEASURED categories
    tier: str                       # Poor | Needs Work | Strong | AI-Optimized
    passed: bool                    # normalized_score >= PUBLISH_THRESHOLD
    documented_subtotal: float      # earned points from tier="documented" sub-checks only
    categories: list[CategoryResult]
    fix_list: list[str]
    not_measured: list[str] = field(default_factory=list)  # names of excluded categories


# =============================================================================
# A tiny standard-library DOM (no bs4/lxml dependency, matching the venv)
# =============================================================================

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
         "link", "meta", "param", "source", "track", "wbr"}
_WORD_RE = re.compile(r"[A-Za-z0-9']+")


class _El:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: list[tuple[str, str | None]]):
        self.tag = tag
        self.attrs: dict[str, str] = {k.lower(): (v or "") for k, v in attrs}
        self.children: list[Any] = []   # _El or str
        self.parent: _El | None = None

    def iter(self):
        for c in self.children:
            if isinstance(c, _El):
                yield c
                yield from c.iter()

    def find_all(self, *tags: str) -> list["_El"]:
        want = set(tags)
        return [e for e in self.iter() if e.tag in want]

    def first(self, *tags: str) -> "_El | None":
        want = set(tags)
        for e in self.iter():
            if e.tag in want:
                return e
        return None

    def text(self) -> str:
        out: list[str] = []
        for c in self.children:
            out.append(c if isinstance(c, str) else c.text())
        return "".join(out)


class _DOMBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _El("#document", [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        el = _El(tag, attrs)
        el.parent = self.stack[-1]
        self.stack[-1].children.append(el)
        if tag not in _VOID:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        el = _El(tag, attrs)
        el.parent = self.stack[-1]
        self.stack[-1].children.append(el)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _parse_html(source: str) -> _El:
    b = _DOMBuilder()
    b.feed(source)
    b.close()
    return b.root


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


# =============================================================================
# A small sub-check accumulator so every category scores honestly and tracks
# which of its earned points were documented vs hypothesis.
# =============================================================================


class _Scorer:
    def __init__(self):
        self.earned = 0.0
        self.documented = 0.0
        self.findings: list[str] = []

    def award(self, ok: bool, pts: float, tier: str, pass_msg: str, fail_msg: str):
        if ok:
            self.earned += pts
            if tier == rubric.DOCUMENTED:
                self.documented += pts
        else:
            self.findings.append(fail_msg)
        return ok

    def partial(self, got: float, pts: float, tier: str, fail_msg: str | None):
        """Award a pre-computed fraction of `pts` (0..pts)."""
        got = max(0.0, min(pts, got))
        self.earned += got
        if tier == rubric.DOCUMENTED:
            self.documented += got
        if got < pts and fail_msg:
            self.findings.append(fail_msg)
        return got


# =============================================================================
# JSON-LD extraction (shared by categories 1 and 4)
# =============================================================================


def _extract_jsonld(dom: _El) -> tuple[list[Any], list[str]]:
    """Return (parsed_objects, parse_errors). Every block is a real json.loads."""
    objects: list[Any] = []
    errors: list[str] = []
    for s in dom.find_all("script"):
        if s.attrs.get("type", "").strip().lower() != "application/ld+json":
            continue
        raw = s.text().strip()
        if not raw:
            errors.append("empty JSON-LD script block")
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"malformed JSON-LD block: {exc.__class__.__name__}: {exc}")
            continue
        # A block may be a @graph, a list, or a single node.
        if isinstance(data, dict) and "@graph" in data and isinstance(data["@graph"], list):
            objects.extend(data["@graph"])
        elif isinstance(data, list):
            objects.extend(data)
        else:
            objects.append(data)
    return objects, errors


def _types_of(node: Any) -> list[str]:
    if not isinstance(node, dict):
        return []
    t = node.get("@type")
    if isinstance(t, list):
        return [str(x) for x in t]
    if isinstance(t, str):
        return [t]
    return []


_LOCAL_BUSINESS_SUBTYPES = {
    # A representative slice of schema.org LocalBusiness subtypes; the check is
    # "a specific subtype, not the generic base", so membership OR "ends in a
    # known specific noun" both count, but generic LocalBusiness never does.
    "Dentist", "Physician", "MedicalClinic", "Plumber", "Electrician",
    "Restaurant", "CafeOrCoffeeShop", "Bakery", "HairSalon", "BeautySalon",
    "AutoRepair", "Attorney", "LegalService", "AccountingService",
    "RealEstateAgent", "Locksmith", "RoofingContractor", "HVACBusiness",
    "Notary", "Optician", "VeterinaryCare",
    "ProfessionalService", "HomeAndConstructionBusiness", "ChildCare",
    "DryCleaningOrLaundry", "MovingCompany", "PestControl", "GeneralContractor",
}


def _find_local_business(objects: list[Any]) -> tuple[dict | None, bool]:
    """Return (node, is_specific_subtype). node is the best LocalBusiness-ish node."""
    generic_node = None
    for node in objects:
        types = _types_of(node)
        for t in types:
            if t in _LOCAL_BUSINESS_SUBTYPES:
                return node, True
        if rubric.GENERIC_LOCALBUSINESS in types:
            generic_node = node
    return generic_node, False


# =============================================================================
# Category 1 — Structured data (20, documented)
# =============================================================================


def _cat1_structured_data(pages: dict[str, _El]) -> CategoryResult:
    s = _Scorer()
    # Aggregate JSON-LD across every page; subtype/required-fields judged on the
    # primary page (index.html) where the LocalBusiness lives.
    all_objects: list[Any] = []
    all_errors: list[str] = []
    for name, dom in pages.items():
        objs, errs = _extract_jsonld(dom)
        all_objects.extend(objs)
        all_errors.extend(f"{name}: {e}" for e in errs)

    # (a) valid JSON parse of every block (3)
    s.award(not all_errors, 3, rubric.DOCUMENTED,
            "all JSON-LD blocks parsed",
            "JSON-LD parse failures: " + "; ".join(all_errors))

    biz, specific = _find_local_business(all_objects)

    # (b) specific LocalBusiness subtype, not generic (4) — hypothesis: whether
    # subtype specificity actually affects AI-answer citation is unproven, see
    # CRAWLER_INTELLIGENCE.md section 3 and the CATEGORIES comment in rubric.py.
    if specific:
        s.award(True, 4, rubric.HYPOTHESIS, "", "")
    elif biz is not None:
        s.award(False, 4, rubric.HYPOTHESIS, "",
                "JSON-LD uses generic 'LocalBusiness' instead of a specific subtype "
                "(e.g. Dentist, Plumber) — AI engines weight the generic type far less")
    else:
        s.award(False, 4, rubric.HYPOTHESIS, "",
                "no LocalBusiness node found in JSON-LD")

    # (c) required LocalBusiness fields present: name, address, telephone, url (4)
    req = ["name", "address", "telephone", "url"]
    if biz is not None:
        present = [f for f in req if biz.get(f)]
        s.partial(len(present), 4, rubric.DOCUMENTED,
                  "missing required LocalBusiness field(s): "
                  + ", ".join(f for f in req if f not in present)
                  if len(present) < 4 else None)
    else:
        s.findings.append("cannot check required fields — no LocalBusiness node")

    # (d) Organization and WebSite present (3) — hypothesis, see (b) above.
    have_org = any("Organization" in _types_of(n) for n in all_objects)
    have_site = any("WebSite" in _types_of(n) for n in all_objects)
    s.partial((1.5 if have_org else 0) + (1.5 if have_site else 0), 3, rubric.HYPOTHESIS,
              "missing " + " and ".join(
                  x for x, ok in (("Organization", have_org), ("WebSite", have_site)) if not ok)
              + " schema" if not (have_org and have_site) else None)

    # (e) a Service or FAQPage node where applicable (2) — hypothesis, see (b).
    have_service = any(("Service" in _types_of(n) or "FAQPage" in _types_of(n))
                       for n in all_objects)
    s.award(have_service, 2, rubric.HYPOTHESIS, "",
            "no Service or FAQPage schema found on any page")

    # (f) @id entity linking (2) — hypothesis, see (b).
    have_id = any(isinstance(n, dict) and n.get("@id") for n in all_objects)
    s.award(have_id, 2, rubric.HYPOTHESIS, "",
            "no @id entity linking present in JSON-LD")

    # (g) sameAs populated (2) — hypothesis, see (b).
    same_as = biz.get("sameAs") if isinstance(biz, dict) else None
    if not same_as:
        same_as = next((n.get("sameAs") for n in all_objects
                        if isinstance(n, dict) and n.get("sameAs")), None)
    s.award(bool(same_as), 2, rubric.HYPOTHESIS, "",
            "sameAs is absent or empty — no authoritative profile links declared")

    # (a) and (c) above stay DOCUMENTED — mechanical JSON-LD validity and NAP-field
    # presence are directly verifiable, not a claim about AI-citation effect. The
    # remaining 13 of 20 points (b, d, e, f, g) are HYPOTHESIS per the 2026-08-16
    # Brain Trust finding; dominant tier follows the majority of the weight.
    return _mk(1, s, rubric.HYPOTHESIS)


# =============================================================================
# Category 2 — Semantic HTML / GEO-SFE (20, hypothesis)
# =============================================================================


def _main_content(dom: _El) -> _El:
    return dom.first("main") or dom.first("article") or dom.first("body") or dom


def _content_chunks(main: _El) -> list[int]:
    """Word counts of paragraph 'chunks' (paragraphs with real prose, >30 words)."""
    counts = []
    for p in main.find_all("p"):
        n = len(_words(p.text()))
        if n > 30:
            counts.append(n)
    return counts


def _cat2_semantic_html(dom: _El) -> CategoryResult:
    s = _Scorer()
    main = _main_content(dom)
    headings = dom.find_all("h1", "h2", "h3", "h4", "h5", "h6")
    h1s = [h for h in headings if h.tag == "h1"]

    # (a) exactly one h1 (3)
    s.award(len(h1s) == 1, 3, rubric.HYPOTHESIS, "",
            f"expected exactly one <h1>, found {len(h1s)}")

    # (b) heading depth 3-5 distinct levels (3)
    levels = sorted({int(h.tag[1]) for h in headings})
    depth = len(levels)
    s.award(3 <= depth <= 5, 3, rubric.HYPOTHESIS, "",
            f"heading depth is {depth} distinct levels; target 3-5")

    # (c) logical nesting, no skipped levels (3)
    skipped = False
    seq = [int(h.tag[1]) for h in headings]
    for prev, cur in zip(seq, seq[1:]):
        if cur > prev + 1:
            skipped = True
            break
    s.award(not skipped and bool(seq), 3, rubric.HYPOTHESIS, "",
            "heading levels skip a step (e.g. h2 -> h4)")

    # (d) answer-first: first paragraph after the h1 is non-empty prose (3)
    answer_ok = False
    if h1s:
        # first <p> that appears after the h1 in document order
        seen_h1 = False
        for el in main.iter():
            if el is h1s[0] or (el.tag == "h1"):
                seen_h1 = True
                continue
            if seen_h1 and el.tag == "p":
                answer_ok = len(_words(el.text())) >= 20
                break
        if not seen_h1:  # h1 outside main; fall back to first prose paragraph
            first_p = main.first("p")
            answer_ok = bool(first_p) and len(_words(first_p.text())) >= 20
    s.award(answer_ok, 3, rubric.HYPOTHESIS, "",
            "no answer-first opening — the first paragraph after the h1 is not "
            "substantive prose")

    # (e) chunk length mean 150-300 words (2)
    chunks = _content_chunks(main)
    mean_chunk = sum(chunks) / len(chunks) if chunks else 0
    s.award(bool(chunks) and 150 <= mean_chunk <= 300, 2, rubric.HYPOTHESIS, "",
            f"mean content chunk is {mean_chunk:.0f} words; target 150-300")

    # (f) structured-element proportion 0.25-0.35 (2)
    structured = len(main.find_all("ul", "ol", "table", "pre", "dl"))
    denom = structured + len(chunks)
    prop = structured / denom if denom else 0
    s.award(0.25 <= prop <= 0.35, 2, rubric.HYPOTHESIS, "",
            f"structured-element proportion is {prop:.2f}; target 0.25-0.35")

    # (g) emphasis density 0.05-0.10 (2)
    total_words = len(_words(main.text())) or 1
    emph_words = sum(len(_words(e.text())) for e in main.find_all("strong", "b", "em", "i", "mark"))
    emph_density = emph_words / total_words
    s.award(0.05 <= emph_density <= 0.10, 2, rubric.HYPOTHESIS, "",
            f"emphasis density is {emph_density:.3f}; target 0.05-0.10")

    # (h) internal-link density 0.15-0.20 (1)
    internal_links = [a for a in main.find_all("a") if _is_internal(a.attrs.get("href", ""))]
    link_density = len(internal_links) / total_words
    s.award(0.15 <= link_density <= 0.20, 1, rubric.HYPOTHESIS, "",
            f"internal-link density is {link_density:.3f} "
            f"({len(internal_links)} links / {total_words} words); target 0.15-0.20")

    # (i) semantic tags present: main, article, section, nav (1)
    have = {t for t in ("main", "article", "section", "nav") if dom.first(t)}
    s.partial(len(have) / 4, 1, rubric.HYPOTHESIS,
              "missing semantic tag(s): "
              + ", ".join(t for t in ("main", "article", "section", "nav") if t not in have)
              if len(have) < 4 else None)

    return _mk(2, s, rubric.HYPOTHESIS)


def _is_internal(href: str) -> bool:
    href = (href or "").strip()
    if not href or href.startswith("#"):
        return False
    low = href.lower()
    if low.startswith(("http://", "https://", "//", "mailto:", "tel:", "javascript:", "data:")):
        return False
    return True


# =============================================================================
# Category 3 — Crawler access and llms.txt (12, documented + 1 hypothesis)
#
# 2026-08-16, RUBRIC_WEIGHT_SOURCING_TRACE_2026-08-16.md Phase 1: the
# crawler-blocking check needs no external study to defend — it's a
# mechanical necessity, not a statistical claim. If robots.txt blocks a
# named bot (OAI-SearchBot, PerplexityBot, and the rest — see rubric.py's
# REQUIRED_BOTS, sourced from CRAWLER_INTELLIGENCE.md sections 2 & 4), that
# bot cannot fetch the page, so it cannot cite it. The llms.txt sub-check is
# separately, honestly tagged "hypothesis" (CRAWLER_INTELLIGENCE.md 4.6:
# "ships as hygiene at near-zero rubric weight... genuinely used by coding
# agents, not answer engines") — keep it framed as low-stakes hygiene, not a
# selling point.
# =============================================================================


def _parse_robots(text: str) -> list[tuple[list[str], list[tuple[str, str]]]]:
    """Return groups: (user_agents, [(directive, value), ...]). Standard robots.txt."""
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    cur_agents: list[str] = []
    cur_rules: list[tuple[str, str]] = []
    last_was_agent = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        field_name = field_name.strip().lower()
        value = value.strip()
        if field_name == "user-agent":
            if cur_rules and not last_was_agent:
                groups.append((cur_agents, cur_rules))
                cur_agents, cur_rules = [], []
            cur_agents.append(value)
            last_was_agent = True
        else:
            cur_rules.append((field_name, value))
            last_was_agent = False
    if cur_agents or cur_rules:
        groups.append((cur_agents, cur_rules))
    return groups


def _rules_for(groups, agent: str) -> list[tuple[str, str]]:
    """Directives that apply to `agent` (its own group plus the '*' group)."""
    rules: list[tuple[str, str]] = []
    for agents, grp_rules in groups:
        names = [a.lower() for a in agents]
        if "*" in names or agent.lower() in names:
            rules.extend(grp_rules)
    return rules


def _is_blocked(rules: list[tuple[str, str]], path: str) -> bool:
    """Longest-match Allow/Disallow, per the robots.txt standard."""
    best_len = -1
    blocked = False
    for directive, value in rules:
        if directive not in ("allow", "disallow"):
            continue
        if value == "":
            continue
        if path.startswith(value.replace("*", "")):
            if len(value) > best_len:
                best_len = len(value)
                blocked = (directive == "disallow")
    # A bare "Disallow: /" blocks everything.
    for directive, value in rules:
        if directive == "disallow" and value == "/" and best_len <= 1:
            blocked = True
    return blocked


def _cat3_crawler_access(site: Path, pages: dict[str, _El],
                          homepage_only: bool = False) -> CategoryResult:
    if homepage_only:
        # 2026-08-16 operator ruling (Bink's ask, Brain Trust review): a
        # single-page live audit (/sales/audit-current, /sales/report) only ever
        # fetches the business's homepage HTML — it never requests robots.txt or
        # llms.txt, so their absence here proves nothing about the real site.
        # Auto-zeroing this category previously scored every live business's real
        # robots.txt as "missing" regardless of whether it actually was. Marked
        # not_measured instead, matching the existing Category 5 pattern.
        return CategoryResult(
            3, rubric.CATEGORY_NAME[3], rubric.CATEGORY_WEIGHT[3], 0.0, rubric.DOCUMENTED,
            "not_measured", findings=[],
            not_measured_reason="single-page live audit — robots.txt and llms.txt "
            "were never fetched, so their absence is not evidence they're missing "
            "from the real site", documented_earned=0.0)
    s = _Scorer()
    robots_path = site / "robots.txt"
    if not robots_path.exists():
        cr = CategoryResult(3, rubric.CATEGORY_NAME[3], 12, 0.0, rubric.DOCUMENTED,
                            "measured",
                            findings=["robots.txt is missing — crawlers get no guidance"],
                            documented_earned=0.0)
        return cr
    groups = _parse_robots(robots_path.read_text(encoding="utf-8"))

    # Hard-fail gate: a blocked user-triggered fetcher zeros the whole category.
    hard_blocked = [b for b in rubric.USER_TRIGGERED_FETCHERS
                    if _is_blocked(_rules_for(groups, b), "/")]
    if hard_blocked:
        return CategoryResult(
            3, rubric.CATEGORY_NAME[3], 12, 0.0, rubric.DOCUMENTED, "measured",
            findings=[f"HARD FAIL: user-triggered fetcher(s) blocked: {', '.join(hard_blocked)} "
                      "— these are the citation moment and must never be blocked"],
            documented_earned=0.0)

    # (a) allow every required retrieval + user-triggered bot (5)
    blocked = [b for b in rubric.REQUIRED_BOTS
               if _is_blocked(_rules_for(groups, b), "/")]
    s.partial((len(rubric.REQUIRED_BOTS) - len(blocked)) / len(rubric.REQUIRED_BOTS) * 5,
              5, rubric.DOCUMENTED,
              f"robots.txt blocks required crawler(s): {', '.join(blocked)}"
              if blocked else None)

    # (b) no sitewide Disallow: / for '*' (2)
    star_blocked = _is_blocked(_rules_for(groups, "SomeUnknownBot"), "/")
    s.award(not star_blocked, 2, rubric.DOCUMENTED, "",
            "robots.txt sitewide-disallows all crawlers (Disallow: /)")

    # (c) .well-known not blocked (2)
    wk_blocked = any(_is_blocked(_rules_for(groups, b), "/.well-known/security.txt")
                     for b in ("Googlebot", "*"))
    s.award(not wk_blocked, 2, rubric.DOCUMENTED, "",
            ".well-known is blocked in robots.txt (breaks discovery + verification)")

    # (d) sitemap referenced (1)
    has_sitemap = any(d == "sitemap" for _, rules in groups for d, _ in rules)
    s.award(has_sitemap, 1, rubric.DOCUMENTED, "",
            "robots.txt does not reference a sitemap")

    # (e) no noindex meta on key pages (1)
    noindexed = [n for n, dom in pages.items() if _has_noindex(dom)]
    s.award(not noindexed, 1, rubric.DOCUMENTED, "",
            f"noindex meta present on: {', '.join(noindexed)}")

    # (f) llms.txt present and valid Markdown — hypothesis, low weight (1)
    llms = site / "llms.txt"
    llms_ok = llms.exists() and _looks_like_markdown(llms.read_text(encoding="utf-8"))
    s.award(llms_ok, 1, rubric.HYPOTHESIS, "",
            "llms.txt is missing or not valid Markdown (low-weight hygiene)")

    return _mk(3, s, rubric.DOCUMENTED)


def _has_noindex(dom: _El) -> bool:
    for m in dom.find_all("meta"):
        if m.attrs.get("name", "").lower() == "robots" and "noindex" in m.attrs.get("content", "").lower():
            return True
    return False


def _looks_like_markdown(text: str) -> bool:
    # Curated links with a heading — the llms.txt convention.
    return bool(re.search(r"^#\s+\S", text, re.M)) and bool(re.search(r"\[[^\]]+\]\([^)]+\)", text))


# =============================================================================
# Category 4 — Entity consistency (13, documented)
# =============================================================================


def _norm_phone(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def _phone_match(a: str, b: str) -> bool:
    """Compare two already-digit-normalized phones, tolerant of a country-code
    prefix (per the spec's 'normalize phone formatting')."""
    if len(a) < 7 or len(b) < 7:
        return False
    return a == b or a[-10:] == b[-10:]


def _norm_text(v: str) -> str:
    return re.sub(r"\s+", " ", (v or "").strip().lower()).strip(" .,")


def _address_string(addr: Any) -> str:
    if isinstance(addr, str):
        return _norm_text(addr)
    if isinstance(addr, dict):
        parts = [addr.get("streetAddress", ""), addr.get("addressLocality", ""),
                 addr.get("postalCode", "")]
        return _norm_text(" ".join(p for p in parts if p))
    return ""


def _footer_text(dom: _El) -> str:
    f = dom.first("footer")
    return f.text() if f else ""


def _cat4_entity_consistency(pages: dict[str, _El]) -> CategoryResult:
    s = _Scorer()
    index = pages.get("index.html") or next(iter(pages.values()))
    objects, _ = _extract_jsonld(index)
    biz, _ = _find_local_business(objects)
    biz = biz or {}
    footer = _footer_text(index)
    footer_norm = _norm_text(footer)

    # (a) NAP match across schema and page footer (5): name(2) phone(2) locality(1)
    schema_phone = _norm_phone(biz.get("telephone", ""))
    footer_phones = set(_norm_phone(p) for p in re.findall(r"[\d][\d\-\.\s\(\)]{6,}\d", footer))
    phone_ok = bool(schema_phone) and any(_phone_match(schema_phone, fp) for fp in footer_phones)
    s.award(phone_ok, 2, rubric.DOCUMENTED, "",
            f"footer phone does not match schema telephone ({biz.get('telephone', '—')})")

    schema_name = _norm_text(biz.get("name", ""))
    name_ok = bool(schema_name) and schema_name in footer_norm
    s.award(name_ok, 2, rubric.DOCUMENTED, "",
            f"business name in schema ('{biz.get('name', '—')}') not found in page footer")

    locality = ""
    addr = biz.get("address")
    if isinstance(addr, dict):
        locality = _norm_text(addr.get("addressLocality", ""))
    loc_ok = bool(locality) and locality in footer_norm
    s.award(loc_ok, 1, rubric.DOCUMENTED, "",
            "address locality from schema not shown in the page footer")

    # (b) sameAs present and includes a Google Business Profile URL (4)
    same_as = biz.get("sameAs") or []
    if isinstance(same_as, str):
        same_as = [same_as]
    s.award(bool(same_as), 2, rubric.DOCUMENTED, "",
            "sameAs is empty — no authoritative profiles linked")
    gbp = any(re.search(r"(g\.page|google\.com/maps|business\.google\.com|maps\.app\.goo\.gl)",
                        str(u), re.I) for u in same_as)
    s.award(gbp, 2, rubric.DOCUMENTED, "",
            "sameAs does not include a Google Business Profile URL")

    # (c) reviews present and linked, not orphaned (4)
    has_reviews = any(t in ("Review", "AggregateRating") for n in objects for t in _types_of(n)) \
        or isinstance(biz.get("aggregateRating"), dict) or bool(biz.get("review"))
    s.award(has_reviews, 2, rubric.DOCUMENTED, "",
            "no reviews / aggregateRating present in schema")
    # linked: aggregateRating tied to the business (has itemReviewed or lives on biz),
    # or a visible reviews anchor exists.
    linked = bool(biz.get("aggregateRating") or biz.get("review")) or \
        any("review" in (a.attrs.get("href", "").lower()) for a in index.find_all("a"))
    s.award(has_reviews and linked, 2, rubric.DOCUMENTED, "",
            "reviews are orphaned — not attached to the business entity or linked on-page")

    return _mk(4, s, rubric.DOCUMENTED)


# =============================================================================
# Category 5 — Performance / CWV (15, documented) — measured only with cwv
#
# 2026-08-16, RUBRIC_WEIGHT_SOURCING_TRACE_2026-08-16.md Phase 1: the strongest
# category in the rubric and the only one with fully external, independently
# citable sourcing for both the metrics AND the pass thresholds. LCP <2.5s,
# INP <200ms, CLS <0.1 are Google's own published Core Web Vitals "good"
# thresholds (https://web.dev/articles/vitals), not an internal GEO claim,
# and already a real Google Search ranking signal on their own. Defend this
# category's methodology directly by citing Google, with full confidence.
# =============================================================================


def _cat5_performance(dom: _El, cwv: dict | None) -> CategoryResult:
    if not cwv:
        return CategoryResult(
            5, rubric.CATEGORY_NAME[5], 15, 0.0, rubric.DOCUMENTED, "not_measured",
            findings=[], not_measured_reason="no Core Web Vitals data supplied "
            "(requires PageSpeed/CrUX field data); not estimated", documented_earned=0.0)
    s = _Scorer()
    lcp = cwv.get("lcp_s")
    inp = cwv.get("inp_ms")
    cls = cwv.get("cls")

    s.award(isinstance(lcp, (int, float)) and lcp < 2.5, 4, rubric.DOCUMENTED, "",
            f"LCP {lcp}s exceeds the 2.5s threshold")
    s.award(isinstance(inp, (int, float)) and inp < 200, 4, rubric.DOCUMENTED, "",
            f"INP {inp}ms exceeds the 200ms threshold")
    s.award(isinstance(cls, (int, float)) and cls < 0.1, 3, rubric.DOCUMENTED, "",
            f"CLS {cls} exceeds the 0.1 threshold")

    # HTTPS: declared canonical/og:url must use https
    urls = []
    for lnk in dom.find_all("link"):
        if lnk.attrs.get("rel", "").lower() == "canonical":
            urls.append(lnk.attrs.get("href", ""))
    for m in dom.find_all("meta"):
        if m.attrs.get("property", "").lower() == "og:url":
            urls.append(m.attrs.get("content", ""))
    https_ok = bool(urls) and all(u.lower().startswith("https://") for u in urls if u)
    s.award(https_ok, 2, rubric.DOCUMENTED, "",
            "declared canonical/og:url are not all HTTPS")

    viewport = any(m.attrs.get("name", "").lower() == "viewport" for m in dom.find_all("meta"))
    s.award(viewport, 2, rubric.DOCUMENTED, "",
            "no viewport meta tag — not mobile-friendly")

    return _mk(5, s, rubric.DOCUMENTED)


# =============================================================================
# Category 6 — Data integrity (10, documented)
#
# 2026-08-16, RUBRIC_WEIGHT_SOURCING_TRACE_2026-08-16.md Phase 1: every check
# here validates against a real, external, independently checkable standard,
# not a proprietary GEO claim — broken-link and canonical-tag conventions and
# sitemap.xml validity per Google Search Central
# (https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap),
# and JSON-LD structure per schema.org (https://schema.org/) and Google's own
# Rich Results Test (https://search.google.com/test/rich-results). The doc's
# "refreshed content is cited more often" rationale for the last-updated-date
# check isn't sourced specifically for AI citation, but it's a long-standing,
# low-controversy idea in search generally — defend the validation mechanics
# here directly; don't extend that general idea into an AI-citation-specific claim.
# =============================================================================


def _cat6_data_integrity(site: Path, pages: dict[str, _El],
                          homepage_only: bool = False) -> CategoryResult:
    s = _Scorer()

    # (a) every internal link target resolves to a file that exists (3)
    # 2026-08-16 operator ruling (Bink's ask): skipped for single-page live
    # audits. A homepage-only fetch never retrieves the pages an internal link
    # points to, so "does not resolve to a file that exists" was flagging every
    # real internal link on every live business as "broken" — it was testing
    # whether the temp audit directory happens to contain that file, not
    # whether the link is actually broken on the real site.
    if not homepage_only:
        broken: list[str] = []
        checked = 0
        for name, dom in pages.items():
            for a in dom.find_all("a"):
                href = a.attrs.get("href", "")
                if not _is_internal(href):
                    continue
                checked += 1
                if not _resolves(site, href):
                    broken.append(f"{name} -> {href}")
        s.award(not broken, 3, rubric.DOCUMENTED, "",
                f"broken internal link(s): {', '.join(broken)}")

    # (b) self-referential canonical on each page (2)
    missing_canon: list[str] = []
    for name, dom in pages.items():
        canon = None
        for lnk in dom.find_all("link"):
            if lnk.attrs.get("rel", "").lower() == "canonical":
                canon = lnk.attrs.get("href", "")
                break
        if not canon or not _canonical_self(canon, name):
            missing_canon.append(name)
    s.partial((len(pages) - len(missing_canon)) / len(pages) * 2, 2, rubric.DOCUMENTED,
              f"missing or non-self-referential canonical on: {', '.join(missing_canon)}"
              if missing_canon else None)

    # (c) Open Graph AND Twitter card tags present (2)
    index = pages.get("index.html") or next(iter(pages.values()))
    has_og = any(m.attrs.get("property", "").lower().startswith("og:")
                 for m in index.find_all("meta"))
    has_tw = any(m.attrs.get("name", "").lower().startswith("twitter:")
                 for m in index.find_all("meta"))
    s.partial((1 if has_og else 0) + (1 if has_tw else 0), 2, rubric.DOCUMENTED,
              "missing " + " and ".join(
                  x for x, ok in (("Open Graph", has_og), ("Twitter card", has_tw)) if not ok)
              + " tags" if not (has_og and has_tw) else None)

    # (d) valid XML sitemap that parses and lists real files (2)
    # 2026-08-16 operator ruling (Bink's ask): skipped for single-page live
    # audits — sitemap.xml is never fetched, so "missing" here means "we never
    # asked," not "the real site has no sitemap."
    if not homepage_only:
        s.partial(_sitemap_score(site) * 2, 2, rubric.DOCUMENTED,
                  _sitemap_finding(site))

    # (e) visible last-updated date on content pages (1)
    dated = [n for n, dom in pages.items() if _has_last_updated(dom)]
    s.partial(len(dated) / len(pages), 1, rubric.DOCUMENTED,
              "no visible last-updated date on: "
              + ", ".join(n for n in pages if n not in dated)
              if len(dated) < len(pages) else None)

    if homepage_only:
        # Only (b), (c), (e) are measurable from a homepage-only fetch — 5 of
        # the category's 10 points. (a) and (d) are excluded from both the
        # earned score and the denominator, not auto-zeroed.
        return CategoryResult(
            6, rubric.CATEGORY_NAME[6], 5, round(s.earned, 3), rubric.DOCUMENTED,
            "measured", findings=list(s.findings),
            not_measured_reason="internal-link resolution (3 pts) and sitemap "
            "validity (2 pts) excluded from this category's weight for "
            "single-page live audits — both require artifacts a homepage-only "
            "fetch never retrieves",
            documented_earned=round(s.documented, 3))

    return _mk(6, s, rubric.DOCUMENTED)


def _resolves(site: Path, href: str) -> bool:
    path = href.split("#", 1)[0].split("?", 1)[0].strip()
    if not path:
        return True  # pure fragment/query on same page
    if path.endswith("/"):
        path += "index.html"
    if path == "" or path == "/":
        path = "index.html"
    rel = path.lstrip("/")
    target = (site / rel)
    if target.exists():
        return True
    # extensionless clean URL -> file.html
    if not Path(rel).suffix and (site / (rel + ".html")).exists():
        return True
    return False


def _canonical_self(canon: str, name: str) -> bool:
    path = _url_path(canon).rstrip("/")   # path portion only, e.g. "" or "/about.html"
    tail = path.rsplit("/", 1)[-1]
    if tail == "":                         # root URL is the canonical for index.html
        tail = "index.html"
    return tail == name


def _has_last_updated(dom: _El) -> bool:
    if dom.first("time") is not None:
        return True
    text = dom.text().lower()
    return bool(re.search(r"(last updated|updated on|last reviewed)\b", text))


def _sitemap_score(site: Path) -> float:
    sm = site / "sitemap.xml"
    if not sm.exists():
        return 0.0
    try:
        root = ET.fromstring(sm.read_text(encoding="utf-8"))
    except ET.ParseError:
        return 0.0
    locs = [e.text for e in root.iter() if e.tag.endswith("loc") and e.text]
    if not locs:
        return 0.0
    real = sum(1 for loc in locs if _resolves(site, _url_path(loc)))
    return real / len(locs)


def _sitemap_finding(site: Path) -> str | None:
    score = _sitemap_score(site)
    if score >= 1.0:
        return None
    if not (site / "sitemap.xml").exists():
        return "sitemap.xml is missing"
    return "sitemap.xml is invalid XML or lists files that do not exist"


def _url_path(loc: str) -> str:
    m = re.match(r"https?://[^/]+(/.*)?$", loc.strip())
    if m:
        return m.group(1) or "/"
    return loc.strip()


# =============================================================================
# Category 7 — Citation presence (10) — never measured at this stage
# =============================================================================


def _cat7_citation() -> CategoryResult:
    return CategoryResult(
        7, rubric.CATEGORY_NAME[7], 10, 0.0, rubric.DOCUMENTED, "not_measured",
        findings=[], not_measured_reason="requires live engine queries (Phase 3)",
        documented_earned=0.0)


# =============================================================================
# Assembly
# =============================================================================


def _mk(cat_id: int, s: _Scorer, tier: str) -> CategoryResult:
    return CategoryResult(
        id=cat_id, name=rubric.CATEGORY_NAME[cat_id], weight=rubric.CATEGORY_WEIGHT[cat_id],
        earned=round(s.earned, 3), tier=tier, status="measured",
        findings=list(s.findings), documented_earned=round(s.documented, 3))


def _load_pages(site: Path) -> dict[str, _El]:
    pages: dict[str, _El] = {}
    for html in sorted(site.glob("*.html")):
        pages[html.name] = _parse_html(html.read_text(encoding="utf-8"))
    return pages


def _build_fix_list(categories: list[CategoryResult]) -> list[str]:
    """Prioritized, plain-language fixes — highest-weight category first. Each entry
    names the problem and (implicitly) the points at stake."""
    ordered = sorted(categories, key=lambda c: c.weight, reverse=True)
    fixes: list[str] = []
    for cat in ordered:
        if cat.status != "measured":
            continue
        lost = cat.weight - cat.earned
        if lost <= 0.01:
            continue
        for finding in cat.findings:
            fixes.append(f"[{cat.name}, up to {cat.weight - cat.earned:.0f} pts] {finding}")
    return fixes


def run_audit(site_dir: str | Path, *, cwv: dict | None = None,
              homepage_only: bool = False) -> AuditResult:
    """Audit a directory of generated site files. Every category reads a real
    artifact; unmeasurable categories are excluded from the denominator.

    `homepage_only=True` for live single-page audits (the caller fetched only
    the business's homepage HTML, never robots.txt/llms.txt/sitemap.xml or any
    other page) — Category 3 and part of Category 6 depend on artifacts that
    were never fetched in that mode, so they're excluded rather than
    auto-zeroed. Generated-site audits (`audit_site_from_facts`) leave this
    False since the site engine writes robots.txt and sitemap.xml for real.
    """
    site = Path(site_dir)
    if not site.is_dir():
        raise NotADirectoryError(f"site_dir is not a directory: {site}")
    pages = _load_pages(site)
    if "index.html" not in pages and not pages:
        raise FileNotFoundError(f"no HTML pages found in {site}")
    index = pages.get("index.html") or next(iter(pages.values()))

    categories = [
        _cat1_structured_data(pages),
        _cat2_semantic_html(index),
        _cat3_crawler_access(site, pages, homepage_only),
        _cat4_entity_consistency(pages),
        _cat5_performance(index, cwv),
        _cat6_data_integrity(site, pages, homepage_only),
        _cat7_citation(),
    ]

    measured = [c for c in categories if c.status == "measured"]
    points_available = float(sum(c.weight for c in measured))
    points_earned = float(sum(c.earned for c in measured))
    documented_subtotal = float(sum(c.documented_earned for c in measured))
    normalized = round(points_earned / points_available * 100) if points_available else 0

    _passed = normalized >= rubric.PUBLISH_THRESHOLD
    return AuditResult(
        normalized_score=normalized,
        points_earned=round(points_earned, 2),
        points_available=points_available,
        tier=rubric.tier_for(normalized, passed=_passed),
        passed=_passed,
        documented_subtotal=round(documented_subtotal, 2),
        categories=categories,
        fix_list=_build_fix_list(categories),
        not_measured=[c.name for c in categories if c.status == "not_measured"],
    )


# =============================================================================
# Engine-backed audit — generate a site from facts, then grade it (days 6-8)
# =============================================================================


def audit_site_from_facts(facts: Any, *, cwv: dict | None = None,
                          workdir: str | Path | None = None) -> AuditResult:
    """Generate a full site from confirmed BusinessFacts, then audit it.

    This is the real end-to-end path now that the site engine exists: it
    materializes a per-client site directory via `site_engine.generate_site` and
    grades it with `run_audit`. Every point derives from the generated artifacts,
    which derive from `facts`; nothing is assumed.
    """
    import tempfile
    from .site_engine import generate_site

    out = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="geo_site_"))
    generate_site(facts, out)
    return run_audit(out, cwv=cwv)


def result_to_breakdown(result: AuditResult) -> dict[str, Any]:
    """Serialize an AuditResult for an API response."""
    return {
        "normalized_score": result.normalized_score,
        "points_earned": result.points_earned,
        "points_available": result.points_available,
        "tier": result.tier,
        "passed": result.passed,
        "documented_subtotal": result.documented_subtotal,
        "categories": [
            {"id": c.id, "name": c.name, "weight": c.weight, "earned": c.earned,
             "tier": c.tier, "status": c.status, "findings": c.findings}
            for c in result.categories
        ],
        "fix_list": result.fix_list,
        "not_measured": result.not_measured,
    }


# =============================================================================
# By-site-id entry point — now real, backed by the facts repository
# =============================================================================


def run_ai_readiness_audit(site_id: UUID, *, repo: Any = None,
                           cwv: dict | None = None) -> dict[str, Any]:
    """Audit by site id, end to end. Loads the confirmed BusinessFacts for the
    site via the facts repository, generates the site, grades it, and returns the
    serialized breakdown plus score/passed.

    `repo` defaults to the Supabase-backed repository; inject an
    `InMemoryFactsRepository` (or any FactsRepository) for tests and local runs.
    If the site's required facts are missing or unconfirmed, the repository
    raises `FactsNotConfirmed` — the audit is never run on a guessed record.
    """
    if repo is None:
        from ..repositories.facts_repository import SupabaseFactsRepository
        repo = SupabaseFactsRepository()
    facts = repo.load_business_facts(site_id)
    result = audit_site_from_facts(facts, cwv=cwv)
    out = result_to_breakdown(result)
    out["score"] = result.normalized_score
    out["passed"] = result.passed
    return out
