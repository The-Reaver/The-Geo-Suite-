# SPEC: SPEC_CCC_M2_SONAR
"""Standalone Sonar tests — unweighted classifier + Wilson + multi-model grid.

No network. Asserts values and named reasons, not bare booleans.
"""
from __future__ import annotations

import math
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(PROJ, "backend")
for p in (PROJ, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.compliance.compliance_checker import DEFAULT_HIGH_RISK_TERMS
from app.services.sonar.accuracy_audit import (
    correction_packet,
    extract_claims,
    severity,
    verify_claims,
)
from app.services.sonar.alert_gates import evaluate_sov_drop_alert, intervals_overlap
from app.services.sonar.citation_classifier import (
    citation_ratio,
    classify_references,
    tag_source_type,
)
from app.services.sonar.gap_analysis import (
    detect_citation_gaps,
    find_conversion_opportunities,
    score_gap_priority,
)
from app.services.sonar.multi_model import (
    compare_engines,
    summarize_presence,
    wilson_interval,
)
from app.services.sonar.visibility_metrics import (
    citation_stability_index,
    share_of_voice,
)

passed = 0
total = 0


def assert_true(cond, msg):
    global passed, total
    total += 1
    if not cond:
        print("FAIL:", msg)
        raise SystemExit(1)
    print("PASS:", msg)
    passed += 1


def test_citation_vs_mention_and_null_ratio():
    domains = ["clinic.example"]
    aliases = ["Hyperbaric Hope"]

    linked = classify_references(
        "See Hyperbaric Hope at https://clinic.example/about for hours.",
        [],
        brand_domains=domains,
        brand_aliases=aliases,
    )
    assert_true(len(linked["citations"]) == 1, "linked brand domain is a CITATION")
    assert_true(
        linked["citation_ratio"] == 1.0,
        "citation-only response has ratio 1.0",
    )

    mention_only = classify_references(
        "Patients often ask about Hyperbaric Hope near downtown.",
        [],
        brand_domains=domains,
        brand_aliases=aliases,
    )
    assert_true(len(mention_only["mentions"]) == 1, "alias without link is a MENTION")
    assert_true(len(mention_only["citations"]) == 0, "no citation without brand URL")
    assert_true(
        mention_only["citation_ratio"] == 0.0,
        "mention-only ratio is 0.0 (seen, never linked)",
    )

    empty = classify_references(
        "No clinic is named here.",
        ["https://other.example/page"],
        brand_domains=domains,
        brand_aliases=aliases,
    )
    assert_true(empty["citation_ratio"] is None, "unseen brand returns NULL ratio not 0")
    assert_true(
        empty["reason"] == "not seen in any tracked response",
        "NULL ratio reason named",
    )
    assert_true(
        citation_ratio(0, 0) is None,
        "citation_ratio(0,0) is NULL not 0",
    )


def test_word_boundary_alias_and_foreign_url_excluded():
    out = classify_references(
        "The hyperbaric chamber market grew; see https://unrelated.example/x",
        [],
        brand_domains=["clinic.example"],
        brand_aliases=["Hyperbaric"],
    )
    # "hyperbaric" as substring of a longer phrase still matches as a word;
    # ensure embedded-in-word fails:
    embedded = classify_references(
        "prehypeRBARICally speaking nothing",
        [],
        brand_domains=["clinic.example"],
        brand_aliases=["Hyperbaric"],
    )
    assert_true(
        len(embedded["mentions"]) == 0,
        "substring-inside-word is not a mention",
    )
    assert_true(
        len(out["citations"]) == 0,
        "foreign URL is excluded from brand citations",
    )


def test_tag_source_type_hbot_registry():
    assert_true(
        tag_source_type("https://www.healthgrades.com/physician/x") == "REVIEW_SITE",
        "Healthgrades maps to REVIEW_SITE",
    )
    assert_true(
        tag_source_type("https://www.zocdoc.com/doctor/y") == "DIRECTORY",
        "Zocdoc maps to DIRECTORY",
    )
    assert_true(
        tag_source_type("https://www.reddit.com/r/Hyperbaric/") == "COMMUNITY",
        "Reddit maps to COMMUNITY",
    )
    assert_true(
        tag_source_type("https://random-unknown.example/page") == "UNKNOWN",
        "unregistered domain maps to UNKNOWN not silently GENERAL",
    )


def test_wilson_interval_bounds_and_small_n():
    # Documented call shape from SPEC: wilson_interval(4, 20)
    ci = wilson_interval(4, 20)
    assert_true(ci is not None, "n=20 returns an interval")
    lo, hi = ci
    assert_true(0.0 <= lo < hi <= 1.0, "Wilson bounds inside [0,1]")
    # Hand check: p̂=0.2, z=1.96 → centre≈0.238, margin≈0.168 → ~[0.070, 0.406]
    assert_true(
        abs(lo - 0.0805) < 0.02 and abs(hi - 0.406) < 0.03,
        f"wilson_interval(4,20) near documented region got {(lo, hi)}",
    )
    assert_true(
        wilson_interval(1, 4) is None,
        "n<5 returns NULL (insufficient sampling) not a point estimate",
    )


def test_compare_engines_presence_and_unavailable():
    grid = compare_engines(
        {
            "chatgpt": {
                "status": "OK",
                "response_text": "Try Hyperbaric Hope https://clinic.example/",
                "cited_urls": [],
            },
            "perplexity": {
                "status": "OK",
                "response_text": "Hyperbaric Hope is nearby.",
                "cited_urls": [],
            },
            "gemini": {
                "status": "UNAVAILABLE",
                "reason": "quota",
            },
        },
        brand_domains=["clinic.example"],
        brand_aliases=["Hyperbaric Hope"],
    )
    assert_true(grid["ok_engines"] == 2, "UNAVAILABLE engines excluded from ok count")
    assert_true(grid["cited_engines"] == 1, "one engine cited the brand domain")
    assert_true(grid["seen_engines"] == 2, "cited or mentioned counts as seen")
    assert_true(
        grid["presence_wilson_95"] is None,
        "presence CI NULL when ok_engines < 5 (insufficient sampling)",
    )
    assert_true(
        grid["weights_status"] == "UNVALIDATED",
        "comparison grid tags weights UNVALIDATED",
    )
    assert_true(
        summarize_presence(grid) == "PARTIALLY_VISIBLE",
        "one citation + two seen maps to PARTIALLY_VISIBLE",
    )


def test_alert_gate_suppresses_overlapping_ci():
    assert_true(
        intervals_overlap(0.10, 0.30, 0.25, 0.40) is True,
        "overlapping intervals detected",
    )
    suppressed = evaluate_sov_drop_alert(
        prev_point=0.50,
        curr_point=0.30,
        prev_ci=(0.35, 0.55),
        curr_ci=(0.20, 0.40),
        drop_pp_threshold=10.0,
    )
    assert_true(
        suppressed["fire"] is False and suppressed["reason"] == "insufficient_sample",
        "10pp+ drop with overlapping CIs does not fire",
    )
    fired = evaluate_sov_drop_alert(
        prev_point=0.50,
        curr_point=0.20,
        prev_ci=(0.45, 0.55),
        curr_ci=(0.10, 0.25),
        drop_pp_threshold=10.0,
    )
    assert_true(
        fired["fire"] is True and fired["reason"] == "interval_separated_drop",
        "separated intervals allow drop alert",
    )


def test_share_of_voice_three_clinic_fixture():
    # A: 2c+1m = 5, B: 1c+0m = 2, C: 0c+3m = 3; denom 10 → 0.5 / 0.2 / 0.3
    out = share_of_voice(
        {
            "A": {"citations": 2, "mentions": 1},
            "B": {"citations": 1, "mentions": 0},
            "C": {"citations": 0, "mentions": 3},
        }
    )
    assert_true(out["shares"] is not None, "SOV shares present for non-empty counts")
    assert_true(
        abs(out["shares"]["A"] - 0.5) < 1e-9
        and abs(out["shares"]["B"] - 0.2) < 1e-9
        and abs(out["shares"]["C"] - 0.3) < 1e-9,
        "three-clinic SOV matches hand computation with w_c=2",
    )
    assert_true(
        out["weights_status"] == "UNVALIDATED",
        "SOV payload tags weights UNVALIDATED",
    )
    assert_true(out["w_c"] == 2.0, "SOV uses registry seed w_c=2.0")

    empty = share_of_voice({})
    assert_true(empty["shares"] is None, "empty brand_counts yields NULL shares")
    assert_true(
        empty["reason"] == "no brand referenced in tracked responses",
        "empty SOV reason named",
    )


def test_csi_renorm_and_insufficient_components():
    partial = citation_stability_index(0.8, 0.6, 0.4, None)
    assert_true(partial["csi"] is not None, "CSI computed with three components")
    # Renorm over w1+w2+w3 = 0.85 → 100*(0.4/0.85*0.8 + 0.3/0.85*0.6 + 0.15/0.85*0.4)
    expected = 100.0 * (
        (0.40 / 0.85) * 0.8 + (0.30 / 0.85) * 0.6 + (0.15 / 0.85) * 0.4
    )
    assert_true(
        abs(partial["csi"] - expected) < 1e-9,
        "CSI renormalises when freshness is unmeasurable",
    )
    assert_true(
        partial["weights_status"] == "UNVALIDATED",
        "CSI tags weights UNVALIDATED",
    )
    thin = citation_stability_index(0.9, None, None, None)
    assert_true(thin["csi"] is None, "CSI NULL with fewer than two components")
    assert_true(
        thin["reason"] == "fewer than two measurable CSI components",
        "thin CSI reason named",
    )


def test_gap_missing_weight_is_unranked():
    gaps = detect_citation_gaps(
        {
            "healthgrades": {"brand_cited": False, "engine": "chatgpt"},
            "zocdoc": {"brand_cited": True, "engine": "chatgpt"},
        },
        {
            "healthgrades": {
                "competitors_present": ["Rival A", "Rival B"],
                "competitors_tracked": 3,
            },
            "zocdoc": {
                "competitors_present": ["Rival A"],
                "competitors_tracked": 3,
            },
        },
    )
    assert_true(len(gaps) == 1, "only competitor-present brand-absent platform is a gap")
    assert_true(gaps[0]["platform"] == "healthgrades", "gap platform is healthgrades")

    unranked = score_gap_priority(
        gaps[0],
        engine_weights={},  # missing weight must not score as zero
        sov_deficit=0.4,
        effort="low",
    )
    assert_true(
        unranked["priority"] == "UNRANKED",
        "missing engine_weight yields UNRANKED not zero",
    )
    assert_true(
        unranked["reason"] == "missing engine_weight in registry",
        "UNRANKED reason named",
    )
    assert_true(unranked["score"] is None, "UNRANKED score is NULL not 0")

    scored = score_gap_priority(
        gaps[0],
        engine_weights={"healthgrades": 0.8},
        sov_deficit=0.4,
        effort="low",
    )
    # a*2/3 + b*0.8 + c*0.4 + d*(1-0.1) = 0.3*0.666... + 0.24 + 0.1 + 0.135
    expected = 100.0 * (
        0.30 * (2 / 3) + 0.30 * 0.8 + 0.25 * 0.4 + 0.15 * 0.9
    )
    assert_true(
        abs(scored["score"] - expected) < 1e-6,
        f"scored gap priority matches seed formula got {scored['score']}",
    )
    assert_true(
        scored["weights_status"] == "UNVALIDATED",
        "gap priority tags weights UNVALIDATED",
    )

    opps = find_conversion_opportunities(
        {
            "citations": [],
            "mentions": [{"alias": "Hyperbaric Hope"}],
            "third_party_sources": ["https://www.healthgrades.com/physician/x"],
        }
    )
    assert_true(len(opps) == 1, "mention-without-citation yields conversion opportunity")
    assert_true(
        opps[0]["opportunity_type"] == "mention_without_citation",
        "conversion opportunity type named",
    )


def test_medical_hallucination_is_critical():
    assert_true(
        "autism" in DEFAULT_HIGH_RISK_TERMS or "treats autism" in DEFAULT_HIGH_RISK_TERMS,
        "compliance high-risk list includes autism terms",
    )
    claims = extract_claims(
        "Hyperbaric Hope treats autism and offers a miracle cure.",
        brand_aliases=["Hyperbaric Hope"],
    )
    assert_true(len(claims) >= 1, "indication claim extracted near brand alias")
    verified = verify_claims(
        claims,
        fact_sheet={
            "indications_treated": ["diabetic foot ulcer"],
            "indications_not_treated": ["autism"],
        },
    )
    hallu = [v for v in verified if v["status"] == "HALLUCINATION"]
    assert_true(len(hallu) >= 1, "unsupported autism treatment is HALLUCINATION")
    sev = severity(hallu[0])
    assert_true(sev == "CRITICAL", "medical indication hallucination is CRITICAL")
    packet = correction_packet(hallu[0])
    assert_true(packet["severity"] == "CRITICAL", "correction packet severity CRITICAL")
    assert_true(
        packet["compliance_high_risk_term"] in DEFAULT_HIGH_RISK_TERMS,
        f"CRITICAL cites compliance high-risk term got {packet['compliance_high_risk_term']}",
    )
    assert_true(
        packet["route"] == "compliance_checker.DEFAULT_HIGH_RISK_TERMS",
        "medical CRITICAL routes through compliance checker list",
    )


if __name__ == "__main__":
    test_citation_vs_mention_and_null_ratio()
    test_word_boundary_alias_and_foreign_url_excluded()
    test_tag_source_type_hbot_registry()
    test_wilson_interval_bounds_and_small_n()
    test_compare_engines_presence_and_unavailable()
    test_alert_gate_suppresses_overlapping_ci()
    test_share_of_voice_three_clinic_fixture()
    test_csi_renorm_and_insufficient_components()
    test_gap_missing_weight_is_unranked()
    test_medical_hallucination_is_critical()
    print(f"{passed}/{total} passed")
