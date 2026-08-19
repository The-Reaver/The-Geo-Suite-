# SPEC: SPEC_CCC_M9_ADMIN
"""Admin registry seeds — UNVALIDATED until Track B settles."""
from __future__ import annotations

WEIGHTS_STATUS = "UNVALIDATED"

# Representative count cap (ADM-9.1.3)
REPRESENTATIVE_K = 5

# Lexical similarity / co-occurrence thresholds
CLUSTER_TOKEN_JACCARD_MIN = 0.35
HEALTH_DIVERGENCE_THRESHOLD = 0.45

# Budget alert fractions (ADM-9.2.3)
BUDGET_ALERT_FRACTION = 0.8
BUDGET_EXHAUST_FRACTION = 1.0

# Journey-stage phrase table (HBOT-adapted seeds)
JOURNEY_STAGE_PHRASES: dict[str, tuple[str, ...]] = {
    "AWARENESS": (
        "what is",
        "how does",
        "benefits of",
        "explained",
        "overview",
    ),
    "CONSIDERATION": (
        "vs",
        "versus",
        "compare",
        "alternatives",
        "side effects",
        "is it safe",
    ),
    "DECISION": (
        "near me",
        "cost",
        "price",
        "appointment",
        "book",
        "schedule",
        "clinic",
    ),
    "ADVOCACY": (
        "review",
        "testimonial",
        "recommend",
        "success story",
        "patient story",
    ),
}

ROLES = ("Admin", "Analyst", "Viewer", "Client")
