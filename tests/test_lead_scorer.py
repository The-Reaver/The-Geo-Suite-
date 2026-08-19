"""Standalone tests for the HBOT lead scorer (verify.py --geo battery).

No pytest. Run directly: python projects/geo_platform/tests/test_lead_scorer.py

Fixtures are the six seeded providers from sales/HBOT_Lead_Ranking.xlsx, with
their exact spreadsheet inputs. The expected priorities and tiers are the values
in docs/HBOT_LEAD_RANKING.md, so a drift in the weights fails here.
"""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.sales.lead_scorer import (  # noqa: E402
    accessibility_gap_from_compliance,
    classify_claim_risk,
    rank_leads,
    score_lead,
    visibility_gap_from_audit_score,
    DEFAULT_HIGH_RISK_TERMS,
    DEFAULT_MODERATE_RISK_TERMS,
)

DELOREY = {
    "name": "DeLorey Chiropractic Clinic",
    "practice_type": "Chiropractic",
    "ownership": "Private",
    "decision_maker": "Owner (Dr. Nathan DeLorey, D.C.)",
    "payment_model": "Cash",
    "indications": ["Sports injuries", "concussions", "autism", "fatigue"],
}

PETERS = {
    "name": "Peters Chiropractic",
    "practice_type": "Chiropractic",
    "ownership": "Private",
    "decision_maker": "Owner (Dr. Steven Peters, D.C.)",
    "payment_model": "Cash",
    "indications": ["Concussions", "sports/brain injury recovery", "whiplash"],
}

KOS = {
    "name": "KOS Integrative (Tanaka & Chong)",
    "practice_type": "Chiropractic",
    "ownership": "Private",
    "decision_maker": "Owner (Dr. Josuke Tanaka, D.C.)",
    "payment_model": "Cash",
    "indications": ["Chiropractic neurology", "TBI care", "functional med"],
}

APPLEWOOD = {
    "name": "Applewood Chiropractic Health Center",
    "practice_type": "Chiropractic",
    "ownership": "Private",
    "decision_maker": "Partner (Drs. Joyce & Jackson, D.C.)",
    "payment_model": "Cash",
    "indications": ["Altitude acclimatization", "sports injuries", "wellness"],
}

INTEGRATIVE = {
    "name": "Integrative Hyperbaric & Wound Care",
    "practice_type": "Integrative Med",
    "ownership": "Private",
    "decision_maker": "Medical Director (Dr. Raj Mehra, D.O.)",
    "payment_model": "Mixed",
    "indications": ["Brain injury", "Lyme", "fibromyalgia", "neuropathy"],
}

YORK = {
    "name": "York Hospital Wound Care Center",
    "practice_type": "Wound Care",
    "ownership": "Hospital",
    "decision_maker": "Medical Director (Dr. Beth Easton, MD)",
    "payment_model": "Insurance",
    "indications": ["Diabetic ulcers", "osteomyelitis", "carbon monoxide"],
}

SEEDED = [DELOREY, PETERS, KOS, APPLEWOOD, INTEGRATIVE, YORK]

# priority, tier, fit -- straight from docs/HBOT_LEAD_RANKING.md
EXPECTED = {
    "DeLorey Chiropractic Clinic": (76, "A", 100),
    "Peters Chiropractic": (74, "A", 100),
    "KOS Integrative (Tanaka & Chong)": (74, "A", 100),
    "Applewood Chiropractic Health Center": (69, "B", 94),
    "Integrative Hyperbaric & Wound Care": (49, "C", 62),
    "York Hospital Wound Care Center": (24, "DQ", 32),
}


def test_seeded_providers_match_the_spreadsheet():
    for provider in SEEDED:
        name = provider["name"]
        want_priority, want_tier, want_fit = EXPECTED[name]
        result = score_lead(provider)
        assert result["fit"] == want_fit, (
            f"{name}: fit {result['fit']} != spreadsheet {want_fit}"
        )
        assert result["priority"] == want_priority, (
            f"{name}: priority {result['priority']} != spreadsheet {want_priority}"
        )
        assert result["tier"] == want_tier, (
            f"{name}: tier {result['tier']} != spreadsheet {want_tier}"
        )


def test_delorey_is_tier_a_at_76_unaudited():
    result = score_lead(DELOREY)
    assert result["priority"] == 76, f"Expected 76, got {result['priority']}"
    assert result["tier"] == "A", f"Expected tier A, got {result['tier']}"
    assert result["fit"] == 100, f"Expected fit 100, got {result['fit']}"
    assert result["provisional"] is True, "Unaudited leads must be flagged provisional"
    joined = " | ".join(result["reasons"])
    assert "claim risk 'High'" in joined, f"Autism must drive High claim risk: {joined}"
    assert "autism" in joined, f"The off-label term must be named: {joined}"
    assert "40/40 fit points" in joined, f"Chiropractic must earn 40: {joined}"


def test_applewood_is_tier_b_at_69():
    result = score_lead(APPLEWOOD)
    assert result["priority"] == 69, f"Expected 69, got {result['priority']}"
    assert result["tier"] == "B", f"Expected tier B, got {result['tier']}"
    joined = " | ".join(result["reasons"])
    assert "partner-owned" in joined, f"Partner ownership must be named: {joined}"
    assert "24/30 fit points" in joined, f"Partner access must earn 24: {joined}"


def test_hospital_hard_filter_always_wins():
    """Even given a perfect audit, a hospital stays DQ."""
    generous_audit = {"accessibility_gap": 40, "visibility_gap": 40}
    result = score_lead(YORK, audit=generous_audit)
    assert result["tier"] == "DQ", f"Hospital must be DQ, got {result['tier']}"
    assert result["priority"] > 24, (
        "The record still carries a computed priority; only the tier is forced to DQ"
    )
    joined = " | ".join(result["reasons"])
    assert "hard filter" in joined, f"The filter must be explained: {joined}"
    assert "hospital-affiliated" in joined, f"The reason must name why: {joined}"


def test_audit_raises_opportunity_and_clears_provisional():
    unaudited = score_lead(INTEGRATIVE)
    audited = score_lead(INTEGRATIVE, audit={"accessibility_gap": 35,
                                             "visibility_gap": 30})
    assert unaudited["provisional"] is True, "Unaudited must be provisional"
    assert audited["provisional"] is False, "Audited must clear the provisional flag"
    assert audited["opportunity"] > unaudited["opportunity"], (
        f"Audit gaps must raise opportunity: {audited['opportunity']} "
        f"vs {unaudited['opportunity']}"
    )
    assert audited["priority"] > unaudited["priority"], (
        f"Audit gaps must raise priority: {audited['priority']} "
        f"vs {unaudited['priority']}"
    )
    # 62 fit, opportunity 35 + 30 + 20 = 85 -> round(43.4 + 25.5) = 69
    assert audited["opportunity"] == 85, f"Expected 85, got {audited['opportunity']}"
    assert audited["priority"] == 69, f"Expected 69, got {audited['priority']}"
    assert audited["tier"] == "B", f"The audit must lift C to B, got {audited['tier']}"


def test_audit_gaps_are_clamped_to_their_axes():
    result = score_lead(DELOREY, audit={"accessibility_gap": 900,
                                        "visibility_gap": -50})
    assert result["opportunity"] == 60, (
        f"Gaps must clamp to 40 and 0, giving 40+0+20=60, got {result['opportunity']}"
    )


def test_missing_keys_fail_cleanly():
    result = score_lead({"name": "Nameless Clinic"})
    assert result["tier"] == "INCOMPLETE", f"Expected INCOMPLETE, got {result['tier']}"
    assert result["priority"] == 0, "An unscoreable record must not invent a priority"
    joined = " | ".join(result["reasons"])
    assert "missing required key(s)" in joined, f"Reason unclear: {joined}"
    assert "practice_type" in joined, f"The missing keys must be named: {joined}"


def test_empty_provider_fails_cleanly():
    result = score_lead({})
    assert result["tier"] == "INCOMPLETE", f"Expected INCOMPLETE, got {result['tier']}"
    assert "missing required key(s)" in " ".join(result["reasons"])


def test_rank_leads_orders_by_priority_with_dq_last():
    ranked = rank_leads(SEEDED)
    names = [row["name"] for row in ranked]
    priorities = [row["priority"] for row in ranked]

    assert names[0] == "DeLorey Chiropractic Clinic", (
        f"Highest priority must lead, got {names[0]}"
    )
    assert names[-1] == "York Hospital Wound Care Center", (
        f"DQ must sort last, got {names[-1]}"
    )
    non_dq = [row for row in ranked if row["tier"] != "DQ"]
    non_dq_priorities = [row["priority"] for row in non_dq]
    assert non_dq_priorities == sorted(non_dq_priorities, reverse=True), (
        f"Non-DQ leads must be descending by priority, got {non_dq_priorities}"
    )
    assert priorities[0] == 76, f"Expected 76 at the top, got {priorities[0]}"


def test_rank_leads_applies_audits_by_name():
    audits = {"Integrative Hyperbaric & Wound Care": {"accessibility_gap": 35,
                                                      "visibility_gap": 30}}
    ranked = rank_leads(SEEDED, audits)
    by_name = {row["name"]: row for row in ranked}
    assert by_name["Integrative Hyperbaric & Wound Care"]["provisional"] is False
    assert by_name["Integrative Hyperbaric & Wound Care"]["priority"] == 69
    assert by_name["DeLorey Chiropractic Clinic"]["provisional"] is True, (
        "A provider with no audit stays provisional"
    )


def test_rank_leads_does_not_mutate_providers():
    before = [dict(p) for p in SEEDED]
    rank_leads(SEEDED)
    assert [dict(p) for p in SEEDED] == before, "Scoring must never mutate the input"


def test_off_label_term_list_is_a_parameter():
    band_default, matched_default = classify_claim_risk(["autism"])
    assert band_default == "High", f"autism is High by default, got {band_default}"
    assert matched_default == ["autism"], f"Got {matched_default}"

    band_custom, _ = classify_claim_risk(["autism"], high_risk_terms=["lyme"],
                                         moderate_risk_terms=[])
    assert band_custom == "Low", (
        f"With autism removed from the term list the band must drop, got {band_custom}"
    )

    band_promoted, _ = classify_claim_risk(["diabetic ulcers"],
                                           high_risk_terms=["diabetic ulcers"])
    assert band_promoted == "High", f"A custom term must be honoured, got {band_promoted}"


def test_default_term_lists_are_documented_lists():
    assert isinstance(DEFAULT_HIGH_RISK_TERMS, list)
    assert isinstance(DEFAULT_MODERATE_RISK_TERMS, list)
    assert "autism" in DEFAULT_HIGH_RISK_TERMS
    assert "lyme" in DEFAULT_HIGH_RISK_TERMS
    assert "concussion" in DEFAULT_MODERATE_RISK_TERMS


def test_on_label_indications_are_low_risk():
    band, matched = classify_claim_risk(
        ["Diabetic ulcers", "osteomyelitis", "carbon monoxide"])
    assert band == "Low", f"On-label wound care must be Low risk, got {band}"
    assert matched == [], f"Nothing should match: {matched}"


def test_compliance_and_audit_bridges_map_onto_the_gap_axes():
    assert accessibility_gap_from_compliance({"compliance_gap_0_100": 100}) == 40.0
    assert accessibility_gap_from_compliance({"compliance_gap_0_100": 50}) == 20.0
    assert accessibility_gap_from_compliance({}) == 0.0
    assert visibility_gap_from_audit_score(100) == 0.0
    assert visibility_gap_from_audit_score(50) == 20.0


def test_every_seeded_candidate_carries_nonempty_evidence_with_3plus_talking_points():
    """SPEC_SALES_VALIDATION_PASS section 4.1 acceptance: "Every candidate
    carries a non-empty evidence pack and at least three talking points."

    This codebase has no separate 'evidence pack' object; the deterministic
    `reasons` list `score_lead` returns IS the candidate-facing evidence --
    it names the real inputs (practice type, payment model, decision maker,
    claim risk, audit status, priority formula) that drove the score, which
    is exactly what an agent reads off a call script. Proven against the
    fixed six-provider SEEDED dataset (docs/HBOT_LEAD_RANKING.md), not a
    single cherry-picked example, and covers the DQ (hospital) candidate too
    -- a disqualified candidate still gets an honest evidence pack, not a
    blank one.
    """
    for provider in SEEDED:
        name = provider["name"]
        result = score_lead(provider)
        reasons = result["reasons"]
        assert isinstance(reasons, list), f"{name}: reasons must be a list, got {type(reasons)}"
        assert len(reasons) >= 3, (
            f"{name}: evidence pack has only {len(reasons)} talking point(s) "
            f"({reasons!r}); spec requires at least three"
        )
        for reason in reasons:
            assert isinstance(reason, str) and reason.strip(), (
                f"{name}: evidence pack contains a blank/placeholder entry: {reason!r}"
            )
        joined = " | ".join(reasons)
        assert provider["practice_type"].lower() in joined.lower(), (
            f"{name}: evidence pack does not name the real practice type "
            f"'{provider['practice_type']}', got: {joined}"
        )
        assert provider["payment_model"].lower() in joined.lower(), (
            f"{name}: evidence pack does not name the real payment model "
            f"'{provider['payment_model']}', got: {joined}"
        )

    # Ranking sanity's companion: the ranked list itself (what a rep actually
    # opens) preserves a nonempty evidence pack per row, DQ candidate included.
    ranked = rank_leads(SEEDED)
    assert len(ranked) == len(SEEDED), (
        f"rank_leads dropped candidates: {len(ranked)} of {len(SEEDED)}"
    )
    for row in ranked:
        assert len(row["reasons"]) >= 3, (
            f"{row['name']}: ranked candidate lost its evidence pack, "
            f"only {len(row['reasons'])} talking point(s): {row['reasons']!r}"
        )
    dq_row = next(r for r in ranked if r["name"] == "York Hospital Wound Care Center")
    assert len(dq_row["reasons"]) >= 3, (
        "the disqualified (DQ) candidate must still carry a real evidence pack, "
        f"not a blank one: {dq_row['reasons']!r}"
    )


def _run_all():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  " + t.__name__)
            passed += 1
        except AssertionError as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
        except Exception as e:
            print("FAIL  " + t.__name__ + ": " + type(e).__name__ + " " + str(e))
    print(f"\n{passed}/{len(tests)} passed")
    if passed < len(tests):
        sys.exit(1)


if __name__ == "__main__":
    _run_all()
