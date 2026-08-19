"""Sales-side services: lead scoring + unweighted CCC sales tools."""

from .lead_scorer import (
    accessibility_gap_from_compliance,
    classify_claim_risk,
    rank_leads,
    score_lead,
    visibility_gap_from_audit_score,
    DEFAULT_HIGH_RISK_TERMS,
    DEFAULT_MODERATE_RISK_TERMS,
)
from .schema_inspector import inspect_as_ai, inspect_proposed_jsonld, render_comparison
from .preview_delivery import (
    clear_preview_store,
    create_preview,
    preview_status,
    record_open,
)
from .proposal_generator import build_proposal

__all__ = [
    "accessibility_gap_from_compliance",
    "classify_claim_risk",
    "rank_leads",
    "score_lead",
    "visibility_gap_from_audit_score",
    "DEFAULT_HIGH_RISK_TERMS",
    "DEFAULT_MODERATE_RISK_TERMS",
    "inspect_as_ai",
    "inspect_proposed_jsonld",
    "render_comparison",
    "clear_preview_store",
    "create_preview",
    "preview_status",
    "record_open",
    "build_proposal",
]