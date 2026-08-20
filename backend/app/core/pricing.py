"""The GEO Suite sales pricing tiers -- the one place these numbers live.

2026-08-20: previously hardcoded identically in two places
(app/services/reporting/sales_kit.py's _pricing_html() and frontend/app/nova/
NovaShell.tsx's pricing panel), kept in sync by hand. Define it once here;
sales_kit.py imports PRICING_TIERS directly, and the frontend fetches the
same data from GET /sales/pricing-tiers (see app/routers/sales_preview.py)
rather than hardcoding a second copy in TypeScript.

Illustrative pricing, pending final sign-off -- not yet an operator-committed
price list. Nothing here is a legal or contractual claim.
"""
from __future__ import annotations

from . import rubric

PRICING_TIERS: list[dict] = [
    {
        "name": "Starter",
        "price": 500,
        "tag": "Foundational AI-search readiness",
        "popular": False,
        "bullets": [
            "Live AI-Search Readiness audit",
            f"Gap report vs. the {rubric.PUBLISH_THRESHOLD}-point publish gate",
            "Monthly readiness re-check",
            "No site rebuild included",
        ],
    },
    {
        "name": "Full-Service Growth",
        "price": 2500,
        "tag": "Everything to clear the gate and stay there",
        "popular": True,
        "bullets": [
            f"Generated site tuned to clear the {rubric.PUBLISH_THRESHOLD}-point gate",
            "Hosting, SSL, uptime monitoring",
            "Ongoing AI-visibility + local SEO optimization",
            "Monthly compliance + readiness report",
            "Unlimited content updates",
        ],
    },
    {
        "name": "Growth + Social",
        "price": 4500,
        "tag": "For practices ready to dominate online",
        "popular": False,
        "bullets": [
            "Everything in Full-Service Growth, plus",
            "YouTube, Instagram, Facebook management",
            "Review + reputation engine",
            "We handle everything — send us raw content",
        ],
    },
]
