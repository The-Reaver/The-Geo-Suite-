"""Deterministic HBOT lead scorer.

Productizes `docs/HBOT_LEAD_RANKING.md` and the formulas seeded in
`sales/HBOT_Lead_Ranking.xlsx`. Pure, importable, offline: scoring never fetches
a site and never mutates a provider record.

The weights below mirror the spreadsheet cell-for-cell:

    fit          = type_pts(0-40) + payment_pts(0-30) + owner_access_pts(0-30)
    opportunity  = accessibility_gap(0-40) + visibility_gap(0-40) + claim_risk_pts(0-20)
    priority     = ROUND(0.7 * fit + 0.3 * opportunity)
    tier         = DQ if hospital-owned, else A >= 70, B 50-69, C < 50

The hospital hard filter always wins: hospital-affiliated centers buy through
procurement and do not control their web presence, so they are not prospects.
"""
from __future__ import annotations

import math
import re

TYPE_POINTS: dict[str, int] = {
    "chiropractic": 40,
    "integrative med": 32,
    "sports/pain": 28,
    "wellness": 24,
    "veterinary": 20,
}
TYPE_POINTS_DEFAULT = 10

PAYMENT_POINTS: dict[str, int] = {
    "cash": 30,
    "mixed": 20,
}
PAYMENT_POINTS_DEFAULT = 12  # insurance-dependent

OWNER_ACCESS_HOSPITAL = 10
OWNER_ACCESS_OWNER = 30
OWNER_ACCESS_PARTNER = 24
OWNER_ACCESS_DEFAULT = 10  # corporate / no single accessible decision-maker

CLAIM_RISK_POINTS = {"High": 20, "Med": 12, "Low": 5}

# Documented defaults, overridable per call. High-risk terms are the off-label
# HBOT claims that carry real FTC exposure; moderate terms are off-label but
# commonly marketed with hedging.
DEFAULT_HIGH_RISK_TERMS: list[str] = [
    "autism", "lyme", "anti-aging", "antiaging", "reverse aging", "cancer",
    "alzheimer", "dementia", "multiple sclerosis", "cerebral palsy",
]
DEFAULT_MODERATE_RISK_TERMS: list[str] = [
    "concussion", "concussions", "brain injury", "tbi", "traumatic brain",
    "sports", "sports injury", "recovery", "wellness", "fatigue",
    "fibromyalgia", "neuropathy", "neurology", "functional med", "altitude",
    "longevity", "performance", "whiplash",
]

REQUIRED_KEYS = (
    "name", "practice_type", "ownership", "decision_maker",
    "payment_model", "indications",
)

TIER_A_MIN = 70
TIER_B_MIN = 50

MAX_ACCESSIBILITY_GAP = 40
MAX_VISIBILITY_GAP = 40


def _excel_round(value: float) -> int:
    """Excel ROUND is half-away-from-zero; Python's round() is half-to-even."""
    if value >= 0:
        return int(math.floor(value + 0.5))
    return -int(math.floor(-value + 0.5))


def _clamp(value, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, number))


def _mentions(text: str, terms: list[str]) -> list[str]:
    found: list[str] = []
    for term in terms or []:
        pattern = r"\b" + re.escape(term.strip().lower()).replace(r"\ ", r"\s+") + r"\b"
        if term.strip() and re.search(pattern, text):
            found.append(term)
    return found


def classify_claim_risk(
    indications,
    *,
    high_risk_terms: list[str] | None = None,
    moderate_risk_terms: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Return (band, matched_terms) where band is 'High' | 'Med' | 'Low'."""
    high = DEFAULT_HIGH_RISK_TERMS if high_risk_terms is None else high_risk_terms
    moderate = (DEFAULT_MODERATE_RISK_TERMS
                if moderate_risk_terms is None else moderate_risk_terms)

    if isinstance(indications, str):
        text = indications.lower()
    else:
        text = ", ".join(str(i) for i in (indications or [])).lower()

    matched_high = _mentions(text, high)
    if matched_high:
        return "High", matched_high
    matched_med = _mentions(text, moderate)
    if matched_med:
        return "Med", matched_med
    return "Low", []


def _type_points(practice_type: str) -> int:
    return TYPE_POINTS.get(str(practice_type or "").strip().lower(),
                           TYPE_POINTS_DEFAULT)


def _payment_points(payment_model: str) -> int:
    return PAYMENT_POINTS.get(str(payment_model or "").strip().lower(),
                              PAYMENT_POINTS_DEFAULT)


def _owner_access_points(ownership: str, decision_maker: str) -> tuple[int, str]:
    if str(ownership or "").strip().lower() == "hospital":
        return OWNER_ACCESS_HOSPITAL, "hospital-affiliated"
    dm = str(decision_maker or "").lower()
    if "owner" in dm:
        return OWNER_ACCESS_OWNER, "owner-operated"
    if "partner" in dm:
        return OWNER_ACCESS_PARTNER, "partner-owned"
    return OWNER_ACCESS_DEFAULT, "no single accessible owner"


def _incomplete(missing: list[str]) -> dict:
    return {
        "name": "",
        "fit": 0,
        "opportunity": 0,
        "priority": 0,
        "tier": "INCOMPLETE",
        "provisional": True,
        "reasons": [
            f"cannot score: provider record is missing required key(s) "
            f"{', '.join(missing)}"
        ],
    }


def score_lead(provider: dict, *, audit: dict | None = None,
               high_risk_terms: list[str] | None = None,
               moderate_risk_terms: list[str] | None = None) -> dict:
    """Score one provider. Returns {name, fit, opportunity, priority, tier,
    provisional, reasons}. Never raises on a malformed record."""
    if not isinstance(provider, dict) or not provider:
        return _incomplete(list(REQUIRED_KEYS))

    missing = [k for k in REQUIRED_KEYS if k not in provider or provider[k] in (None, "")]
    if missing:
        return _incomplete(missing)

    name = str(provider["name"])
    practice_type = str(provider["practice_type"])
    ownership = str(provider["ownership"])
    decision_maker = str(provider["decision_maker"])
    payment_model = str(provider["payment_model"])

    reasons: list[str] = []

    type_pts = _type_points(practice_type)
    payment_pts = _payment_points(payment_model)
    owner_pts, owner_label = _owner_access_points(ownership, decision_maker)
    fit = type_pts + payment_pts + owner_pts

    reasons.append(f"practice type '{practice_type}' -> {type_pts}/40 fit points")
    reasons.append(f"payment model '{payment_model}' -> {payment_pts}/30 fit points")
    reasons.append(
        f"decision maker '{decision_maker}' -> {owner_pts}/30 fit points ({owner_label})"
    )

    band, matched = classify_claim_risk(
        provider["indications"],
        high_risk_terms=high_risk_terms,
        moderate_risk_terms=moderate_risk_terms,
    )
    claim_risk_pts = CLAIM_RISK_POINTS[band]
    matched_note = f" (off-label terms: {', '.join(matched)})" if matched else ""
    reasons.append(
        f"claim risk '{band}' -> {claim_risk_pts}/20 opportunity points{matched_note}"
    )

    provisional = True
    accessibility_gap = 0.0
    visibility_gap = 0.0
    if isinstance(audit, dict) and (
        "accessibility_gap" in audit or "visibility_gap" in audit
    ):
        accessibility_gap = _clamp(audit.get("accessibility_gap", 0),
                                   0, MAX_ACCESSIBILITY_GAP)
        visibility_gap = _clamp(audit.get("visibility_gap", 0), 0, MAX_VISIBILITY_GAP)
        provisional = False
        reasons.append(
            f"audited: accessibility gap {accessibility_gap:g}/40, "
            f"visibility gap {visibility_gap:g}/40"
        )
    else:
        reasons.append(
            "no site audit supplied: accessibility and visibility gaps count 0, "
            "so this score is provisional and can only rise"
        )

    opportunity = accessibility_gap + visibility_gap + claim_risk_pts
    priority = _excel_round(0.7 * fit + 0.3 * opportunity)

    is_hospital = str(ownership).strip().lower() == "hospital"
    if is_hospital:
        tier = "DQ"
        reasons.append(
            "hard filter: hospital-affiliated centers are disqualified regardless "
            "of fit or opportunity"
        )
    elif priority >= TIER_A_MIN:
        tier = "A"
    elif priority >= TIER_B_MIN:
        tier = "B"
    else:
        tier = "C"

    reasons.append(
        f"priority = round(0.7 * {fit:g} + 0.3 * {opportunity:g}) = {priority}; tier {tier}"
    )

    return {
        "name": name,
        "fit": int(fit),
        "opportunity": int(opportunity) if float(opportunity).is_integer() else opportunity,
        "priority": priority,
        "tier": tier,
        "provisional": provisional,
        "reasons": reasons,
    }


def rank_leads(providers: list[dict], audits: dict | None = None) -> list[dict]:
    """Score many providers; return sorted by priority descending, DQ last.

    `audits` maps a provider name to its audit dict. Read-only: the input
    provider records are never modified.
    """
    if not isinstance(providers, list):
        return []

    audits = audits if isinstance(audits, dict) else {}
    scored: list[dict] = []
    for provider in providers:
        key = provider.get("name") if isinstance(provider, dict) else None
        scored.append(score_lead(provider, audit=audits.get(key)))

    def sort_key(row: dict) -> tuple[int, int]:
        rank = {"DQ": 2, "INCOMPLETE": 1}.get(row["tier"], 0)
        return (rank, -row["priority"])

    return sorted(scored, key=sort_key)


def accessibility_gap_from_compliance(prospect_result: dict) -> float:
    """Map `compliance_checker.audit_site(mode='prospect')` onto the 0-40
    accessibility-gap axis this model expects."""
    if not isinstance(prospect_result, dict):
        return 0.0
    gap = _clamp(prospect_result.get("compliance_gap_0_100", 0), 0, 100)
    return round(gap * MAX_ACCESSIBILITY_GAP / 100.0, 2)


def visibility_gap_from_audit_score(normalized_score) -> float:
    """Map a GEO AI-readiness score (0-100) onto the 0-40 visibility-gap axis."""
    score = _clamp(normalized_score, 0, 100)
    return round((100 - score) * MAX_VISIBILITY_GAP / 100.0, 2)
