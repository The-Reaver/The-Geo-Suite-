# SPEC: SPEC_CCC_M4_ECOSYSTEM_FOOTPRINT
"""UNVALIDATED ecosystem weight seeds."""
from __future__ import annotations

from typing import Any

_SEED: dict[str, dict[str, Any]] = {
    "eco.base.CONSENSUS_CRITICAL": {"value": 40.0, "status": "UNVALIDATED"},
    "eco.base.COMMUNITY_INFLUENTIAL": {"value": 30.0, "status": "UNVALIDATED"},
    "eco.base.NICHE_DIRECTORY": {"value": 25.0, "status": "UNVALIDATED"},
    "eco.base.MEDIA_AUTHORITY": {"value": 20.0, "status": "UNVALIDATED"},
    "eco.base.GENERAL": {"value": 5.0, "status": "UNVALIDATED"},
    "eco.health.exists": {"value": 20.0, "status": "UNVALIDATED"},
    "eco.health.claimed": {"value": 15.0, "status": "UNVALIDATED"},
    "eco.health.reviews_10": {"value": 15.0, "status": "UNVALIDATED"},
    "eco.health.rating_4": {"value": 15.0, "status": "UNVALIDATED"},
    "eco.health.activity_90": {"value": 15.0, "status": "UNVALIDATED"},
    "eco.health.structured": {"value": 10.0, "status": "UNVALIDATED"},
    "eco.health.messaging": {"value": 10.0, "status": "UNVALIDATED"},
}


def weight(key: str) -> dict[str, Any]:
    row = _SEED.get(key)
    if row is None:
        raise KeyError(f"unknown_weight_key:{key}")
    return {"key": key, "value": float(row["value"]), "status": row["status"]}
