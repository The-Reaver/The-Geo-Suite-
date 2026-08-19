"""Read-only dashboard panels for M2-M4 capabilities.

Surfaces compliance findings, the ranking scorecard, and the ranked lead
pipeline. Never fabricates a score: missing HTML or an empty provider list
returns an honest empty state with a reason, not zeros dressed up as data.
"""
from __future__ import annotations

from typing import Any, Optional

from app.services.compliance.compliance_checker import audit_site
from app.services.ranking.factor_audit import audit_ranking, scorecard_markdown
from app.services.sales.lead_scorer import rank_leads


def build_compliance_panel(html: Optional[str], *, mode: str = "prospect") -> dict:
    """Compliance findings for the client dashboard.

    Empty / missing HTML -> honest empty state (no fabricated gap score).
    """
    if html is None or not str(html).strip():
        return {
            "empty": True,
            "reason": "No site HTML is available to audit for compliance",
            "mode": mode,
            "ok": None,
            "blocking": [],
            "findings": [],
            "compliance_gap_0_100": None,
        }
    result = audit_site(html, mode=mode)
    return {
        "empty": False,
        "reason": None,
        "mode": mode,
        "ok": result.get("ok"),
        "blocking": result.get("blocking") or [],
        "findings": result.get("findings") or [],
        "compliance_gap_0_100": result.get("compliance_gap_0_100"),
    }


def build_ranking_panel(html: Optional[str], *,
                        metrics: Optional[dict] = None,
                        business_name: str = "Your site") -> dict:
    """Ranking scorecard for the client dashboard."""
    if html is None or not str(html).strip():
        return {
            "empty": True,
            "reason": "No site HTML is available to score against the ranking factors",
            "overall_score": None,
            "seo_score": None,
            "geo_score": None,
            "top_gaps": [],
            "scorecard_markdown": (
                f"## Ranking scorecard — {business_name}\n\n"
                "No scorecard could be produced: no site HTML is available.\n"
            ),
        }
    result = audit_ranking(html, metrics=metrics)
    if result.get("overall_score") is None:
        return {
            "empty": True,
            "reason": result.get("error") or "Ranking audit produced no score",
            "overall_score": None,
            "seo_score": None,
            "geo_score": None,
            "top_gaps": [],
            "scorecard_markdown": scorecard_markdown(result, business_name=business_name),
        }
    return {
        "empty": False,
        "reason": None,
        "overall_score": result.get("overall_score"),
        "seo_score": result.get("seo_score"),
        "geo_score": result.get("geo_score"),
        "top_gaps": result.get("top_gaps") or [],
        "factors": result.get("factors") or [],
        "scorecard_markdown": scorecard_markdown(result, business_name=business_name),
    }


def build_lead_pipeline(providers: Optional[list],
                        audits: Optional[dict] = None) -> dict:
    """Ranked lead pipeline for the sales/admin surface."""
    if not providers:
        return {
            "empty": True,
            "reason": "No providers in the pipeline",
            "count": 0,
            "provisional_count": 0,
            "leads": [],
        }
    ranked = rank_leads(providers, audits)
    return {
        "empty": False,
        "reason": None,
        "count": len(ranked),
        "provisional_count": sum(1 for row in ranked if row.get("provisional")),
        "leads": ranked,
    }


def render_compliance_section(panel: dict) -> str:
    """HTML fragment for the client dashboard. Escapes nothing fabricated."""
    if panel.get("empty"):
        return (
            f'<section class="card" id="compliance">'
            f'<h2>Compliance</h2>'
            f'<p class="empty">{_esc(panel.get("reason") or "No compliance data.")}</p>'
            f'</section>'
        )
    findings = panel.get("findings") or []
    if findings:
        items = "".join(
            f"<li><strong>{_esc(f.get('rule', ''))}</strong>: "
            f"{_esc(f.get('message', f.get('reason', '')))}</li>"
            for f in findings[:10]
            if isinstance(f, dict)
        )
        findings_html = f"<ul>{items}</ul>"
    else:
        findings_html = "<p>No compliance findings.</p>"
    gap = panel.get("compliance_gap_0_100")
    gap_html = f"<p>Compliance gap: {gap}/100</p>" if gap is not None else ""
    status = "Compliant" if panel.get("ok") else "Findings present"
    return (
        f'<section class="card" id="compliance">'
        f'<h2>Compliance</h2>'
        f'<p class="status-badge">{status}</p>'
        f'{gap_html}'
        f'{findings_html}'
        f'</section>'
    )


def render_ranking_section(panel: dict) -> str:
    if panel.get("empty"):
        return (
            f'<section class="card" id="ranking">'
            f'<h2>Ranking scorecard</h2>'
            f'<p class="empty">{_esc(panel.get("reason") or "No ranking data.")}</p>'
            f'</section>'
        )
    gaps = panel.get("top_gaps") or []
    if gaps:
        items = "".join(
            f"<li>{_esc(g.get('label', g.get('id', '')))}: "
            f"{_esc(g.get('gap_note', g.get('note', '')))}</li>"
            if isinstance(g, dict) else f"<li>{_esc(str(g))}</li>"
            for g in gaps[:5]
        )
        gaps_html = f"<ul>{items}</ul>"
    else:
        gaps_html = "<p>No open ranking gaps.</p>"
    return (
        f'<section class="card" id="ranking">'
        f'<h2>Ranking scorecard</h2>'
        f'<div class="metric-value">{panel.get("overall_score")}</div>'
        f'<p>SEO: {panel.get("seo_score")} / GEO: {panel.get("geo_score")}</p>'
        f'<h3>Top gaps</h3>{gaps_html}'
        f'</section>'
    )


def render_lead_pipeline_html(panel: dict) -> str:
    if panel.get("empty"):
        return (
            "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
            "<title>Lead pipeline</title></head><body>"
            f"<h1>Lead pipeline</h1><p>{_esc(panel.get('reason') or 'Empty')}</p>"
            "</body></html>"
        )
    rows = []
    for lead in panel.get("leads") or []:
        rows.append(
            "<tr>"
            f"<td>{_esc(lead.get('name', ''))}</td>"
            f"<td>{lead.get('priority', '')}</td>"
            f"<td>{_esc(lead.get('tier', ''))}</td>"
            f"<td>{'provisional' if lead.get('provisional') else 'audited'}</td>"
            "</tr>"
        )
    body = (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
        "<title>Lead pipeline</title>"
        "<style>body{font-family:sans-serif;margin:2rem}table{border-collapse:collapse}"
        "td,th{border:1px solid #ccc;padding:.4rem .8rem;text-align:left}</style>"
        "</head><body>"
        f"<h1>Lead pipeline</h1>"
        f"<p>{panel.get('count')} leads "
        f"({panel.get('provisional_count')} provisional)</p>"
        "<table><thead><tr><th>Name</th><th>Priority</th><th>Tier</th>"
        "<th>Audit</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></body></html>"
    )
    return body


def _esc(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
