# SPEC: SPEC_CCC_M8_REPORTING
"""Metric records that refuse naked numbers — CI enforcement for sampled metrics."""
from __future__ import annotations

from typing import Any

SAMPLED = "sampled"
POINT = "point"

FORBIDDEN_CAUSAL = (
    "root cause",
    "caused by",
    "because competitor",
    "granger-causes",
    "attributed to",
    "drove the drop",
    "led to the decline",
)


def metric_record(
    *,
    value: float | None,
    ci_lower: float | None,
    ci_upper: float | None,
    n: int | None,
    measured_at: str,
    source_module: str,
    status: str,
    limitations: list[str],
    kind: str = SAMPLED,
    name: str = "metric",
) -> dict:
    return {
        "name": name,
        "value": value,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "n": n,
        "measured_at": measured_at,
        "source_module": source_module,
        "status": status,
        "limitations": list(limitations or []),
        "kind": kind,
    }


def render_metric(record: dict) -> dict:
    """Refuse sampled metrics missing CI bounds."""
    record = record or {}
    name = record.get("name") or "metric"
    status = record.get("status")
    if status in ("INSUFFICIENT_DATA", "NOT_MEASURED", "UNAVAILABLE"):
        return {
            "display": status,
            "value": None,
            "status": status,
            "reason": f"status {status} is not rendered as 0",
        }
    if record.get("kind", SAMPLED) == SAMPLED:
        if record.get("ci_lower") is None or record.get("ci_upper") is None:
            raise ValueError(f"sampled metric '{name}' missing ci_lower/ci_upper")
    return {
        "display": "MEASURED",
        "value": record.get("value"),
        "ci_lower": record.get("ci_lower"),
        "ci_upper": record.get("ci_upper"),
        "n": record.get("n"),
        "status": "MEASURED",
        "reason": "rendered with interval",
    }


def executive_summary(client: dict, window: dict) -> dict:
    """RPT-8.1.1 without M5 attribution panels."""
    metrics = (client or {}).get("metrics") or {}
    payload = {
        "client": (client or {}).get("name"),
        "window": window,
        "metrics": metrics,
        "panels": ["visibility", "engines", "competitive"],
        "limitations": list((client or {}).get("limitations") or [
            "Sampled metrics describe controlled prompt sets, not all patient queries.",
        ]),
        "methodology": (client or {}).get("methodology") or {
            "show_your_work": True,
            "weights_status": "UNVALIDATED",
        },
    }
    # M5 deferred — keys must be absent, not empty.
    for banned in (
        "granger",
        "varmax",
        "attribution_waterfall",
        "roi_irf",
        "econometric_attribution",
    ):
        payload.pop(banned, None)
    return payload


def engine_breakdown(client: dict, window: dict) -> dict:
    return {
        "window": window,
        "engines": (client or {}).get("engines") or {},
        "limitations": ["Cross-engine comparison requires identical prompt text."],
    }


def competitive_view(client: dict, competitors: list[dict]) -> dict:
    return {
        "client": (client or {}).get("name"),
        "competitors": competitors or [],
        "limitations": ["Partial competitor coverage biases comparisons."],
    }


def category_pillars(result: Any) -> list[dict]:
    """Adapt a real audit_engine.AuditResult into the per-category shape
    render_html.render_report_html renders pillar-by-pillar sections from.

    This is the merge point named in the 2026-08-16 report-renderer architecture
    question: AuditResult.categories (real findings, tier, status, not-measured
    reasons) becomes view["categories"], replacing the old points-only
    {name: points} shape with one dict per pillar. No section here is invented —
    every field is a direct pass-through of what the engine already measured.
    """
    pillars: list[dict] = []
    for c in result.categories:
        pillars.append({
            "id": c.id,
            "name": c.name,
            "weight": c.weight,
            "earned": c.earned,
            "tier": c.tier,
            "status": c.status,
            "findings": list(c.findings or []),
            "not_measured_reason": c.not_measured_reason,
        })
    return pillars


def split_trend_at_model_boundary(points: list[dict]) -> list[list[dict]]:
    """Break trend into segments when model_id changes."""
    if not points:
        return []
    segments: list[list[dict]] = [[points[0]]]
    for pt in points[1:]:
        prev = segments[-1][-1]
        if pt.get("model_id") != prev.get("model_id"):
            segments.append([pt])
        else:
            segments[-1].append(pt)
    return segments
