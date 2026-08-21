# SPEC: SPEC_CCC_M8_REPORTING, Sales Kit extension (2026-08-16)
"""Sales Kit — a single printable/exportable packet combining a real live audit
("before"), a real generated-site proof point ("after"), and pricing.

Built per the 2026-08-16 operator decision for the 2026-08-17 investor demo:
"pulls the audit report + generated site + pricing into one exportable/
printable packet per business." Minimal, real, scoped tight.

Honesty boundary this file exists to hold: the "after" example is NOT a
generated site for the specific business being audited — this session has no
real, operator-confirmed facts (address, phone, hours) for any of the 38 HBOT
businesses, and inventing them would be exactly the fabrication every other
part of this codebase refuses to do. Instead, the "after" is ONE real,
clearly-labeled illustrative example (`ILLUSTRATIVE_HBOT_EXAMPLE` below,
fictional business, real generator, real audit run against it) — proving the
"a generated site clears the gate" claim with a freshly-computed score instead
of the old hardcoded "94" in the Nova UI copy, while never claiming to be any
specific real business's actual future site.
"""
from __future__ import annotations

import html
import tempfile
from pathlib import Path
from typing import Any

from ...core import pricing, rubric
from ...schemas.site_schemas import BusinessFacts, FAQ, Rating, Service
from ..audit_engine import run_audit
from ..site_engine import generate_site
from .render_html import _colors, _esc, _score_gauge  # reuse, don't duplicate

# A fictional, clearly-labeled HBOT clinic — never presented as a real business.
# Real facts, real generator, real audit; only the business itself is illustrative.
#
# 2026-08-21: business_name/domain feed select_theme()'s seed
# (sha256(business_name|domain)), so this fixture's identity string
# deterministically pins one specific template+palette forever. The
# original name/domain happened to hash to Editorial Minimal + Blue --
# byte-for-byte identical to what the original pre-session 3-template/
# 8-palette engine already produced for this exact fixture, confirmed by
# diffing against the initial commit. That meant every bare "Site
# Generator" click (the demo's own zero-context fallback path) looked
# untouched by an entire session of design-library growth, not because
# the new engine wasn't live, but by pure hash coincidence on this one
# fixture. Changed to a name that hashes onto Trust Panel -- one of the
# two Dental/Medical-family templates actually added this session, and
# thematically apt for a medical business (its whole design is a
# persistent trust-fact sidebar).
ILLUSTRATIVE_HBOT_EXAMPLE = BusinessFacts(
    business_name="Meridian Hyperbaric Wellness (illustrative)",
    subtype="MedicalClinic",
    street="100 Example Way", locality="Example City", region="CA",
    postal_code="90001", telephone="+1-555-010-0100",
    domain="meridian-hyperbaric-illustrative.example",
    hours=["Mon-Fri 8:00-17:00", "Sat 9:00-13:00"],
    service_areas=["Example City", "Example County"],
    services=[
        Service(name="Hyperbaric Oxygen Therapy",
                description="Monoplace-chamber HBOT sessions for wound healing, recovery, and approved indications."),
        Service(name="Post-Treatment Consultation",
                description="Follow-up review of treatment response with a licensed provider."),
        Service(name="New Patient Intake",
                description="Initial evaluation to confirm candidacy and build a treatment plan."),
    ],
    credentials=["UHMS-affiliated staff (illustrative)"],
    faqs=[
        FAQ(question="How many sessions does HBOT typically take?",
            answer="Course length varies by indication and is set by your treating physician."),
        FAQ(question="Is HBOT covered by insurance?",
            answer="Coverage depends on your plan and the approved indication being treated."),
    ],
    same_as=["https://g.page/example-hyperbaric-illustrative"],
    # Illustrative rating — not a real business, no real reviews exist to cite.
    rating=Rating(value=4.8, count=126),
    last_updated="2026-08-16",
    tagline="Illustrative example — not a real business",
)

_PACKET_CACHE: dict | None = None  # the "after" is identical for every kit; compute once per process


def _after_example() -> dict:
    """Real generate + real audit of the illustrative example, cached in-process
    (deterministic input, no reason to regenerate per request)."""
    global _PACKET_CACHE
    if _PACKET_CACHE is not None:
        return _PACKET_CACHE
    with tempfile.TemporaryDirectory(prefix="geo_kit_example_") as tmpdir:
        out = Path(tmpdir)
        generate_site(ILLUSTRATIVE_HBOT_EXAMPLE, out)
        result = run_audit(out)  # NOT homepage_only — the generator writes real robots.txt/sitemap.xml
    _PACKET_CACHE = {
        "score": result.normalized_score,
        "passed": result.passed,
        "not_measured": result.not_measured,
    }
    return _PACKET_CACHE


def _tier_html(name: str, price: int, tag: str, bullets: list[str], popular: bool = False) -> str:
    badge = '<div class="kit-plan-badge">Most popular</div>' if popular else ""
    items = "".join(f"<li>{_esc(b)}</li>" for b in bullets)
    cls = "kit-plan popular" if popular else "kit-plan"
    return (
        f'<div class="{cls}">{badge}<div class="kit-plan-name">{_esc(name)}</div>'
        f'<div class="kit-plan-price">${price:,}<span>/mo</span></div>'
        f'<div class="kit-plan-tag">{_esc(tag)}</div><ul>{items}</ul></div>'
    )


def _pricing_html() -> str:
    # core/pricing.py is the one place these tiers are defined -- the same
    # data GET /sales/pricing-tiers hands the live Nova demo, instead of two
    # hardcoded copies kept in sync by hand.
    tiers = "".join(
        _tier_html(t["name"], t["price"], t["tag"], t["bullets"], popular=t["popular"])
        for t in pricing.PRICING_TIERS
    )
    return (
        '<section class="block"><h2>Pricing</h2><div class="kit-plans">'
        + tiers
        + '</div><p class="kit-plan-note">Illustrative pricing — pending final sign-off.</p></section>'
    )


def render_sales_kit_html(business_name: str, before_score: int, before_gaps: list[str],
                          before_not_measured: list[str]) -> str:
    """The full printable packet: before (real live audit) + after (real
    illustrative generated-site proof) + pricing + honesty disclosures."""
    colors = _colors(None)
    name = _esc(business_name or "Prospect")
    after = _after_example()

    before_gauge = _score_gauge(float(before_score), colors)
    after_gauge = _score_gauge(float(after["score"]), colors)
    gaps_html = "".join(f"<li>{_esc(g)}</li>" for g in before_gaps[:5]) or "<li>No gaps returned.</li>"
    nm_html = (
        f'<p class="kit-note">Not measured for this live single-page audit: {_esc(", ".join(before_not_measured))}.</p>'
        if before_not_measured else ""
    )

    prelim_html = ""
    if rubric.AI_SEARCH_READINESS_CLAIMS_PAUSED:
        # 2026-08-16: the Brain Trust's HOLD on score trustworthiness (steps 2-4
        # of its own handoff) passed independent re-verification the same day —
        # Jasiah's fresh 68/68 test run, Bink's bit-for-bit spot re-score of 5
        # live businesses, Category 7 exclusion and this very disclosure both
        # confirmed actually working. That HOLD is lifted; do not restate it
        # here. This banner now reflects the one gap still genuinely open: the
        # rubric's category weights have no cited empirical source (open since
        # 2026-08-08, unrelated to the fix that was just verified).
        prelim_html = (
            '<div class="kit-prelim">PRELIMINARY — the rubric\'s category weights '
            "(20/20/12/13/15/10/10) are not yet traced to a cited source or stated "
            "confidence interval. The score itself is real and independently "
            "re-verified (2026-08-16); it's the weighting behind it that's still "
            "open. Do not present as a finished client-facing readiness claim "
            "until that's closed.</div>"
        )

    css = f"""
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      color: {colors['ink']}; background: {colors['surface']}; margin: 0; }}
    .kit {{ max-width: 760px; margin: 0 auto; padding: 32px 28px; }}
    header.brand {{ border-bottom: 3px solid {colors['accent']}; padding-bottom: 14px; margin-bottom: 8px; }}
    header.brand h1 {{ font-size: 22px; margin: 0; }}
    header.brand .sub {{ color: {colors['muted']}; font-size: 13px; margin-top: 2px; }}
    .kit-prelim {{ margin: 14px 0; padding: 10px 14px; border: 1px solid {colors['gate']};
      border-radius: 9px; background: #fff7f0; color: {colors['gate']}; font-size: 12px; line-height: 1.6; }}
    .block {{ padding: 18px 0; border-bottom: 1px solid {colors['line']}; }}
    .block h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: .04em;
      color: {colors['muted']}; margin: 0 0 12px; }}
    .kit-compare {{ display: flex; gap: 24px; flex-wrap: wrap; }}
    .kit-col {{ flex: 1; min-width: 260px; }}
    .kit-col h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .04em; margin: 0 0 6px; }}
    .kit-col .score-num {{ font-size: 32px; font-weight: 700; }}
    .kit-col .score-num span {{ font-size: 14px; color: {colors['muted']}; font-weight: 400; }}
    .kit-col .kit-label {{ font-size: 11px; color: {colors['muted']}; margin-top: 4px; }}
    .kit-note {{ font-size: 11px; color: {colors['muted']}; margin-top: 8px; }}
    ul.kit-gaps {{ font-size: 12px; padding-left: 18px; margin: 8px 0 0; }}
    .kit-plans {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .kit-plan {{ flex: 1; min-width: 180px; border: 1px solid {colors['line']}; border-radius: 10px;
      padding: 14px 16px; position: relative; }}
    .kit-plan.popular {{ border-color: {colors['accent']}; }}
    .kit-plan-badge {{ position: absolute; top: -10px; left: 14px; background: {colors['accent']};
      color: #fff; font-size: 10px; padding: 2px 8px; border-radius: 6px; }}
    .kit-plan-name {{ font-weight: 700; font-size: 13px; }}
    .kit-plan-price {{ font-size: 22px; font-weight: 700; margin-top: 4px; }}
    .kit-plan-price span {{ font-size: 12px; color: {colors['muted']}; font-weight: 400; }}
    .kit-plan-tag {{ font-size: 11px; color: {colors['muted']}; margin: 4px 0 8px; }}
    .kit-plan ul {{ font-size: 11px; padding-left: 16px; margin: 0; }}
    .kit-plan-note {{ font-size: 11px; color: {colors['muted']}; margin-top: 10px; }}
    @media print {{ .kit {{ max-width: none; }} .block {{ break-inside: avoid; }} }}
    """

    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"/>"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
        f"<title>{name} — GEO Suite Sales Kit</title>"
        f"<style>{css}</style></head><body><main class=\"kit\">"
        f'<header class="brand"><h1>{name}</h1><div class="sub">GEO Suite Sales Kit</div></header>'
        f"{prelim_html}"
        '<section class="block"><h2>Before / After</h2><div class="kit-compare">'
        f'<div class="kit-col"><h3>Today, live-measured</h3>'
        f'<div class="score-num">{float(before_score):g}<span>/100</span></div>'
        f'{before_gauge}<div class="kit-label">real, this business, just now</div>'
        f'<ul class="kit-gaps">{gaps_html}</ul>{nm_html}</div>'
        f'<div class="kit-col"><h3>After — illustrative example</h3>'
        f'<div class="score-num">{float(after["score"]):g}<span>/100</span></div>'
        f'{after_gauge}<div class="kit-label">a real generated site, freshly audited — '
        f'NOT this business\'s actual future site, a proof of concept</div></div>'
        "</div></section>"
        f"{_pricing_html()}"
        "</main></body></html>"
    )
