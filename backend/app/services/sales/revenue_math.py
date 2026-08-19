# SPEC: SPEC_CCC_SALES_DISCOVERY
"""Lost-revenue estimate as an interval — never a bare point."""
from __future__ import annotations

from typing import Any


def _interval(val: Any, name: str) -> tuple[float, float] | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        v = float(val)
        return (v, v)
    if isinstance(val, (list, tuple)) and len(val) == 2:
        return (float(val[0]), float(val[1]))
    if isinstance(val, dict) and "lo" in val and "hi" in val:
        return (float(val["lo"]), float(val["hi"]))
    raise ValueError(f"bad_interval:{name}")


def estimate_lost_revenue(inputs: dict, *, benchmarks: dict) -> dict:
    """F1 — interval lost revenue. Missing sourced benchmark → INSUFFICIENT_BENCHMARKS."""
    required = ("S", "a", "c", "t")
    missing = [k for k in required if k not in (benchmarks or {})]
    if missing:
        return {
            "status": "INSUFFICIENT_BENCHMARKS",
            "lost_lo": None,
            "lost_hi": None,
            "reason": f"missing benchmark terms: {', '.join(missing)}",
            "missing": missing,
        }

    intervals: dict[str, tuple[float, float]] = {}
    for k in required:
        iv = _interval(benchmarks[k], k)
        if iv is None:
            return {
                "status": "INSUFFICIENT_BENCHMARKS",
                "lost_lo": None,
                "lost_hi": None,
                "reason": f"missing benchmark terms: {k}",
                "missing": [k],
            }
        lo, hi = iv
        if lo < 0 or hi < 0 or lo > hi:
            return {
                "status": "INSUFFICIENT_BENCHMARKS",
                "lost_lo": None,
                "lost_hi": None,
                "reason": f"invalid non-negative interval for {k}",
                "missing": [k],
            }
        intervals[k] = (lo, hi)

    v = float((inputs or {}).get("v", 0.0))
    v = max(0.0, min(1.0, v))
    # lost = S·a·c·(1−v)·t
    factor = 1.0 - v
    lost_lo = (
        intervals["S"][0]
        * intervals["a"][0]
        * intervals["c"][0]
        * factor
        * intervals["t"][0]
    )
    lost_hi = (
        intervals["S"][1]
        * intervals["a"][1]
        * intervals["c"][1]
        * factor
        * intervals["t"][1]
    )
    return {
        "status": "OK",
        "lost_lo": lost_lo,
        "lost_hi": lost_hi,
        "v": v,
        "assumptions": {
            "S": intervals["S"],
            "a": intervals["a"],
            "c": intervals["c"],
            "t": intervals["t"],
            "label": "national/metro benchmark intervals — approximate for local clinic",
        },
        "reason": "interval estimate; not a measurement of actual loss",
        "display_hint": "show lower bound as 'at least' when space for one number",
    }
