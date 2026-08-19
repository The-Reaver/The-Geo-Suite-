# SPEC: SPEC_CCC_M8_REPORTING
"""Interval-separation alert gate (Base path B-2).

No scores invented. Suppresses drop alerts when Wilson (or supplied)
intervals overlap — honest insufficient-sample.
"""
from __future__ import annotations

from typing import Any


def intervals_overlap(a_lo: float, a_hi: float, b_lo: float, b_hi: float) -> bool:
    """True when [a_lo, a_hi] and [b_lo, b_hi] share any point."""
    return not (a_hi < b_lo or b_hi < a_lo)


def evaluate_sov_drop_alert(
    *,
    prev_point: float,
    curr_point: float,
    prev_ci: tuple[float, float],
    curr_ci: tuple[float, float],
    drop_pp_threshold: float = 10.0,
) -> dict[str, Any]:
    """Decide whether a SOV drop alert may fire.

    Base path: even if the point estimate drops by ≥ threshold pp, overlapping
    CIs mean we cannot distinguish from noise.
    """
    drop_pp = (prev_point - curr_point) * 100.0
    if drop_pp < drop_pp_threshold:
        return {
            "fire": False,
            "reason": "below_threshold",
            "drop_pp": drop_pp,
        }
    if intervals_overlap(prev_ci[0], prev_ci[1], curr_ci[0], curr_ci[1]):
        return {
            "fire": False,
            "reason": "insufficient_sample",
            "message": (
                "insufficient sample — cannot distinguish from noise"
            ),
            "drop_pp": drop_pp,
            "prev_ci": list(prev_ci),
            "curr_ci": list(curr_ci),
        }
    return {
        "fire": True,
        "reason": "interval_separated_drop",
        "drop_pp": drop_pp,
        "prev_ci": list(prev_ci),
        "curr_ci": list(curr_ci),
    }
