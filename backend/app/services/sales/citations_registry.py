# SPEC: SPEC_CCC_SALES_DISCOVERY
"""Sales discovery citations registry — withhold unsourced stats.

Every claim must have a resolvable URL before it may be shown to a prospect.
Entries without a URL render as withheld (AGENTS.md no-fabrication).
"""
from __future__ import annotations

from typing import Any

# Bracket refs from the blueprint that have NO reference list in-repo.
# Until Oluwole resolves each to a primary URL, url stays None → withheld.
_CLAIMS: dict[str, dict[str, Any]] = {
    "ai_local_discovery_share": {
        "text": "share of consumers using AI to find local businesses",
        "url": None,
        "status": "UNSOURCED",
    },
    "local_business_invisible_share": {
        "text": "share of local businesses invisible to AI answers",
        "url": None,
        "status": "UNSOURCED",
    },
    "near_me_visit_24h_share": {
        "text": "share of near-me searches leading to a visit within 24 hours",
        "url": None,
        "status": "UNSOURCED",
    },
}


def get_claim(key: str) -> dict[str, Any]:
    row = _CLAIMS.get(key)
    if row is None:
        return {
            "key": key,
            "status": "UNKNOWN_CLAIM",
            "display": None,
            "reason": "claim not in citations registry",
        }
    if not row.get("url"):
        return {
            "key": key,
            "status": "WITHHELD",
            "display": None,
            "text": row.get("text"),
            "reason": "statistic withheld: no resolvable primary URL",
        }
    return {
        "key": key,
        "status": "OK",
        "display": row.get("text"),
        "url": row["url"],
        "reason": "sourced",
    }


def render_stat(key: str) -> dict[str, Any]:
    """Prospect-facing render: blank + warning when unsourced."""
    claim = get_claim(key)
    if claim.get("status") != "OK":
        return {
            "shown": False,
            "value": None,
            "flag": claim.get("status"),
            "reason": claim.get("reason"),
        }
    return {
        "shown": True,
        "value": claim.get("display"),
        "url": claim.get("url"),
        "flag": None,
        "reason": "sourced",
    }
