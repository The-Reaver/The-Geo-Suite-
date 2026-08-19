"""Compliance checking for a WCAG 2.1 AA static subset, health-marketing claims, and PHI testimonials."""

from .compliance_checker import (
    audit_site,
    check_accessibility,
    check_marketing_claims,
    check_phi_testimonials,
    DEFAULT_HIGH_RISK_TERMS,
)

__all__ = [
    "audit_site",
    "check_accessibility",
    "check_marketing_claims",
    "check_phi_testimonials",
    "DEFAULT_HIGH_RISK_TERMS",
]
