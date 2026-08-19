"""WCAG 2.1 AA static-subset + health-marketing + PHI compliance checker.

Pure, importable, offline. Parses local HTML; no live crawl in the battery.
Two entry points via audit_site(): publish gate (blocking) and prospect auditor (gap score).

2026-08-16: check_citation_records() adds Phase 1 of the citation-rigor
tracked item (see the module docstring in
backend/app/schemas/compliance_schemas.py for the full three-phase ruling).
It is a structural presence/quality gate over CitationRecord objects, the
same kind of check as check_phi_testimonials() below: pattern and field
checks, not a reasoning engine, and it makes no judgment about whether a
citation actually rescues a claim, that judgment is always a lawyer-authored
CitationRecord, never computed here. It is deliberately NOT called from
audit_site() yet; Phase 3 wires it into the publish path once Phase 2
supplies real, ratified CitationRecord content to check. Calling it today
against an empty record list, which is the correct state until Phase 2 runs,
returns no findings.

2026-08-18: generalized rules learned from a real health-marketing legal
review, encoded here as reusable logic (never as facts about the specific
business or matter reviewed -- nothing client-specific belongs in this
module or in knowledge_core; only the legal reasoning does):

- The net-impression rule (FTC Act §5; state consumer-fraud analogs read
  the same way): an ad is judged by the overall message a reasonable
  consumer takes away, not by whether a risky sentence sits inside
  quotation marks or next to a footnote. A citation can convert an
  unsubstantiated claim into a sourced, hedged one -- but it cannot rescue
  absolute or guarantee language ("permanent," "eliminates," "guaranteed,"
  and the like); those represent a certainty no citation supplies, so they
  are checked unconditionally, never defused by a nearby disclaimer.
  DEFAULT_ABSOLUTE_GUARANTEE_TERMS / marketing-unrescuable-guarantee-claim.
- Citation-scope extrapolation: a citation only substantiates a claim that
  shares the underlying study's actual modality and population. Evidence
  for a narrow, local intervention (e.g. an injection at one site) does
  not substantiate a systemic or whole-body claim -- that gap can't be
  closed by better wording, only by narrowing the claim or finding
  evidence that actually covers it. check_citation_records() flags a
  record whose claim_scope mixes a narrow-evidence marker with a systemic-
  claim marker. See _NARROW_EVIDENCE_MARKERS / _SYSTEMIC_CLAIM_MARKERS /
  citation-scope-extrapolation.
- The establishment-claim substantiation bar (already encoded, 2026-08-16):
  "studies show X" is a stronger representation than a hedged opinion, and
  requires a tighter applicability_boundary before it can rely on a
  citation at all. See _ESTABLISHMENT_CLAIM_MIN_BOUNDARY_LENGTH.
- Anti-cherry-picking (already encoded): a citation must carry its own
  real, distinct limitation, not a placeholder or the claim scope repeated
  back -- quoting a favorable finding while omitting a study's own stated
  limitation is itself a deceptive-omission pattern.
"""
from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from pathlib import Path

from ...schemas.compliance_schemas import CitationRecord, ClaimStrength
from .regulatory_citations import citations_for_rule

# Default off-label HBOT high-risk terms (parameter, not hardcoded at call sites).
DEFAULT_HIGH_RISK_TERMS: list[str] = [
    "cure",
    "cures",
    "reverse aging",
    "autism",
    "lyme",
    "cancer",
    "miracle",
    "guaranteed cure",
    "fda approved for",
    "treats autism",
    "eliminates",
]

# Absolute / guarantee language. Per the net-impression rule (FTC Act §5;
# Iowa's Consumer Fraud Act draws the same "overall message a reasonable
# consumer takes away" line), a citation or hedge placed near one of these
# words does not rescue it the way it rescues an ordinary unsubstantiated
# claim -- "permanent," "eliminates," "guaranteed," and their siblings are
# themselves the violation, because they represent a certainty no citation
# can supply. A footnote does not un-say a guarantee. So these are checked
# unconditionally in check_marketing_claims(), never defused by a nearby
# _EVIDENCE_MARKERS hit the way DEFAULT_HIGH_RISK_TERMS are.
DEFAULT_ABSOLUTE_GUARANTEE_TERMS: list[str] = [
    "permanent treatment",
    "permanently cures",
    "permanently cure",
    "guaranteed",
    "guarantee results",
    "removes the cause",
    "maximum results",
    "extremely safe",
    "completely safe",
    "100% safe",
    "no risk",
    "zero risk",
    "reverses your",
    "reverse your condition",
    "reverse their condition",
]

# Adjacent evidence / hedge markers that substantiate a nearby health claim.
_EVIDENCE_MARKERS: tuple[str, ...] = (
    "disclaimer",
    "consult your physician",
    "consult your doctor",
    "results may vary",
    "not intended to diagnose",
    "not evaluated by the fda",
    "citation",
    "study",
    "research",
    "evidence",
    "data-claim-evidence",
    "data-disclaimer",
    "may help",
    "may support",
    "individual results",
    "[1]",
    "[2]",
    "[3]",
)

_TESTIMONIAL_HINTS: tuple[str, ...] = (
    "testimonial",
    "patient-story",
    "patient_story",
    "review-quote",
    "patient-review",
)

_CONDITION_TERMS: tuple[str, ...] = (
    "autism",
    "cancer",
    "lyme",
    "diabetes",
    "arthritis",
    "depression",
    "anxiety",
    "fibromyalgia",
    "migraine",
    "chronic pain",
    "tbi",
    "stroke",
)

_NAME_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
)

_HEX_COLOR = re.compile(r"#([0-9a-fA-F]{3,8})\b")
_RGB_COLOR = re.compile(
    r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", re.I
)


# ---------------------------------------------------------------------------
# Lightweight DOM (stdlib only, mirrors audit_engine pattern)
# ---------------------------------------------------------------------------

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
         "link", "meta", "param", "source", "track", "wbr"}


class _El:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: list[tuple[str, str | None]]):
        self.tag = tag
        self.attrs: dict[str, str] = {k.lower(): (v or "") for k, v in attrs}
        self.children: list = []
        self.parent: _El | None = None

    def iter(self):
        for c in self.children:
            if isinstance(c, _El):
                yield c
                yield from c.iter()

    def find_all(self, *tags: str) -> list["_El"]:
        want = set(tags)
        return [e for e in self.iter() if e.tag in want]

    def text(self) -> str:
        out: list[str] = []
        for c in self.children:
            out.append(c if isinstance(c, str) else c.text())
        return "".join(out)

    def attr(self, name: str) -> str:
        return self.attrs.get(name.lower(), "")

    def has_ancestor_attr(self, name: str, value: str = "true") -> bool:
        node: _El | None = self
        while node is not None and node.tag != "#document":
            if node.attr(name).lower() == value.lower():
                return True
            node = node.parent
        return False

    def class_id_blob(self) -> str:
        return f"{self.attr('class')} {self.attr('id')}".lower()


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


def _finding(rule: str, severity: str, element: str, message: str) -> dict:
    return {"rule": rule, "severity": severity, "element": element, "message": message}


def _load_html(path_or_html: str) -> tuple[str | None, list[dict]]:
    """Return (html, input_findings). Never raises."""
    if path_or_html is None:
        return None, [_finding(
            "input-empty", "error", "input",
            "Input is empty or missing; cannot audit compliance.",
        )]

    raw = str(path_or_html).strip()
    if not raw:
        return None, [_finding(
            "input-empty", "error", "input",
            "Input is empty or missing; cannot audit compliance.",
        )]

    if raw.lstrip().startswith("<"):
        return raw, []

    p = Path(raw)
    if p.is_dir():
        index = p / "index.html"
        if not index.is_file():
            return None, [_finding(
                "input-missing", "error", "path",
                f"Directory {raw!r} has no index.html.",
            )]
        try:
            return index.read_text(encoding="utf-8"), []
        except OSError as exc:
            return None, [_finding(
                "input-read-error", "error", "path",
                f"Cannot read {index}: {exc}",
            )]

    if p.is_file():
        try:
            return p.read_text(encoding="utf-8"), []
        except OSError as exc:
            return None, [_finding(
                "input-read-error", "error", "path",
                f"Cannot read {raw!r}: {exc}",
            )]

    if not os.path.exists(raw):
        return None, [_finding(
            "input-missing", "error", "path",
            f"Path not found: {raw!r}.",
        )]

    return raw, []


# ---------------------------------------------------------------------------
# Color contrast helpers (WCAG 2.1 relative luminance)
# ---------------------------------------------------------------------------

def _expand_hex(h: str) -> str:
    if len(h) == 3:
        return "".join(c + c for c in h)
    if len(h) == 6:
        return h
    return h[:6]


def _parse_color(value: str) -> tuple[float, float, float] | None:
    value = (value or "").strip()
    m = _HEX_COLOR.search(value)
    if m:
        h = _expand_hex(m.group(1))
        try:
            r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
            return r, g, b
        except ValueError:
            return None
    m = _RGB_COLOR.search(value)
    if m:
        return int(m.group(1)) / 255.0, int(m.group(2)) / 255.0, int(m.group(3)) / 255.0
    return None


def _srgb(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = (_srgb(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    l1, l2 = _luminance(fg), _luminance(bg)
    bright, dark = max(l1, l2), min(l1, l2)
    return (bright + 0.05) / (dark + 0.05)


# ---------------------------------------------------------------------------
# Public check functions
# ---------------------------------------------------------------------------

def check_accessibility(html: str) -> tuple[int, list[dict]]:
    """WCAG 2.1 AA static subset. Returns (score_0_100, findings)."""
    if not (html or "").strip():
        f = _finding(
            "input-empty", "error", "html",
            "HTML input is empty; accessibility cannot be assessed.",
        )
        return 0, [f]

    root = _parse_html(html)
    html_el = root.find_all("html")
    findings: list[dict] = []

    # lang attribute on <html>
    lang = ""
    if html_el:
        lang = html_el[0].attr("lang").strip()
    if not lang:
        findings.append(_finding(
            "wcag-lang", "error", "html",
            "Document is missing a non-empty lang attribute on <html>.",
        ))

    # exactly one h1
    h1s = root.find_all("h1")
    if len(h1s) == 0:
        findings.append(_finding(
            "wcag-h1-missing", "error", "h1",
            "Document must contain exactly one <h1>; found none.",
        ))
    elif len(h1s) > 1:
        findings.append(_finding(
            "wcag-h1-multiple", "error", "h1",
            f"Document must contain exactly one <h1>; found {len(h1s)}.",
        ))

    # logical heading order (no level skips)
    headings = [(e.tag, e) for e in root.iter() if re.fullmatch(r"h[1-6]", e.tag)]
    prev_level = 0
    for tag, el in headings:
        level = int(tag[1])
        if prev_level and level > prev_level + 1:
            findings.append(_finding(
                "wcag-heading-order", "error", tag,
                f"Heading level skips from h{prev_level} to h{level}.",
            ))
        prev_level = level

    # images: alt or role=presentation
    for img in root.find_all("img"):
        role = img.attr("role").lower()
        alt = img.attr("alt")
        if role == "presentation":
            continue
        if not alt.strip():
            src = img.attr("src") or "(no src)"
            findings.append(_finding(
                "wcag-alt-text", "error", "img",
                f"Image missing non-empty alt text: {src}.",
            ))

    # form controls: associated label
    for control in root.find_all("input", "select", "textarea"):
        ctype = control.attr("type").lower()
        if ctype in ("hidden", "submit", "button", "reset"):
            continue
        cid = control.attr("id")
        aria = control.attr("aria-label") or control.attr("aria-labelledby")
        if aria.strip():
            continue
        labeled = False
        if cid:
            for lab in root.find_all("label"):
                if lab.attr("for") == cid:
                    labeled = True
                    break
        if not labeled:
            parent = control.parent
            if parent and parent.tag == "label" and parent.text().strip():
                labeled = True
        if not labeled:
            findings.append(_finding(
                "wcag-form-label", "error", control.tag,
                f"Form control missing associated label (id={cid or 'none'}).",
            ))

    # links: discernible text
    for link in root.find_all("a"):
        text = link.text().strip()
        aria = link.attr("aria-label").strip()
        if text or aria:
            continue
        imgs = link.find_all("img")
        if any(img.attr("alt").strip() for img in imgs):
            continue
        href = link.attr("href") or "(no href)"
        findings.append(_finding(
            "wcag-link-text", "error", "a",
            f"Link has no discernible text: {href}.",
        ))

    # inline color contrast below 4.5:1
    for el in root.iter():
        if not isinstance(el, _El):
            continue
        style = el.attr("style")
        if not style or "color" not in style.lower():
            continue
        fg = _parse_color(style)
        bg = _parse_color(style.split("background")[-1] if "background" in style.lower() else "")
        if fg and bg:
            ratio = _contrast_ratio(fg, bg)
            if ratio < 4.5:
                findings.append(_finding(
                    "wcag-color-contrast", "error", el.tag,
                    f"Inline style contrast {ratio:.2f}:1 is below 4.5:1 for normal text.",
                ))

    # accessibility statement link
    has_a11y_link = False
    for link in root.find_all("a"):
        blob = f"{link.attr('href')} {link.text()}".lower()
        if "accessibility" in blob:
            has_a11y_link = True
            break
    if not has_a11y_link:
        findings.append(_finding(
            "wcag-accessibility-statement", "error", "a",
            "Page is missing a link to an accessibility statement.",
        ))

    # score: start at 100, deduct per finding
    error_count = sum(1 for f in findings if f["severity"] == "error")
    score = max(0, 100 - error_count * 12)
    return score, findings


def check_marketing_claims(
    text: str,
    *,
    high_risk_terms: list[str] | None = None,
    absolute_guarantee_terms: list[str] | None = None,
) -> list[dict]:
    """Flag health claims lacking a hedge or citation near the claim, and
    separately, flag absolute/guarantee language that no nearby hedge or
    citation can rescue in the first place (see DEFAULT_ABSOLUTE_GUARANTEE_TERMS).
    """
    if not (text or "").strip():
        return [_finding(
            "input-empty", "error", "text",
            "Text input is empty; marketing claims cannot be assessed.",
        )]

    terms = high_risk_terms if high_risk_terms is not None else DEFAULT_HIGH_RISK_TERMS
    absolutes = (
        absolute_guarantee_terms if absolute_guarantee_terms is not None
        else DEFAULT_ABSOLUTE_GUARANTEE_TERMS
    )
    lowered = text.lower()
    findings: list[dict] = []
    window = 220

    for term in terms:
        t = term.lower().strip()
        if not t:
            continue
        start = 0
        while True:
            idx = lowered.find(t, start)
            if idx == -1:
                break
            ctx_start = max(0, idx - window)
            ctx_end = min(len(lowered), idx + len(t) + window)
            context = lowered[ctx_start:ctx_end]
            if not any(marker in context for marker in _EVIDENCE_MARKERS):
                findings.append(_finding(
                    "marketing-unsubstantiated-claim", "error", "text",
                    f"High-risk health claim {term!r} lacks adjacent evidence or disclaimer.",
                ))
            start = idx + len(t)

    for term in absolutes:
        t = term.lower().strip()
        if not t:
            continue
        start = 0
        while True:
            idx = lowered.find(t, start)
            if idx == -1:
                break
            findings.append(_finding(
                "marketing-unrescuable-guarantee-claim", "error", "text",
                f"Absolute/guarantee language {term!r} found. Per the net-"
                "impression rule, this is not rescued by a nearby citation "
                "or disclaimer -- the fix is to remove or reword the claim "
                "itself, not to footnote it.",
            ))
            start = idx + len(t)

    return findings


def check_phi_testimonials(html: str) -> list[dict]:
    """Flag testimonial blocks lacking authorization or containing identifiers."""
    if not (html or "").strip():
        return [_finding(
            "input-empty", "error", "html",
            "HTML input is empty; PHI testimonials cannot be assessed.",
        )]

    root = _parse_html(html)
    findings: list[dict] = []

    candidates: list[_El] = []
    for el in root.iter():
        if not isinstance(el, _El):
            continue
        blob = el.class_id_blob()
        if any(h in blob for h in _TESTIMONIAL_HINTS):
            candidates.append(el)
        elif el.tag == "blockquote" and el.text().strip():
            candidates.append(el)

    if not candidates:
        return findings

    for block in candidates:
        text = block.text().strip()
        if not text:
            continue
        if block.has_ancestor_attr("data-hipaa-authorized") or block.attr("data-hipaa-authorized").lower() == "true":
            continue

        findings.append(_finding(
            "phi-unauthorized-testimonial", "error", block.tag,
            "Testimonial or patient story block lacks data-hipaa-authorized marker.",
        ))

        names = _NAME_PATTERN.findall(text)
        lower_text = text.lower()
        for name in names:
            if any(cond in lower_text for cond in _CONDITION_TERMS):
                findings.append(_finding(
                    "phi-identifier-in-testimonial", "error", block.tag,
                    f"Testimonial contains likely identifier ({name}) with a health condition.",
                ))
                break

    return findings


_PLACEHOLDER_LIMITATIONS: tuple[str, ...] = (
    "tbd", "n/a", "na", "none", "unknown", "todo", "pending", "-", "--",
)

# Per the memo's substantiation-bar rule, an establishment claim ("studies
# show X") needs a tighter applicability_boundary than a hedged opinion
# before it can rely on a citation at all. This threshold is a structural
# length floor standing in for that rule, not a judgment about whether the
# boundary text is actually correct or sufficient; a lawyer's ratification
# is what determines that, this only catches an establishment claim paired
# with a boundary too thin to have been seriously scoped.
_ESTABLISHMENT_CLAIM_MIN_BOUNDARY_LENGTH = 15

# A citation only substantiates a claim that shares the study's actual
# modality and population -- a study of a narrow, local intervention (an
# injection at one site, a topical application) cannot be cited to support
# a systemic or whole-body claim; the underlying evidence never tested
# that. This is a scope mismatch, not a strength-of-evidence question, and
# no amount of rewording rescues it: the only fixes are to narrow the claim
# to match the evidence, or find evidence that actually covers the broader
# claim. Checked by looking for both a narrow-evidence marker and a
# systemic-claim marker inside the same claim_scope -- that combination is
# exactly what it looks like when a citation is being stretched past what
# it showed.
_NARROW_EVIDENCE_MARKERS: tuple[str, ...] = (
    "local injection",
    "injected joint",
    "injection site",
    "at the injection site",
    "topical",
    "topically",
    "in vitro",
    "single site",
    "localized",
)
_SYSTEMIC_CLAIM_MARKERS: tuple[str, ...] = (
    "systemic",
    "whole-body",
    "whole body",
    "immune system",
    "throughout the body",
    "eliminat",
    "restart your body",
    "reverse your condition",
    "reverse their condition",
    "reverse the condition",
)


def check_citation_records(records: list[CitationRecord]) -> list[dict]:
    """Structural presence/quality gate over citation records, Phase 1 of the
    citation-rigor tracked item. Same kind of check as check_phi_testimonials()
    above: pattern and field checks, never a judgment about whether a citation
    actually rescues a claim. That judgment is always a lawyer-authored,
    ratified CitationRecord; this function only checks that the record in
    front of it is structurally complete enough to be usable at all.

    Pydantic already refuses to construct a CitationRecord with a missing or
    whitespace-only required field (see compliance_schemas.py), so every
    finding here is a second-layer content-quality check beyond "is the
    field present": a limitation that's just a placeholder string, a
    limitation that was accidentally copy-pasted as the claim scope itself,
    and an establishment claim whose applicability_boundary is too thin to
    have been seriously scoped.

    Not wired into audit_site(). Phase 3 of the tracked item wires this into
    the publish path once Phase 2 supplies real, ratified records. An empty
    or missing records list returns no findings, which is the correct,
    honest result until Phase 2 exists, not an error.
    """
    if not records:
        return []

    findings: list[dict] = []
    for record in records:
        ref = record.source_note_id or record.study_reference

        limitation_lower = record.limitation.strip().lower()
        if limitation_lower in _PLACEHOLDER_LIMITATIONS:
            findings.append(_finding(
                "citation-placeholder-limitation", "error", "citation_record",
                f"Citation record ({ref}) has a placeholder limitation "
                f"({record.limitation!r}) instead of a real stated limitation "
                "or contradicting finding. The anti-cherry-pick rule requires "
                "a real one.",
            ))

        if record.limitation.strip().lower() == record.claim_scope.strip().lower():
            findings.append(_finding(
                "citation-limitation-equals-scope", "error", "citation_record",
                f"Citation record ({ref}) has an identical claim_scope and "
                "limitation, which means no real limitation was actually "
                "recorded, only the claim repeated back.",
            ))

        if (
            record.claim_strength == ClaimStrength.ESTABLISHMENT_CLAIM
            and len(record.applicability_boundary.strip()) < _ESTABLISHMENT_CLAIM_MIN_BOUNDARY_LENGTH
        ):
            findings.append(_finding(
                "citation-establishment-claim-thin-boundary", "error", "citation_record",
                f"Citation record ({ref}) is marked establishment_claim but its "
                f"applicability_boundary ({record.applicability_boundary!r}) is "
                "too thin to have been seriously scoped. Per the substantiation-"
                "bar rule, an establishment claim needs a tighter boundary, not "
                "a looser one.",
            ))

        scope_lower = record.claim_scope.strip().lower()
        has_narrow_evidence = any(m in scope_lower for m in _NARROW_EVIDENCE_MARKERS)
        has_systemic_claim = any(m in scope_lower for m in _SYSTEMIC_CLAIM_MARKERS)
        if has_narrow_evidence and has_systemic_claim:
            findings.append(_finding(
                "citation-scope-extrapolation", "error", "citation_record",
                f"Citation record ({ref}) describes narrow/local evidence "
                f"(claim_scope: {record.claim_scope!r}) alongside a systemic "
                "or whole-body claim in the same scope. A study of a local "
                "or narrow intervention does not substantiate a systemic "
                "claim; narrow the claim to what was actually studied, or "
                "cite evidence that covers the systemic claim directly.",
            ))

    return findings


def _text_from_html(html: str) -> str:
    root = _parse_html(html)
    parts: list[str] = []

    def walk(el):
        if isinstance(el, str):
            parts.append(el)
        else:
            for c in el.children:
                walk(c)

    walk(root)
    return " ".join(parts)


def _compliance_gap(
    a11y_score: int,
    marketing: list[dict],
    phi: list[dict],
    a11y_findings: list[dict],
) -> int:
    """Higher gap = worse compliance = better sales opportunity."""
    gap = 100 - a11y_score
    gap += 15 * len(marketing)
    gap += 20 * len(phi)
    gap += 5 * sum(1 for f in a11y_findings if f["severity"] == "error")
    return min(100, max(0, gap))


def audit_site(path_or_html: str, *, mode: str) -> dict:
    """Audit a site for compliance.

    mode='publish' -> {ok, blocking[]}
    mode='prospect' -> {compliance_gap_0_100, findings[]}
    """
    html, input_findings = _load_html(path_or_html)
    if html is None:
        if mode == "publish":
            return {"ok": False, "blocking": input_findings}
        gap = 100 if input_findings else 0
        return {"compliance_gap_0_100": gap, "findings": input_findings}

    a11y_score, a11y_findings = check_accessibility(html)
    marketing = check_marketing_claims(_text_from_html(html))
    phi = check_phi_testimonials(html)
    all_findings = a11y_findings + marketing + phi

    for f in all_findings:
        f["legal_basis"] = citations_for_rule(f["rule"])

    if mode == "publish":
        blocking = [
            f for f in all_findings
            if f["severity"] == "error"
            and (
                f["rule"].startswith("wcag-")
                or f["rule"].startswith("marketing-")
                or f["rule"].startswith("phi-")
            )
        ]
        return {"ok": len(blocking) == 0, "blocking": blocking}

    if mode == "prospect":
        gap = _compliance_gap(a11y_score, marketing, phi, a11y_findings)
        return {"compliance_gap_0_100": gap, "findings": all_findings}

    raise ValueError(f"Unknown mode {mode!r}; use 'publish' or 'prospect'.")
