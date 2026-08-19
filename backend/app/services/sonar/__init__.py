"""Sonar package — classifier, metrics, gaps, accuracy audit."""

from .accuracy_audit import (
    correction_packet,
    extract_claims,
    severity,
    verify_claims,
)
from .citation_classifier import (
    citation_ratio,
    classify_references,
    tag_source_type,
)
from .gap_analysis import (
    detect_citation_gaps,
    find_conversion_opportunities,
    score_gap_priority,
)
from .multi_model import (
    compare_engines,
    summarize_presence,
)
from .visibility_metrics import (
    citation_stability_index,
    package_proportion,
    share_of_voice,
    wilson_interval,
)

__all__ = [
    "citation_ratio",
    "classify_references",
    "tag_source_type",
    "compare_engines",
    "summarize_presence",
    "wilson_interval",
    "share_of_voice",
    "citation_stability_index",
    "package_proportion",
    "detect_citation_gaps",
    "score_gap_priority",
    "find_conversion_opportunities",
    "extract_claims",
    "verify_claims",
    "severity",
    "correction_packet",
]
