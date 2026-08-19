# SPEC: SPEC_CCC_M4_ECOSYSTEM_FOOTPRINT
"""Review campaign planner — refuse PHI, gating, incentives."""
from __future__ import annotations

from ..compliance.compliance_checker import DEFAULT_HIGH_RISK_TERMS, check_phi_testimonials

_GATE_WORDS = ("nps", "satisfaction", "sentiment", "only happy", "promoter")
_INCENTIVE_WORDS = ("gift card", "discount", "free session", "in exchange", "reward", "incentive")


def validate_campaign_compliance(campaign: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    template = (campaign or {}).get("template") or ""
    selection = " ".join(str(x) for x in ((campaign or {}).get("selection_criteria") or []))
    blob = f"{template} {selection}".lower()

    for term in DEFAULT_HIGH_RISK_TERMS:
        if term.lower() in blob:
            reasons.append(f"PHI rule: high-risk/clinical term '{term}' not allowed in review templates")
    # Also catch condition words via PHI testimonial checker on wrapped html
    findings = check_phi_testimonials(f"<div class='testimonial'>{template}</div>")
    if findings:
        # Empty-input finding alone shouldn't block a non-empty template
        serious = [f for f in findings if f.get("id") != "input-empty"]
        if serious:
            reasons.append("PHI rule: template failed compliance PHI/testimonial checks")

    if any(w in blob for w in _GATE_WORDS):
        reasons.append("review gating: selection may not reference NPS/satisfaction/sentiment")
    if any(w in blob for w in _INCENTIVE_WORDS):
        reasons.append("incentives: templates may not offer value in exchange for a review")

    return (len(reasons) == 0, reasons)


def plan_review_campaign(platform: str, health: dict, *, policy: dict) -> dict:
    template = (policy or {}).get("template") or (
        "We hope you had a good experience. If you are willing, please consider leaving a review."
    )
    selection = list((policy or {}).get("selection_criteria") or ["all_recent_patients_unfiltered"])
    campaign = {
        "platform": platform,
        "template": template,
        "selection_criteria": selection,
        "health": health or {},
    }
    ok, reasons = validate_campaign_compliance(campaign)
    if not ok:
        return {
            "status": "REFUSED",
            "campaign": None,
            "reasons": reasons,
            "reason": reasons[0] if reasons else "compliance refusal",
        }
    return {
        "status": "OK",
        "campaign": campaign,
        "reasons": [],
        "reason": "compliant neutral experience request",
    }
