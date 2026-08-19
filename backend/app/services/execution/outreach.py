# SPEC: SPEC_CCC_M6_AGENTIC
"""Outreach assets — listing packets, review packages, community drafts (EXE-6.1)."""
from __future__ import annotations

from collections import Counter
from typing import Any

from ..ecosystem.review_campaign import validate_campaign_compliance


def listing_packet(gap: dict, brand: dict) -> dict:
    """EXE-6.1.1 — field map + drafts; never invent phone/price."""
    gap = gap or {}
    brand = brand or {}
    required = ("name", "phone", "address", "website")
    missing = [k for k in required if not brand.get(k)]
    if missing:
        return {
            "status": "INSUFFICIENT_BRAND_DATA",
            "packet": None,
            "missing_keys": missing,
            "reason": f"missing brand fields: {', '.join(missing)}",
        }
    platform = gap.get("platform") or gap.get("directory") or "directory"
    return {
        "status": "OK",
        "packet": {
            "platform": platform,
            "field_map": {
                "name": brand.get("name"),
                "phone": brand.get("phone"),
                "address": brand.get("address"),
                "website": brand.get("website"),
                "categories": list(brand.get("categories") or gap.get("categories") or []),
            },
            "description_draft": brand.get("description")
            or f"{brand.get('name')} — local care listing draft (human review required).",
            "add_business_url": gap.get("add_url")
            or f"https://example.invalid/{platform}/add-business",
            "steps": [
                "Confirm NAP against brand facts",
                "Paste description draft",
                "Submit for human approval before publish",
            ],
            "gap": gap,
        },
        "reason": "listing packet from brand facts only",
    }


def review_campaign_package(platform: str, health: dict, *, policy: dict) -> dict:
    """EXE-6.1.2 — delegates compliance to M4; named refusal reasons."""
    policy = policy or {}
    campaign = {
        "platform": platform,
        "template": policy.get("template")
        or "We hope you had a good experience. If willing, please consider a review.",
        "selection_criteria": list(
            policy.get("selection_criteria") or ["all_recent_patients_unfiltered"]
        ),
        "health": health or {},
    }
    ok, reasons = validate_campaign_compliance(campaign)
    if not ok:
        return {
            "status": "REFUSED",
            "package": None,
            "reasons": reasons,
            "reason": reasons[0] if reasons else "compliance refusal",
        }
    return {
        "status": "OK",
        "package": campaign,
        "reasons": [],
        "reason": "compliant review package",
    }


def community_engagement_draft(thread: dict, brand: dict) -> dict:
    """EXE-6.1.3 — suggestion only; promotional heuristic; no auto-post."""
    thread = thread or {}
    brand = brand or {}
    title = thread.get("title") or thread.get("topic") or "discussion"
    body = (
        f"Draft reply for {brand.get('name') or 'the clinic'} on '{title}'. "
        f"Share helpful context; do not hard-sell. Human approval required before post."
    )
    promo_words = ("buy now", "limited offer", "discount", "call today", "best price")
    blob = body.lower() + " " + str(thread.get("suggested_cta") or "").lower()
    promo_hits = [w for w in promo_words if w in blob]
    return {
        "status": "OK",
        "draft": body,
        "promotional_score": min(1.0, 0.25 * len(promo_hits)),
        "guideline_warnings": (
            ["hard-sell language detected — revise before approval"] if promo_hits else []
        ),
        "auto_post": False,
        "requires_human_approval": True,
        "reason": "draft suggestion only — never auto-post in v1",
    }


def competitor_review_intel(reviews: list[dict]) -> dict:
    """EXE-6.1.4 — theme counts from injected corpora; positioning notes only."""
    if not reviews:
        return {
            "status": "EMPTY",
            "praised": [],
            "complaints": [],
            "recommendations": [],
            "reason": "no injected review corpus",
        }
    praised: Counter[str] = Counter()
    complaints: Counter[str] = Counter()
    for r in reviews:
        themes = r.get("themes") or []
        sentiment = (r.get("sentiment") or "").lower()
        for t in themes:
            if sentiment in ("positive", "praise"):
                praised[t] += 1
            elif sentiment in ("negative", "complaint"):
                complaints[t] += 1
            else:
                # Neutral/unknown — skip counting as praise or complaint
                pass
    return {
        "status": "OK",
        "praised": [{"theme": t, "count": c} for t, c in praised.most_common(5)],
        "complaints": [{"theme": t, "count": c} for t, c in complaints.most_common(5)],
        "recommendations": [
            {
                "note": "Positioning note from themes — not a causal claim",
                "basis": "co-occurring review themes in injected corpus",
            }
        ],
        "reason": "theme counts only; no causation",
    }
