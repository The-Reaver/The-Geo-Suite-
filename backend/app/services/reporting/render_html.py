# SPEC: SPEC_CCC_M8_REPORTING (branded report renderer)
"""Branded, charted, print-ready HTML report renderer.

Closes GEO Brain Trust open item 7: reports were raw JSON and plain text with no
PDF, no charts, no branded layout, though the data layer underneath is real.
This renders that same real data (the `view` produced by dashboard.py and
white-labelled by export.apply_white_label) into a branded document.

Fidelity bar (Amaya's ruling): mid-fi. Branded header, an AI-readiness score
gauge with the 90 publish-gate line, per-metric bars that DRAW their confidence
interval as an error bar, an optional rubric-category breakdown, and the
non-negotiable methodology + limitations blocks. Charts are inline SVG — no JS,
no external assets, no fonts to fetch — so the document is self-contained and
converts to PDF cleanly with any headless print step at deploy. This mirrors
site_engine.py's inline-everything approach and adds zero dependencies, keeping
the battery pure and offline.

Honesty rules enforced here, not optional:
  - A withheld / not-measured / insufficient metric renders its STATUS label,
    never a bar at zero (dashboard.render_metric's rule, carried into pixels).
  - Every rendered sampled metric shows its interval; the bar carries the error
    whisker so the number is never seen without its uncertainty.
  - The limitations block and methodology block always render; export's
    _assert_exportable refusal runs first, so an un-honest view cannot be
    rendered at all.
  - An UNVALIDATED weights status is shown as a visible badge, not buried.
"""
from __future__ import annotations

import html
from typing import Any

from ...core import rubric
from .dashboard import render_metric
from .export import _assert_exportable

# 2026-08-16: was hardcoded 90 here, independently of rubric.PUBLISH_THRESHOLD
# (raised to 93 on 2026-08-08) — the same staleness bug found in the Nova UI
# and this session's market-research files, caught here by the same pass.
_PUBLISH_GATE = rubric.PUBLISH_THRESHOLD

# Neutral defaults; overridden per client by branding.colors.
_DEFAULT_COLORS = {
    "ink": "#1a2332",
    "muted": "#5b6b82",
    "accent": "#2f6df6",
    "gate": "#c2410c",
    "bar": "#2f6df6",
    "bar_track": "#e6ebf4",
    "surface": "#ffffff",
    "line": "#d9e0ec",
}


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _colors(branding: dict | None) -> dict:
    colors = dict(_DEFAULT_COLORS)
    supplied = (branding or {}).get("colors") or {}
    if isinstance(supplied, dict):
        for k, v in supplied.items():
            if k in colors and v:
                colors[k] = str(v)
    return colors


def _metrics_items(view: dict) -> list[dict]:
    metrics = (view or {}).get("metrics") or {}
    if isinstance(metrics, dict):
        items = []
        for key, rec in metrics.items():
            if isinstance(rec, dict):
                rec = dict(rec)
                rec.setdefault("name", key)
                items.append(rec)
        return items
    if isinstance(metrics, list):
        return [m for m in metrics if isinstance(m, dict)]
    return []


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _score_gauge(score: float, colors: dict) -> str:
    """A horizontal 0-100 gauge with the publish-gate line drawn in. score is
    assumed already validated numeric by the caller."""
    w, h = 360, 44
    pad = 2
    track_w = w - pad * 2
    fill = _clamp01(score / 100.0) * track_w
    gate_x = pad + _clamp01(_PUBLISH_GATE / 100.0) * track_w
    passed = score >= _PUBLISH_GATE
    fill_color = colors["accent"] if passed else colors["gate"]
    return (
        f'<svg viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="AI readiness score {score:g} of 100, publish gate {_PUBLISH_GATE}" '
        f'width="100%" height="{h}">'
        f'<rect x="{pad}" y="14" width="{track_w}" height="16" rx="8" fill="{colors["bar_track"]}"/>'
        f'<rect x="{pad}" y="14" width="{fill:.1f}" height="16" rx="8" fill="{fill_color}"/>'
        f'<line x1="{gate_x:.1f}" y1="8" x2="{gate_x:.1f}" y2="36" stroke="{colors["gate"]}" '
        f'stroke-width="2" stroke-dasharray="3 2"/>'
        f'<text x="{gate_x:.1f}" y="6" font-size="9" fill="{colors["gate"]}" '
        f'text-anchor="middle">gate {_PUBLISH_GATE}</text>'
        f'</svg>'
    )


def _metric_bar(rec: dict, colors: dict) -> str:
    """One metric row. A withheld/insufficient metric shows its status, not a
    zero bar. A measured metric draws its value bar AND its CI whisker."""
    rendered = render_metric(rec)
    name = _esc(rec.get("name") or "metric")

    if rendered["display"] != "MEASURED":
        status = _esc(rendered["display"])
        return (
            f'<div class="metric">'
            f'<div class="metric-name">{name}</div>'
            f'<div class="metric-status">{status}</div>'
            f'<div class="metric-note">not shown as a number — status is honest, zero would be a lie</div>'
            f'</div>'
        )

    value = rendered["value"]
    lo = rendered.get("ci_lower")
    hi = rendered.get("ci_upper")
    n = rendered.get("n")

    # Bars are scaled on a 0..scale_max axis. Percent-style metrics (0..1) and
    # count-style metrics are both handled by a shared max off the value+hi.
    scale_max = max(float(hi if hi is not None else value), float(value), 1e-9)
    w = 360
    val_w = _clamp01(float(value) / scale_max) * w
    lo_x = _clamp01(float(lo) / scale_max) * w if lo is not None else None
    hi_x = _clamp01(float(hi) / scale_max) * w if hi is not None else None

    whisker = ""
    if lo_x is not None and hi_x is not None:
        whisker = (
            f'<line x1="{lo_x:.1f}" y1="9" x2="{hi_x:.1f}" y2="9" stroke="{colors["ink"]}" stroke-width="2"/>'
            f'<line x1="{lo_x:.1f}" y1="4" x2="{lo_x:.1f}" y2="14" stroke="{colors["ink"]}" stroke-width="2"/>'
            f'<line x1="{hi_x:.1f}" y1="4" x2="{hi_x:.1f}" y2="14" stroke="{colors["ink"]}" stroke-width="2"/>'
        )
    ci_text = (
        f'95% CI [{lo:g}, {hi:g}]' if lo is not None and hi is not None else "interval unavailable"
    )
    n_text = f' &middot; n={_esc(n)}' if n is not None else ""

    return (
        f'<div class="metric">'
        f'<div class="metric-name">{name}</div>'
        f'<div class="metric-value">{_esc(value)}</div>'
        f'<svg class="metric-chart" viewBox="0 0 {w} 18" width="100%" height="18" role="img" '
        f'aria-label="{name} {_esc(value)}, {ci_text}">'
        f'<rect x="0" y="6" width="{val_w:.1f}" height="6" rx="3" fill="{colors["bar"]}"/>'
        f'{whisker}'
        f'</svg>'
        f'<div class="metric-note">{ci_text}{n_text}</div>'
        f'</div>'
    )


def _cat_bar(name: str, pts: float, mx: float, colors: dict, show_name: bool = True) -> str:
    frac = _clamp01(pts / mx) if mx else 0.0
    w = 260
    name_html = f'<span class="cat-name">{_esc(name)}</span>' if show_name else ""
    return (
        f'<div class="cat-row">{name_html}'
        f'<svg viewBox="0 0 {w} 12" width="{w}" height="12">'
        f'<rect x="0" y="3" width="{w}" height="6" rx="3" fill="{colors["bar_track"]}"/>'
        f'<rect x="0" y="3" width="{frac*w:.1f}" height="6" rx="3" fill="{colors["accent"]}"/>'
        f'</svg><span class="cat-pts">{pts:g}/{mx:g}</span></div>'
    )


def _category_breakdown(view: dict, colors: dict) -> str:
    """7-category rubric breakdown. Carries the view['categories'] shape that
    dashboard.category_pillars() produces from a real AuditResult — one pillar
    section per category with its own findings, tier, and (when excluded) its
    not-measured reason, not just a points bar. Also still accepts the older
    {name: points} or [{name, points, max}] shapes for backward compatibility,
    rendering just the bar since those carry no findings to show."""
    cats = (view or {}).get("categories")
    if isinstance(cats, dict):
        bars = [_cat_bar(str(name), float(pts), 100.0, colors)
                for name, pts in cats.items()
                if isinstance(pts, (int, float))]
        if not bars:
            return ""
        return '<section class="block"><h2>Rubric breakdown</h2>' + "".join(bars) + "</section>"

    if not isinstance(cats, list):
        return ""

    sections = []
    for c in cats:
        if not isinstance(c, dict) or "name" not in c:
            continue
        name = str(c["name"])
        # Rich pillar shape (has 'weight'/'status') vs. the older plain-points shape.
        if "weight" in c or "status" in c:
            weight = float(c.get("weight", 100) or 100)
            earned = float(c.get("earned", c.get("points", 0)) or 0)
            status = str(c.get("status") or "measured")
            tier = str(c.get("tier") or "")
            tier_badge = (
                f'<span class="badge-hypothesis">hypothesis</span>'
                if tier == "hypothesis" else ""
            )
            if status == "not_measured":
                reason = _esc(c.get("not_measured_reason") or "not measured in this pass")
                sections.append(
                    f'<div class="pillar"><div class="pillar-head">'
                    f'<span class="cat-name">{_esc(name)}</span>'
                    f'<span class="pillar-status">NOT MEASURED</span></div>'
                    f'<p class="pillar-reason">{reason} — excluded from the score, not assumed to pass.</p>'
                    f'</div>'
                )
                continue
            findings = [str(f) for f in (c.get("findings") or [])]
            findings_html = (
                "<ul class=\"pillar-findings\">"
                + "".join(f"<li>{_esc(f)}</li>" for f in findings)
                + "</ul>"
                if findings else '<p class="pillar-clean">No findings — this pillar is clean.</p>'
            )
            sections.append(
                f'<div class="pillar"><div class="pillar-head">'
                f'<span class="cat-name">{_esc(name)}</span>{tier_badge}</div>'
                + _cat_bar(name, earned, weight, colors, show_name=False)
                + findings_html
                + '</div>'
            )
        elif "points" in c:
            try:
                sections.append(_cat_bar(name, float(c["points"]), float(c.get("max", 100)), colors))
            except (TypeError, ValueError):
                continue

    if not sections:
        return ""
    return (
        '<section class="block pillars"><h2>Pillar-by-pillar findings</h2>'
        + "".join(sections)
        + "</section>"
    )


def _fix_list_block(view: dict) -> str:
    """Recommended fixes, highest-weight category first — a direct render of
    AuditResult.fix_list (audit_engine._build_fix_list), already prioritized
    and plain-language. Real content, not a placeholder section."""
    fixes = (view or {}).get("fix_list") or []
    if not fixes:
        return ""
    items = "".join(f"<li>{_esc(f)}</li>" for f in fixes)
    return f'<section class="block fixes"><h2>Recommended fixes</h2><ol>{items}</ol></section>'


def _money(n: Any) -> str:
    try:
        return "${:,.0f}".format(float(n))
    except (TypeError, ValueError):
        return _esc(n)


def _value_block(view: dict, colors: dict) -> str:
    """Value & Savings — what the client would otherwise pay a vendor stack vs the
    GEO price, with the delta as documented savings. Honest: comparison figures
    are shown as ranges (intervals), never a single fabricated number, and a
    methodology line makes clear they are published market ranges, not a quote.
    Renders only when view['value'] is present with at least an agency range."""
    v = (view or {}).get("value")
    if not isinstance(v, dict):
        return ""
    ar = v.get("agency_range")
    if not (isinstance(ar, (list, tuple)) and len(ar) == 2):
        return ""
    price = v.get("price")
    sr = v.get("savings_range")
    price_html = (
        f'<div class="val-cell"><div class="val-k">Your GEO price</div>'
        f'<div class="val-v">{_money(price)}</div></div>'
        if price is not None else ""
    )
    savings_html = (
        f'<div class="val-cell save"><div class="val-k">Documented savings</div>'
        f'<div class="val-v">{_money(sr[0])} – {_money(sr[1])}</div></div>'
        if isinstance(sr, (list, tuple)) and len(sr) == 2 else ""
    )
    note = _esc(
        v.get("note")
        or "Comparison prices are published market ranges for equivalent services, "
        "not a guarantee of any specific competing quote."
    )
    return (
        '<section class="block value"><h2>Value &amp; Savings</h2>'
        '<div class="val-grid">'
        f'<div class="val-cell"><div class="val-k">Assembled from vendors</div>'
        f'<div class="val-v">{_money(ar[0])} – {_money(ar[1])}</div></div>'
        f'{price_html}{savings_html}'
        '</div>'
        f'<p class="val-note">{note}</p></section>'
    )


def _rating_line(score: Any) -> str:
    """Plain-language tier from the score, mirroring audit_engine's own tier
    labels (Poor/Needs Work/Strong/AI-Optimized) so the cover never invents a
    rating the engine didn't already assign."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return ""
    if s >= 93:
        return "AI-Optimized"
    if s >= 75:
        return "Strong"
    if s >= 50:
        return "Needs Work"
    return "Poor"


def _cover_details_block(view: dict) -> str:
    """Section 1 of the approved outline (2026-08-16): rating summary, date,
    prepared-for line -- the at-a-glance table the header alone didn't carry."""
    score = view.get("score")
    tier = view.get("tier") or _rating_line(score)
    prepared_for = _esc(view.get("client") or "Client")
    date = _esc(view.get("report_date") or "")
    rows = []
    if tier:
        rows.append(f"<div><dt>Rating</dt><dd>{_esc(tier)}</dd></div>")
    if isinstance(score, (int, float)):
        rows.append(f"<div><dt>Score</dt><dd>{float(score):g}/100, gate {_PUBLISH_GATE}</dd></div>")
    rows.append(f"<div><dt>Prepared for</dt><dd>{prepared_for}</dd></div>")
    if date:
        rows.append(f"<div><dt>Date</dt><dd>{date}</dd></div>")
    return f'<section class="block cover"><dl class="cover-grid">{"".join(rows)}</dl></section>'


def _scope_summary_line(view: dict) -> str:
    """Extra line for the methodology/scope block: how many of the 7 rubric
    categories were actually measured vs excluded, computed from the same
    view['categories'] the pillar section renders -- not a separate claim."""
    cats = view.get("categories")
    if not isinstance(cats, list):
        return ""
    measured = [c for c in cats if isinstance(c, dict) and c.get("status") == "measured"]
    excluded = [c for c in cats if isinstance(c, dict) and c.get("status") == "not_measured"]
    if not measured and not excluded:
        return ""
    total = len(measured) + len(excluded)
    txt = f"Measured {len(measured)} of {total} rubric categories."
    if excluded:
        names = ", ".join(_esc(c.get("name", "")) for c in excluded)
        txt += f" Excluded from the score: {names}."
    return f'<p class="scope-summary">{txt}</p>'


# Compliance-checker rule prefixes map to the plain-language governing area
# they're relevant to. This is a structural-check label, not a legal
# determination -- the disclosure below says so explicitly, every render.
_GOVERNING_AREAS: tuple[tuple[str, str], ...] = (
    ("wcag-", "Accessibility (WCAG / ADA-adjacent)"),
    ("marketing-", "Marketing claim substantiation (FTC-adjacent)"),
    ("phi-", "Patient privacy & testimonial handling (HIPAA-adjacent)"),
)


def _governing_framework_block(view: dict) -> str:
    """Section 3 of the approved outline: the compliance frameworks actually
    applied, scoped to what compliance_checker.audit_site() actually checks
    today (WCAG structural subset, marketing-claim substantiation, PHI/
    testimonial handling) -- not an aspirational full legal survey. Renders
    only when the caller supplied real findings; never fabricates a governing-
    framework section out of nothing."""
    findings = view.get("compliance_findings")
    if not isinstance(findings, list) or not findings:
        return ""
    grouped: dict[str, list[dict]] = {}
    for f in findings:
        if not isinstance(f, dict):
            continue
        rule = str(f.get("rule") or "")
        area = next((label for prefix, label in _GOVERNING_AREAS if rule.startswith(prefix)), None)
        if area is None:
            continue
        grouped.setdefault(area, []).append(f)
    if not grouped:
        return ""
    sections = []
    for area, items in grouped.items():
        rows = "".join(
            f'<li><strong>{_esc(f.get("severity", "note"))}:</strong> {_esc(f.get("message", ""))}</li>'
            for f in items
        )
        sections.append(f'<div class="gov-area"><h3>{_esc(area)}</h3><ul>{rows}</ul></div>')
    return (
        '<section class="block governing"><h2>Governing framework</h2>'
        '<p class="gov-disclosure">Structural findings only -- this is a rules-based scan of the '
        'page, not a legal compliance determination. Consult qualified counsel before treating any '
        'finding below as establishing or refuting regulatory compliance.</p>'
        + "".join(sections)
        + "</section>"
    )


def _cross_reference_block(view: dict) -> str:
    """Section 5 of the approved outline: comparing marketing claims against
    the business's own materials/disclosures. No pipeline exists today to
    ingest a business's own documentation, so this renders as an explicit
    not-yet-available section -- never fabricated findings against materials
    nobody supplied."""
    if not view.get("own_materials_provided"):
        return (
            '<section class="block not-available"><h2>Cross-reference against your own materials</h2>'
            '<p class="not-available-note">Not yet available: GEO does not currently ingest a '
            "business's own consent forms, disclosures, or documentation to check for "
            "self-contradiction against the live site. This section will populate once that "
            "intake exists.</p></section>"
        )
    return ""


def _evidence_attribution_block(view: dict) -> str:
    """Section 6 of the approved outline (from the lawyer memo's supplement,
    new relative to the main memo): whether a cited claim's attribution can
    rescue it. Explicitly noted in the approved outline as populating only
    once real citations exist past draft -- blocked on citation-rigor Phase 2
    (the lawyer relationship), not on any engineering work here."""
    citations = view.get("citation_records")
    if not isinstance(citations, list) or not citations:
        return (
            '<section class="block not-available"><h2>Evidence-attribution triage</h2>'
            '<p class="not-available-note">Not yet available: this section populates once real, '
            "lawyer-reviewed citation records exist past draft (citation-rigor Phase 2, blocked on "
            "the lawyer relationship, not engineering work). No claims are triaged here until then."
            "</p></section>"
        )
    rows = "".join(
        f'<li>{_esc(c.get("claim", ""))} — {_esc(c.get("attribution_status", "unresolved"))}</li>'
        for c in citations if isinstance(c, dict)
    )
    return f'<section class="block"><h2>Evidence-attribution triage</h2><ul>{rows}</ul></section>'


def _competitor_block(view: dict, colors: dict) -> str:
    """Section 7 of the approved outline: competitor/benchmark comparison.
    Renders only when the caller supplies real competitor scores -- there is
    no automatic per-request competitor-audit pipeline today, so this stays
    absent by default rather than inventing a comparison, the same pattern
    _value_block already uses for its own optional section."""
    competitors = view.get("competitors")
    if not isinstance(competitors, list) or not competitors:
        return ""
    rows = []
    for comp in competitors:
        if not isinstance(comp, dict) or "name" not in comp or "score" not in comp:
            continue
        try:
            score = float(comp["score"])
        except (TypeError, ValueError):
            continue
        rows.append(_cat_bar(str(comp["name"]), score, 100.0, colors))
    if not rows:
        return ""
    return (
        '<section class="block"><h2>Competitor comparison</h2>'
        '<p class="scope-summary">Real scores from the same rubric, same publish gate.</p>'
        + "".join(rows)
        + "</section>"
    )


_GLOSSARY: tuple[tuple[str, str], ...] = (
    ("AI-Search Readiness score", "0-100 score across the measured rubric categories; the publish gate is the minimum score treated as client-ready."),
    ("Publish gate", f"The {_PUBLISH_GATE}-point threshold a score must clear before being presented as a finished readiness claim."),
    ("Documented", "A finding backed by a cited, verifiable source or a direct structural check of the page."),
    ("Hypothesis", "A finding based on a reasonable inference where the underlying weighting or source is not yet fully cited -- flagged, not hidden."),
    ("Not measured", "A category excluded from the score because this pass didn't fetch the artifact it depends on -- never silently assumed to pass."),
    ("Confidence interval (CI)", "The range a sampled metric's true value likely falls within; a measured metric is never shown without one."),
    ("Compliance gap", "A structural-check score (WCAG, marketing-claim substantiation, PHI/testimonial handling) -- not a legal compliance determination."),
)


def _glossary_block() -> str:
    """Section 10 of the approved outline. Pure definitions of terms already
    used elsewhere in this document -- no claim about the audited business,
    so nothing here needs a real data source."""
    rows = "".join(f"<div><dt>{_esc(term)}</dt><dd>{_esc(defn)}</dd></div>" for term, defn in _GLOSSARY)
    return f'<section class="block glossary"><h2>Glossary</h2><dl>{rows}</dl></section>'


def _limitations_block(view: dict) -> str:
    lims = (view or {}).get("limitations") or []
    items = "".join(f"<li>{_esc(x)}</li>" for x in lims)
    return f'<section class="block limitations"><h2>Limitations</h2><ul>{items}</ul></section>'


def _methodology_block(view: dict, colors: dict) -> str:
    meth = (view or {}).get("methodology") or {}
    badge = ""
    if str(meth.get("weights_status") or "").upper() == "UNVALIDATED":
        badge = '<span class="badge-unvalidated">weights: UNVALIDATED</span>'
    rows = "".join(
        f"<div><dt>{_esc(k)}</dt><dd>{_esc(v)}</dd></div>"
        for k, v in meth.items()
        if k != "weights_status"
    )
    return (
        f'<section class="block methodology"><h2>Scope &amp; methodology {badge}</h2>'
        f'{_scope_summary_line(view)}'
        f'<dl>{rows}</dl></section>'
    )


def render_report_html(view: dict, branding: dict | None = None) -> str:
    """Render a branded, charted, print-ready HTML report from a report view.

    Refuses to render a dishonest view: _assert_exportable runs first, so a view
    with no limitations block or a measured metric missing its interval raises,
    exactly as the JSON/text exporters do. Honesty travels to every format.
    """
    _assert_exportable(view)
    view = view or {}
    colors = _colors(branding)
    brand = (view.get("branding") or (branding or {}))
    client_name = _esc(view.get("client") or brand.get("domain") or "Client")
    window = view.get("window") or {}
    window_txt = _esc(
        f'{window.get("start", "")} - {window.get("end", "")}'.strip(" -")
        or window.get("label")
        or ""
    )
    logo = brand.get("logo")
    logo_html = f'<img class="logo" src="{_esc(logo)}" alt="{client_name} logo"/>' if logo else ""

    # Optional headline score gauge.
    score = view.get("score")
    gauge_html = ""
    if isinstance(score, (int, float)):
        passed = float(score) >= _PUBLISH_GATE
        verdict = "clears the publish gate" if passed else f"below the {_PUBLISH_GATE:g}-point publish gate"
        gauge_html = (
            f'<section class="block score"><h2>AI-Search Readiness</h2>'
            f'<div class="score-num">{float(score):g}<span>/100</span></div>'
            f'{_score_gauge(float(score), colors)}'
            f'<div class="metric-note">{verdict}</div></section>'
        )

    metric_rows = "".join(_metric_bar(m, colors) for m in _metrics_items(view))
    metrics_html = (
        f'<section class="block"><h2>Metrics</h2>{metric_rows}</section>' if metric_rows else ""
    )

    css = f"""
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      color: {colors['ink']}; background: {colors['surface']}; margin: 0; }}
    .report {{ max-width: 720px; margin: 0 auto; padding: 32px 28px; }}
    header.brand {{ display: flex; align-items: center; gap: 14px;
      border-bottom: 3px solid {colors['accent']}; padding-bottom: 14px; margin-bottom: 8px; }}
    .logo {{ height: 40px; width: auto; }}
    header.brand h1 {{ font-size: 20px; margin: 0; }}
    header.brand .window {{ color: {colors['muted']}; font-size: 13px; margin-top: 2px; }}
    .block {{ padding: 18px 0; border-bottom: 1px solid {colors['line']}; }}
    .block h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: .04em;
      color: {colors['muted']}; margin: 0 0 12px; }}
    .score-num {{ font-size: 40px; font-weight: 700; line-height: 1; }}
    .score-num span {{ font-size: 18px; color: {colors['muted']}; font-weight: 400; }}
    .metric {{ margin-bottom: 14px; }}
    .metric-name {{ font-size: 13px; font-weight: 600; }}
    .metric-value {{ font-size: 18px; font-weight: 700; }}
    .metric-status {{ font-size: 15px; font-weight: 700; color: {colors['gate']}; }}
    .metric-note {{ font-size: 11px; color: {colors['muted']}; margin-top: 2px; }}
    .cat-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; font-size: 12px; }}
    .cat-name {{ width: 110px; font-weight: 600; }} .cat-pts {{ color: {colors['muted']}; }}
    .pillar {{ margin-bottom: 18px; padding-bottom: 4px; }}
    .pillar-head {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
    .pillar-status {{ font-size: 10px; font-weight: 700; color: {colors['gate']}; letter-spacing: .04em; }}
    .pillar-reason {{ font-size: 12px; color: {colors['muted']}; margin: 4px 0 0; }}
    .pillar-findings {{ margin: 8px 0 0; padding-left: 18px; font-size: 12px; }}
    .pillar-findings li {{ margin-bottom: 4px; }}
    .pillar-clean {{ font-size: 12px; color: {colors['muted']}; margin: 8px 0 0; }}
    .badge-hypothesis {{ display: inline-block; background: {colors['bar_track']}; color: {colors['muted']};
      font-size: 9px; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; letter-spacing: .04em; }}
    .fixes ol {{ margin: 0; padding-left: 18px; font-size: 12px; }}
    .fixes li {{ margin-bottom: 6px; }}
    .limitations li {{ font-size: 12px; color: {colors['muted']}; margin-bottom: 4px; }}
    .methodology dl {{ margin: 0; }} .methodology dt {{ font-size: 12px; font-weight: 600; }}
    .methodology dd {{ font-size: 12px; color: {colors['muted']}; margin: 0 0 8px; }}
    .badge-unvalidated {{ display: inline-block; background: {colors['gate']}; color: #fff;
      font-size: 10px; padding: 2px 6px; border-radius: 4px; vertical-align: middle;
      text-transform: none; letter-spacing: 0; margin-left: 8px; }}
    .val-grid {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .val-cell {{ flex: 1; min-width: 150px; border: 1px solid {colors['line']};
      border-radius: 10px; padding: 14px 16px; }}
    .val-cell.save {{ border-color: {colors['accent']}; }}
    .val-k {{ font-size: 10px; text-transform: uppercase; letter-spacing: .06em; color: {colors['muted']}; }}
    .val-v {{ font-size: 22px; font-weight: 700; margin-top: 6px; font-variant-numeric: tabular-nums; }}
    .val-cell.save .val-v {{ color: {colors['accent']}; }}
    .val-note {{ font-size: 11px; color: {colors['muted']}; margin-top: 10px; }}
    .cover-grid {{ display: flex; gap: 20px; flex-wrap: wrap; margin: 0; }}
    .cover-grid dt {{ font-size: 10px; text-transform: uppercase; letter-spacing: .06em; color: {colors['muted']}; }}
    .cover-grid dd {{ font-size: 14px; font-weight: 600; margin: 2px 0 0; }}
    .scope-summary {{ font-size: 12px; color: {colors['muted']}; margin: 0 0 10px; }}
    .governing .gov-disclosure {{ font-size: 11px; color: {colors['muted']}; margin: 0 0 12px;
      font-style: italic; }}
    .gov-area {{ margin-bottom: 12px; }}
    .gov-area h3 {{ font-size: 12px; margin: 0 0 4px; }}
    .gov-area ul {{ margin: 0; padding-left: 18px; font-size: 12px; }}
    .not-available {{ background: {colors['bar_track']}; border-radius: 8px; padding: 14px 16px; }}
    .not-available-note {{ font-size: 12px; color: {colors['muted']}; margin: 0; }}
    .glossary dl {{ margin: 0; }} .glossary dt {{ font-size: 12px; font-weight: 600; margin-top: 8px; }}
    .glossary dd {{ font-size: 12px; color: {colors['muted']}; margin: 2px 0 0; }}
    @media print {{ .report {{ max-width: none; }} .block {{ break-inside: avoid; }} }}
    """

    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"/>"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
        f"<title>{client_name} — AI-Search Readiness Report</title>"
        f"<style>{css}</style></head><body><main class=\"report\">"
        f'<header class="brand">{logo_html}<div><h1>{client_name}</h1>'
        f'<div class="window">AI-Search Readiness Report{" · " + window_txt if window_txt else ""}</div>'
        f"</div></header>"
        # Section order follows the approved outline (2026-08-16, built against
        # the real lawyer-memo structure): cover/rating -> scope & methodology
        # -> governing framework -> pillar findings -> cross-reference ->
        # evidence-attribution triage -> competitor comparison -> fix roadmap
        # -> value/ROI -> glossary. limitations always renders last, per the
        # non-negotiable honesty rule this module has always enforced.
        f"{gauge_html}{_cover_details_block(view)}"
        f"{_methodology_block(view, colors)}"
        f"{_governing_framework_block(view)}"
        f"{metrics_html}"
        f"{_category_breakdown(view, colors)}"
        f"{_cross_reference_block(view)}"
        f"{_evidence_attribution_block(view)}"
        f"{_competitor_block(view, colors)}"
        f"{_fix_list_block(view)}"
        f"{_value_block(view, colors)}"
        f"{_glossary_block()}"
        f"{_limitations_block(view)}"
        "</main></body></html>"
    )
