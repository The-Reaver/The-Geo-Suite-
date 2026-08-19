# SPEC: SPEC_CCC_M2_SONAR
"""Sonar RAD-2.4 — citation gap detection and conversion opportunities.

Priority weights load from sonar_weights (UNVALIDATED seeds). A missing
engine_weight must yield UNRANKED — never a silent zero that buries a gap.
"""
from __future__ import annotations

from typing import Any

from .sonar_weights import gap_priority_weights

_EFFORT_MAP = {"low": 0.1, "medium": 0.5, "high": 0.9}


def _brand_present(row: Any) -> bool:
    if isinstance(row, bool):
        return row
    if not isinstance(row, dict):
        return bool(row)
    for key in ("brand_cited", "present", "cited"):
        if key in row:
            return bool(row[key])
    return False


def _competitor_counts(row: Any) -> tuple[int, int]:
    if not isinstance(row, dict):
        return (0, 0)
    present = row.get("competitors_present", row.get("present", 0))
    if isinstance(present, list):
        present_n = len(present)
    else:
        present_n = int(present or 0)
    tracked = row.get("competitors_tracked", row.get("tracked", present_n))
    tracked_n = int(tracked or 0)
    if tracked_n < present_n:
        tracked_n = present_n
    return present_n, tracked_n


def detect_citation_gaps(
    ecosystem_matrix: dict,
    competitor_matrix: dict,
) -> list[dict]:
    """Platforms where competitors appear but the brand does not.

    ecosystem_matrix keys are platform ids; values are bool or
    {brand_cited|present|cited: bool, engine?: str}.
    competitor_matrix values are {competitors_present, competitors_tracked}.
    """
    eco = ecosystem_matrix or {}
    comp = competitor_matrix or {}
    gaps: list[dict] = []
    platforms = sorted(set(eco) | set(comp))
    for platform in platforms:
        brand_ok = _brand_present(eco.get(platform, False))
        present_n, tracked_n = _competitor_counts(comp.get(platform, {}))
        if brand_ok or present_n <= 0:
            continue
        engine = None
        eco_row = eco.get(platform)
        if isinstance(eco_row, dict):
            engine = eco_row.get("engine")
        gaps.append({
            "platform": platform,
            "engine": engine,
            "brand_cited": False,
            "competitors_present": present_n,
            "competitors_tracked": tracked_n,
            "gap_type": "competitor_present_brand_absent",
            "reason": "competitors cited on platform where brand is absent",
        })
    return gaps


def score_gap_priority(
    gap: dict,
    *,
    engine_weights: dict,
    sov_deficit: float,
    effort: str,
) -> dict:
    """F5 priority score. Missing engine_weight → priority UNRANKED."""
    platform = (gap or {}).get("platform")
    engine = (gap or {}).get("engine")
    weights_payload = gap_priority_weights()
    a = weights_payload["weights"]["a"]
    b = weights_payload["weights"]["b"]
    c = weights_payload["weights"]["c"]
    d = weights_payload["weights"]["d"]

    tracked = int((gap or {}).get("competitors_tracked") or 0)
    present = int((gap or {}).get("competitors_present") or 0)
    if tracked <= 0:
        competitor_presence = 0.0
    else:
        competitor_presence = max(0.0, min(1.0, present / tracked))

    # Resolve weight: exact platform key, then engine:platform, then engine.
    ew_raw = None
    lookup_keys = [platform, f"{engine}:{platform}" if engine else None, engine]
    for key in lookup_keys:
        if key is None:
            continue
        if key in (engine_weights or {}):
            ew_raw = engine_weights[key]
            break
        # Nested engine → platform map
        if engine and isinstance((engine_weights or {}).get(engine), dict):
            nested = engine_weights[engine]
            if platform in nested:
                ew_raw = nested[platform]
                break

    if ew_raw is None:
        return {
            "platform": platform,
            "priority": "UNRANKED",
            "score": None,
            "reason": "missing engine_weight in registry",
            "weights_status": weights_payload["status"],
            "components": {
                "competitor_presence": competitor_presence,
                "engine_weight": None,
                "sov_deficit": max(0.0, min(1.0, float(sov_deficit))),
                "effort": effort,
            },
        }

    engine_weight = max(0.0, min(1.0, float(ew_raw)))
    sov = max(0.0, min(1.0, float(sov_deficit)))
    effort_key = (effort or "").strip().lower()
    if effort_key not in _EFFORT_MAP:
        raise ValueError(f"unknown_effort:{effort}")
    effort_v = _EFFORT_MAP[effort_key]

    score = 100.0 * (
        a * competitor_presence
        + b * engine_weight
        + c * sov
        + d * (1.0 - effort_v)
    )
    return {
        "platform": platform,
        "priority": round(score, 6),
        "score": round(score, 6),
        "reason": "gap_priority_scored",
        "weights_status": weights_payload["status"],
        "components": {
            "competitor_presence": competitor_presence,
            "engine_weight": engine_weight,
            "sov_deficit": sov,
            "effort": effort_key,
            "effort_value": effort_v,
            "a": a,
            "b": b,
            "c": c,
            "d": d,
        },
    }


def find_conversion_opportunities(classified: dict) -> list[dict]:
    """RAD-2.4.4: mentioned, not cited, with third-party sources in play."""
    classified = classified or {}
    citations = classified.get("citations") or []
    mentions = classified.get("mentions") or []
    sources = (
        classified.get("third_party_sources")
        or classified.get("sources")
        or []
    )
    if citations or not mentions or not sources:
        return []

    opportunities: list[dict] = []
    for src in sources:
        url = src if isinstance(src, str) else (src or {}).get("url", "")
        if not url:
            continue
        opportunities.append({
            "opportunity_type": "mention_without_citation",
            "third_party_source": url,
            "mention_count": len(mentions),
            "reason": (
                "brand mentioned but not cited; third-party page could carry a link"
            ),
            "roi_class": "highest",
        })
    return opportunities
