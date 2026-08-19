# SPEC: SPEC_CCC_M2_SONAR
"""Sonar weight loader — seeds from SOURCE_WEIGHT_REGISTRY, always tagged.

Product scorers must call these helpers instead of embedding literals.
Every value ships as UNVALIDATED until Track D promotes a row.
"""
from __future__ import annotations

from typing import Any

# Machine twin of docs/SOURCE_WEIGHT_REGISTRY.md scoring-coefficient table.
# Status is part of the return value so callers cannot silently treat seeds
# as settled. Do not promote a row here without a dated Track D run log.
_SEED: dict[str, dict[str, Any]] = {
    "sonar.w_c": {"value": 2.0, "status": "UNVALIDATED"},
    "sonar.csi.w1": {"value": 0.40, "status": "UNVALIDATED"},
    "sonar.csi.w2": {"value": 0.30, "status": "UNVALIDATED"},
    "sonar.csi.w3": {"value": 0.15, "status": "UNVALIDATED"},
    "sonar.csi.w4": {"value": 0.15, "status": "UNVALIDATED"},
    "sonar.gap.a": {"value": 0.30, "status": "UNVALIDATED"},
    "sonar.gap.b": {"value": 0.30, "status": "UNVALIDATED"},
    "sonar.gap.c": {"value": 0.25, "status": "UNVALIDATED"},
    "sonar.gap.d": {"value": 0.15, "status": "UNVALIDATED"},
}


def weight(key: str) -> dict[str, Any]:
    """Return {key, value, status} or raise KeyError for unknown keys."""
    row = _SEED.get(key)
    if row is None:
        raise KeyError(f"unknown_weight_key:{key}")
    return {"key": key, "value": float(row["value"]), "status": row["status"]}


def citation_weight() -> dict[str, Any]:
    return weight("sonar.w_c")


def csi_weights() -> dict[str, Any]:
    """Return CSI component weights with aggregate status."""
    parts = [weight(f"sonar.csi.w{i}") for i in (1, 2, 3, 4)]
    values = {
        "consistency": parts[0]["value"],
        "longitudinal": parts[1]["value"],
        "diversity": parts[2]["value"],
        "freshness": parts[3]["value"],
    }
    statuses = {p["status"] for p in parts}
    status = "UNVALIDATED" if "UNVALIDATED" in statuses else next(iter(statuses))
    return {"weights": values, "status": status, "keys": [p["key"] for p in parts]}


def gap_priority_weights() -> dict[str, Any]:
    """Return gap-priority coefficients a..d with aggregate status."""
    parts = [weight(f"sonar.gap.{k}") for k in ("a", "b", "c", "d")]
    values = {
        "a": parts[0]["value"],
        "b": parts[1]["value"],
        "c": parts[2]["value"],
        "d": parts[3]["value"],
    }
    statuses = {p["status"] for p in parts}
    status = "UNVALIDATED" if "UNVALIDATED" in statuses else next(iter(statuses))
    return {"weights": values, "status": status, "keys": [p["key"] for p in parts]}
