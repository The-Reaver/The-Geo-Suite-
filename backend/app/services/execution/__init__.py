# SPEC: SPEC_CCC_M6_AGENTIC
"""Closed-loop agentic execution — outreach, CMS push, MCP tools."""
from .outreach import (
    community_engagement_draft,
    competitor_review_intel,
    listing_packet,
    review_campaign_package,
)
from .cms_push import (
    connect_cms,
    inject_schema,
    onpage_suggestions,
    push_content_brief,
)
from .mcp_tools import (
    enqueue_content_optimization,
    enqueue_directory_submission,
    learn_from_outcomes,
    register_tools,
    verification_window,
)

__all__ = [
    "listing_packet",
    "review_campaign_package",
    "community_engagement_draft",
    "competitor_review_intel",
    "connect_cms",
    "inject_schema",
    "push_content_brief",
    "onpage_suggestions",
    "register_tools",
    "enqueue_directory_submission",
    "enqueue_content_optimization",
    "verification_window",
    "learn_from_outcomes",
]
