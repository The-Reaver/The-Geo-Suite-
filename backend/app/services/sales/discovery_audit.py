# SPEC: SPEC_CCC_SALES_DISCOVERY
"""Pre-call visibility audit — orchestrates Sonar; does not re-detect citations."""
from __future__ import annotations

from typing import Any

from ..compliance.compliance_checker import DEFAULT_HIGH_RISK_TERMS
from ..sonar.multi_model import compare_engines, summarize_presence
from .citations_registry import render_stat

_PROMPT_TEMPLATES = (
    "best {service} near {city}",
    "{service} for {condition} in {city}",
    "who do you recommend for {service} in {neighborhood}",
    "{business_name} reviews",
    "{business_name} vs {competitor}",
)


def _high_risk_hit(text: str) -> str | None:
    lowered = (text or "").lower()
    for term in sorted(DEFAULT_HIGH_RISK_TERMS, key=len, reverse=True):
        if term and term.lower() in lowered:
            return term
    return None


def build_prompt_set(business: dict) -> dict:
    """Build HBOT prompts; refuse high-risk conditions before dispatch."""
    condition = (business or {}).get("condition") or ""
    hit = _high_risk_hit(condition)
    if hit:
        return {
            "ok": False,
            "prompts": [],
            "reason": f"condition refused: high-risk compliance term '{hit}'",
            "term": hit,
        }
    ctx = {
        "service": business.get("service") or "hyperbaric oxygen therapy",
        "city": business.get("city") or "the area",
        "neighborhood": business.get("neighborhood") or business.get("city") or "the area",
        "condition": condition or "wound care",
        "business_name": business.get("name") or "the clinic",
        "competitor": business.get("competitor") or "a nearby clinic",
    }
    prompts = [t.format(**ctx) for t in _PROMPT_TEMPLATES]
    return {"ok": True, "prompts": prompts, "reason": "prompts_built"}


def run_visibility_audit(
    business: dict,
    *,
    engines: list[str],
    prompt_set: list[str] | None = None,
    engine_responses: dict | None = None,
) -> dict:
    """Orchestrate Sonar over injected engine responses (offline-safe)."""
    built = build_prompt_set(business)
    if not built["ok"]:
        return {
            "status": "REFUSED",
            "verdict": "INSUFFICIENT_DATA",
            "reason": built["reason"],
            "term": built.get("term"),
            "prompts": [],
        }
    prompts = prompt_set if prompt_set is not None else built["prompts"]
    responses = engine_responses or {}
    # Missing engines count as unusable for threshold math.
    grid_input: dict[str, Any] = {}
    for eng in engines:
        if eng not in responses:
            grid_input[eng] = {"status": "UNAVAILABLE", "reason": "no response"}
        else:
            grid_input[eng] = responses[eng]
    grid = compare_engines(
        grid_input,
        brand_domains=list(business.get("domains") or []),
        brand_aliases=list(business.get("aliases") or [business.get("name") or ""]),
    )
    v = verdict({
        "ok_engines": grid.get("ok_engines", 0),
        "cited_engines": grid.get("cited_engines", 0),
        "seen_engines": grid.get("seen_engines", 0),
    })
    return {
        "status": "OK",
        "verdict": v,
        "grid": grid,
        "presence": summarize_presence(grid),
        "prompts": prompts,
        "headline_stats": {
            k: render_stat(k)
            for k in (
                "ai_local_discovery_share",
                "local_business_invisible_share",
                "near_me_visit_24h_share",
            )
        },
        "reason": "audit_complete",
    }


def verdict(audit: dict) -> str:
    ok = int(audit.get("ok_engines") or 0)
    cited = int(audit.get("cited_engines") or 0)
    seen = int(audit.get("seen_engines") or 0)
    if ok < 3:
        return "INSUFFICIENT_DATA"
    if cited >= 3:
        return "VISIBLE"
    if 1 <= cited <= 2 or (seen >= 2 and cited == 0):
        return "PARTIALLY_VISIBLE"
    if seen == 0:
        return "INVISIBLE"
    return "PARTIALLY_VISIBLE"


def competitor_panel(business: dict, competitors: list[dict]) -> dict:
    rows = []
    for c in competitors or []:
        rows.append({
            "name": c.get("name"),
            "domains": c.get("domains") or [],
            "notes": c.get("notes") or "",
        })
    return {
        "business": business.get("name"),
        "competitors": rows,
        "override_allowed": True,
        "reason": "heuristic panel; salesperson may override",
    }
