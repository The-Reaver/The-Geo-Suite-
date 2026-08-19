# SPEC: SPEC_CCC_M2_SONAR
"""Sonar visibility metrics — SOV, Wilson CI, CSI (UNVALIDATED seeds).

Formulas from SPEC_CCC_M2_SONAR Deliverable 2. Weights load via sonar_weights;
never treat status as VALIDATED without Track D.
"""
from __future__ import annotations

from typing import Any

from .sonar_weights import citation_weight, csi_weights


def citation_ratio(citations: int, mentions: int) -> float | None:
    total = citations + mentions
    if total == 0:
        return None
    return citations / total


def wilson_interval(
    successes: int, n: int, *, z: float = 1.96
) -> tuple[float, float] | None:
    """Wilson score interval for a proportion. NULL when n < 5."""
    if n < 5:
        return None
    if successes < 0 or successes > n:
        raise ValueError("successes must be in [0, n]")
    phat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (phat + z2 / (2 * n)) / denom
    margin = (z * ((phat * (1.0 - phat) / n + z2 / (4 * n * n)) ** 0.5)) / denom
    lo = max(0.0, centre - margin)
    hi = min(1.0, centre + margin)
    return (lo, hi)


def share_of_voice(
    brand_counts: dict[str, dict[str, int]],
    *,
    citation_weight_override: float | None = None,
) -> dict[str, Any]:
    """SOV_b = (w_c·C_b + M_b) / Σ_i (w_c·C_i + M_i).

    brand_counts values: {"citations": int, "mentions": int} (also accepts
    short keys c/m). Denominator zero → shares NULL with a named reason.
    """
    w_meta = citation_weight()
    w_c = (
        float(citation_weight_override)
        if citation_weight_override is not None
        else float(w_meta["value"])
    )
    scores: dict[str, float] = {}
    for brand, counts in (brand_counts or {}).items():
        c = int(counts.get("citations", counts.get("c", 0)) or 0)
        m = int(counts.get("mentions", counts.get("m", 0)) or 0)
        scores[brand] = w_c * c + m
    denom = sum(scores.values())
    if denom <= 0:
        return {
            "shares": None,
            "w_c": w_c,
            "weights_status": w_meta["status"],
            "weight_key": w_meta["key"],
            "reason": "no brand referenced in tracked responses",
        }
    shares = {b: scores[b] / denom for b in scores}
    return {
        "shares": shares,
        "w_c": w_c,
        "weights_status": w_meta["status"],
        "weight_key": w_meta["key"],
        "reason": "ok",
    }


def citation_stability_index(
    consistency: float | None,
    longitudinal: float | None,
    diversity: float | None,
    freshness: float | None,
    *,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """CSI = 100 · Σ w_i·component_i with renormalisation when a component is NULL.

    Returns NULL CSI when fewer than two components are measurable.
    sigma_max / freshness curve are caller-supplied — not invented here.
    """
    w_pack = csi_weights()
    base = weights or w_pack["weights"]
    components = {
        "consistency": consistency,
        "longitudinal": longitudinal,
        "diversity": diversity,
        "freshness": freshness,
    }
    usable = {k: v for k, v in components.items() if v is not None}
    if len(usable) < 2:
        return {
            "csi": None,
            "weights_status": w_pack["status"],
            "reason": "fewer than two measurable CSI components",
            "components_used": list(usable.keys()),
        }
    raw_w = {k: float(base[k]) for k in usable}
    w_sum = sum(raw_w.values())
    if w_sum <= 0:
        return {
            "csi": None,
            "weights_status": w_pack["status"],
            "reason": "CSI weight sum is zero after exclusion",
            "components_used": list(usable.keys()),
        }
    renorm = {k: raw_w[k] / w_sum for k in raw_w}
    score = 100.0 * sum(renorm[k] * float(usable[k]) for k in usable)
    return {
        "csi": score,
        "weights_used": renorm,
        "weights_status": w_pack["status"],
        "reason": "ok",
        "components_used": list(usable.keys()),
    }


def package_proportion(
    successes: int,
    n: int,
    *,
    label: str,
) -> dict[str, Any]:
    """Client-facing proportion payload with mandatory Wilson CI + n."""
    if n < 5:
        return {
            "label": label,
            "point": None,
            "ci95": None,
            "n": n,
            "reason": "insufficient_sampling",
            "weights_status": "UNVALIDATED",
        }
    point = successes / n
    ci = wilson_interval(successes, n)
    return {
        "label": label,
        "point": point,
        "ci95": list(ci) if ci else None,
        "n": n,
        "reason": "ok",
        "weights_status": "UNVALIDATED",
    }
