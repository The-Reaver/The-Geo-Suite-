# SPEC: SPEC_CCC_M3_CITATION_INFLUENCE
"""CII / FDS weight loader — seeds UNVALIDATED until Track A/D."""
from __future__ import annotations

from typing import Any

_SEED: dict[str, dict[str, Any]] = {
    "cii.w.topical_relevance": {"value": 0.35, "status": "UNVALIDATED"},
    "cii.w.pricing_presence": {"value": 0.20, "status": "UNVALIDATED"},
    "cii.w.freshness": {"value": 0.20, "status": "UNVALIDATED"},
    "cii.w.trust_cues": {"value": 0.15, "status": "UNVALIDATED"},
    "cii.w.schema_fds": {"value": 0.10, "status": "UNVALIDATED"},
    "fds.award.price": {"value": 20.0, "status": "UNVALIDATED"},
    "fds.award.aggregateRating": {"value": 15.0, "status": "UNVALIDATED"},
    "fds.award.specifications": {"value": 15.0, "status": "UNVALIDATED"},
    "fds.award.review_count": {"value": 10.0, "status": "UNVALIDATED"},
    "fds.award.availability": {"value": 10.0, "status": "UNVALIDATED"},
    "fds.award.faq": {"value": 10.0, "status": "UNVALIDATED"},
    "fds.award.credentials": {"value": 10.0, "status": "UNVALIDATED"},
    "fds.award.date": {"value": 10.0, "status": "UNVALIDATED"},
    "fds.penalty.empty_property": {"value": 10.0, "status": "UNVALIDATED"},
    "fds.penalty.generic_organization": {"value": 15.0, "status": "UNVALIDATED"},
    "fds.threshold.payload": {"value": 50.0, "status": "UNVALIDATED"},
    "authority.dr_threshold": {"value": 60.0, "status": "UNVALIDATED"},
}


def weight(key: str) -> dict[str, Any]:
    row = _SEED.get(key)
    if row is None:
        raise KeyError(f"unknown_weight_key:{key}")
    return {"key": key, "value": float(row["value"]), "status": row["status"]}


def cii_component_weights() -> dict[str, Any]:
    keys = (
        "topical_relevance",
        "pricing_presence",
        "freshness",
        "trust_cues",
        "schema_fds",
    )
    parts = [weight(f"cii.w.{k}") for k in keys]
    values = {k: parts[i]["value"] for i, k in enumerate(keys)}
    status = "UNVALIDATED" if any(p["status"] == "UNVALIDATED" for p in parts) else "VALIDATED"
    return {"weights": values, "status": status}
