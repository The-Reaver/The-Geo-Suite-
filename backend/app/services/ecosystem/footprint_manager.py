"""M4 ecosystem footprint — presence detection (unweighted layer).

Presence grid + NAP consistency + shared source tagging.
Weighted backlink/health composites that need Track D stay out of the
score path except ABSENT=0 / NOT_CHECKED=NULL (observed states, not weights).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from ..platform_registry import (
    DEFAULT_HBOT_PLATFORM_IDS,
    lookup_platform,
)
from ..sales.lead_scorer import visibility_gap_from_audit_score

STATUS_ABSENT = "ABSENT"
STATUS_PRESENT = "PRESENT"
STATUS_NOT_CHECKED = "NOT_CHECKED"
STATUS_CLAIMED = "CLAIMED"

_PHONE_DIGITS = re.compile(r"\D+")
_ABBREV = {
    "street": "st",
    "st.": "st",
    "avenue": "ave",
    "ave.": "ave",
    "road": "rd",
    "rd.": "rd",
    "boulevard": "blvd",
    "blvd.": "blvd",
    "suite": "ste",
    "ste.": "ste",
    "drive": "dr",
    "dr.": "dr",
}


def tag_ai_source_type(domain: str, *, registry: dict | None = None) -> str:
    """BLA-4.1.2 — same registry file as Sonar's tag_source_type."""
    row = lookup_platform(domain, registry=registry)
    if row is None:
        return "UNKNOWN"
    return row.get("ai_source_type") or "UNKNOWN"


def build_presence_grid(
    listings: list[dict],
    competitors: list[dict] | None = None,
    *,
    platforms: tuple[str, ...] | list[str] | None = None,
    checked_at: str | None = None,
) -> dict:
    """BLA-4.2.1 — presence matrix. ABSENT vs NOT_CHECKED are distinct."""
    tracked = list(platforms or DEFAULT_HBOT_PLATFORM_IDS)
    by_platform = {row.get("platform"): row for row in listings if row.get("platform")}
    cells: list[dict] = []
    present = 0
    absent = 0
    not_checked = 0

    for platform in tracked:
        row = by_platform.get(platform)
        if row is None:
            status = STATUS_ABSENT
            absent += 1
            cell = {
                "platform": platform,
                "status": status,
                "health": 0,
                "reason": "listing not present in supplied check results",
            }
        else:
            status = (row.get("status") or "").upper()
            if status == STATUS_NOT_CHECKED or row.get("check_failed"):
                status = STATUS_NOT_CHECKED
                not_checked += 1
                cell = {
                    "platform": platform,
                    "status": status,
                    "health": None,
                    "reason": row.get("reason") or "platform could not be checked",
                }
            elif status == STATUS_ABSENT or row.get("exists") is False:
                status = STATUS_ABSENT
                absent += 1
                cell = {
                    "platform": platform,
                    "status": status,
                    "health": 0,
                    "reason": "listing does not exist",
                }
            else:
                status = STATUS_CLAIMED if row.get("claimed") else STATUS_PRESENT
                present += 1
                cell = {
                    "platform": platform,
                    "status": status,
                    "health": None,  # scored health deferred (Track D)
                    "listing": {
                        k: row.get(k)
                        for k in (
                            "name", "address", "phone", "website",
                            "category", "hours", "url", "claimed",
                            "review_count", "avg_rating",
                        )
                        if k in row
                    },
                    "reason": "listing observed",
                    "weights_status": "UNVALIDATED",
                }
        cells.append(cell)

    stamp = checked_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    checked = present + absent  # NOT_CHECKED excluded from coverage numerator
    coverage = {
        "platforms_tracked": len(tracked),
        "platforms_checked": checked,
        "present": present,
        "absent": absent,
        "not_checked": not_checked,
        "freshness_stamp": stamp,
        "coverage_statement": (
            f"checked {checked} of {len(tracked)} tracked platforms, "
            f"most recent check {stamp}"
        ),
    }

    competitor_coverage = None
    if competitors is not None:
        competitor_coverage = {
            "competitors_supplied": len(competitors),
            "note": "competitor cells are a snapshot; freshness_stamp applies",
        }

    return {
        "cells": cells,
        "coverage": coverage,
        "competitors": competitor_coverage,
        "scored_layers": "deferred",
    }


def _norm_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = _PHONE_DIGITS.sub("", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits or None


def _norm_address(value: str | None) -> str | None:
    if not value:
        return None
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    out = []
    for tok in tokens:
        out.append(_ABBREV.get(tok, tok))
    return " ".join(out) or None


def _norm_field(field: str, value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if field == "phone":
        return _norm_phone(text)
    if field == "address":
        return _norm_address(text)
    if field == "website":
        return text.lower().rstrip("/").removeprefix("https://").removeprefix("http://").removeprefix("www.")
    return text.lower()


def audit_nap_consistency(
    listings: list[dict], canonical: dict, *, fields: list[str] | None = None
) -> dict:
    """BLA-4.2.4 — NAP consistency. NULL with fewer than two checked platforms."""
    compare_fields = fields or [
        "name", "address", "phone", "website", "category", "hours",
    ]
    checked = [
        row for row in listings
        if (row.get("status") or "").upper() not in {STATUS_NOT_CHECKED, STATUS_ABSENT}
        and row.get("exists") is not False
        and not row.get("check_failed")
    ]
    # Also accept PRESENT-shaped rows without explicit status.
    if not checked:
        checked = [
            row for row in listings
            if row.get("exists") is True or row.get("name") or row.get("phone")
        ]
        checked = [
            row for row in checked
            if (row.get("status") or "").upper() != STATUS_NOT_CHECKED
            and not row.get("check_failed")
        ]

    platforms_checked = len(checked)
    if platforms_checked < 2:
        return {
            "consistency": None,
            "mismatches": [],
            "platforms_checked": platforms_checked,
            "reason": "fewer than two platforms successfully checked",
        }

    mismatches: list[dict] = []
    matching = 0
    comparable = 0
    for field in compare_fields:
        canon = _norm_field(field, canonical.get(field))
        for row in checked:
            # Skip fields the platform does not support.
            supported = row.get("supports")
            if isinstance(supported, (list, tuple, set)) and field not in supported:
                continue
            raw = row.get(field)
            if raw is None or raw == "":
                # Absent on a platform that otherwise exists: not a mismatch
                # unless the platform explicitly supports the field.
                if isinstance(supported, (list, tuple, set)) and field in supported:
                    comparable += 1
                    mismatches.append({
                        "platform": row.get("platform"),
                        "field": field,
                        "canonical": canon,
                        "observed": None,
                        "reason": f"{field} supported but empty",
                    })
                continue
            comparable += 1
            observed = _norm_field(field, raw)
            if canon is not None and observed == canon:
                matching += 1
            else:
                mismatches.append({
                    "platform": row.get("platform"),
                    "field": field,
                    "canonical": canon,
                    "observed": observed,
                    "reason": f"{field} mismatch",
                })

    if comparable == 0:
        return {
            "consistency": None,
            "mismatches": mismatches,
            "platforms_checked": platforms_checked,
            "reason": "no comparable fields across checked platforms",
        }

    return {
        "consistency": matching / comparable,
        "matching_fields": matching,
        "comparable_fields": comparable,
        "platforms_checked": platforms_checked,
        "mismatches": mismatches,
        "reason": f"{matching}/{comparable} field comparisons matched",
    }


def ecosystem_gap_axis(grid: dict) -> float:
    """0–40 opportunity feed for the lead scorer — delegates scaling."""
    coverage = grid.get("coverage") or {}
    tracked = coverage.get("platforms_tracked") or 0
    present = coverage.get("present") or 0
    if tracked <= 0:
        # No platforms tracked → unmeasured; treat as full gap opportunity
        # via the same scaler the audit score uses (0 audit → 40 gap).
        return float(visibility_gap_from_audit_score(0))
    # Presence ratio as a 0–100 "audit-like" score, then reuse lead-scorer scaling.
    presence_score = 100.0 * (present / tracked)
    return float(visibility_gap_from_audit_score(presence_score))


def platform_health(listing: dict, *, registry: dict | None = None) -> dict:
    """BLA-4.2.2 — ABSENT health=0; NOT_CHECKED health=NULL."""
    _ = registry  # reserved for Track D platform weights
    listing = listing or {}
    status = (listing.get("status") or "").upper()
    if status == STATUS_NOT_CHECKED or listing.get("check_failed"):
        return {
            "health": None,
            "status": STATUS_NOT_CHECKED,
            "reason": listing.get("reason") or "platform could not be checked",
            "weights_status": "UNVALIDATED",
        }
    if status == STATUS_ABSENT or listing.get("exists") is False:
        return {
            "health": 0,
            "status": STATUS_ABSENT,
            "reason": "listing does not exist",
            "weights_status": "UNVALIDATED",
        }
    from .eco_weights import weight

    score = weight("eco.health.exists")["value"]
    awards = ["exists"]
    if listing.get("claimed") or status == STATUS_CLAIMED:
        score += weight("eco.health.claimed")["value"]
        awards.append("claimed")
    reviews = int(listing.get("review_count") or 0)
    if reviews >= 10:
        score += weight("eco.health.reviews_10")["value"]
        awards.append("reviews_10")
    rating = listing.get("avg_rating")
    if rating is not None and float(rating) >= 4.0:
        score += weight("eco.health.rating_4")["value"]
        awards.append("rating_4")
    if listing.get("activity_within_90_days"):
        score += weight("eco.health.activity_90")["value"]
        awards.append("activity_90")
    if listing.get("structured_fields"):
        score += weight("eco.health.structured")["value"]
        awards.append("structured")
    if listing.get("description_matches_canonical"):
        score += weight("eco.health.messaging")["value"]
        awards.append("messaging")
    return {
        "health": max(0.0, min(100.0, score)),
        "status": STATUS_CLAIMED if listing.get("claimed") else STATUS_PRESENT,
        "awards": awards,
        "weights_status": "UNVALIDATED",
        "reason": "platform_health_scored",
    }
