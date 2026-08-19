# SPEC: SPEC_CCC_M3_CITATION_INFLUENCE
"""Standalone Citation Influence tests."""
from __future__ import annotations

from datetime import date, timedelta
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(PROJ, "backend")
for p in (PROJ, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.ranking.citation_influence import (
    citation_influence_index,
    classify_edit,
    freshness_score,
    trust_cues,
)
from app.services.ranking.entity_clustering import extract_entity_graph
from app.services.ranking.schema_intelligence import (
    FISCHMAN_NOTE,
    classify_payload,
    factual_density,
    generate_attribute_rich_jsonld,
    schema_report,
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


BARE_ORG = """
<html><script type="application/ld+json">
{"@context":"https://schema.org","@type":"Organization","name":"Hope"}
</script></html>
"""

RICH = """
<html><script type="application/ld+json">
{
  "@context":"https://schema.org",
  "@type":"MedicalClinic",
  "name":"Hope",
  "priceRange":"$200-$400",
  "aggregateRating":{"@type":"AggregateRating","ratingValue":4.8,"reviewCount":42},
  "openingHours":"Mo-Fr 09:00-17:00",
  "dateModified":"2026-06-01"
}
</script>
<script type="application/ld+json">
{"@type":"FAQPage","mainEntity":[{"@type":"Question","name":"What is HBOT?","acceptedAnswer":{"@type":"Answer","text":"Oxygen therapy."}}]}
</script></html>
"""


def test_structural_vs_payload_and_absent():
    bare = schema_report(BARE_ORG)
    assert_true(bare["classification"] == "STRUCTURAL", "bare Organization is STRUCTURAL")
    assert_true(
        "OR = 0.678" in (bare.get("gap_note") or "") and "p = 0.296" in (bare.get("gap_note") or ""),
        "STRUCTURAL note quotes Fischman OR and p",
    )
    rich = schema_report(RICH)
    assert_true(rich["classification"] == "PAYLOAD", "rich MedicalClinic is PAYLOAD")
    absent = factual_density({"has_jsonld": False, "nodes": []})
    assert_true(absent["FDS"] is None, "no JSON-LD FDS is null not 0")
    assert_true(absent["classification"] == "ABSENT", "no JSON-LD classification ABSENT")


def test_jsonld_omits_invented_rating():
    out = generate_attribute_rich_jsonld({"name": "Hope"}, {"name": "Hope", "telephone": "555"})
    blob = str(out)
    assert_true("aggregateRating" not in blob, "no aggregateRating when rating not supplied")


def test_freshness_bands():
    today = date(2026, 7, 28)
    assert_true(freshness_score(today - timedelta(days=30), today=today) == 100.0, "age 30 -> 100")
    assert_true(freshness_score(today - timedelta(days=90), today=today) == 80.0, "age 90 -> 80")
    assert_true(freshness_score(today - timedelta(days=180), today=today) == 60.0, "age 180 -> 60")
    assert_true(freshness_score(today - timedelta(days=365), today=today) == 40.0, "age 365 -> 40")
    assert_true(freshness_score(today - timedelta(days=366), today=today) == 20.0, "age >365 -> 20")
    assert_true(freshness_score(None, today=today) is None, "unknown freshness NULL")


def test_cii_renorm_and_insufficient():
    with_fresh_zero = citation_influence_index({
        "topical_relevance": 80,
        "pricing_presence": 100,
        "freshness": 0,
        "trust_cues": 50,
        "schema_fds": 60,
    })
    unknown_fresh = citation_influence_index({
        "topical_relevance": 80,
        "pricing_presence": 100,
        "freshness": None,
        "trust_cues": 50,
        "schema_fds": 60,
    })
    assert_true(unknown_fresh["CII"] is not None, "CII with unknown freshness still scores")
    assert_true(
        unknown_fresh["CII"] > with_fresh_zero["CII"],
        "excluding unknown freshness beats scoring freshness as zero",
    )
    thin = citation_influence_index({"topical_relevance": 80, "pricing_presence": 100})
    assert_true(thin["CII"] is None, "CII NULL with fewer than 3 components")
    assert_true(thin["reason"] == "insufficient_components", "insufficient_components reason")


def test_edit_and_unsupported_and_serp():
    fmt = classify_edit("Hello world paragraph one.", "Hello world paragraph one.")
    assert_true(fmt["class"] == "FORMATTING_ONLY", "reorder/same text FORMATTING_ONLY")
    sub = classify_edit("Hello world.", "Hello world. Sessions from $250.")
    assert_true(sub["class"] == "SUBSTANTIVE", "adding price is SUBSTANTIVE")
    trust = trust_cues("We offer a miracle cure and treat autism.")
    assert_true(len(trust["unsupported_claims"]) >= 1, "unsupported superiority/high-risk listed")
    assert_true(
        "compliance_checker" in trust["route"],
        "unsupported claims routed to compliance gate",
    )
    missing = extract_entity_graph(None)
    assert_true(missing["status"] == "NO_SERP_DATA", "missing SERP -> NO_SERP_DATA")
    assert_true(missing["graph"] is None, "NO_SERP_DATA graph is null not empty")


if __name__ == "__main__":
    _ = (classify_payload, FISCHMAN_NOTE)
    test_structural_vs_payload_and_absent()
    test_jsonld_omits_invented_rating()
    test_freshness_bands()
    test_cii_renorm_and_insufficient()
    test_edit_and_unsupported_and_serp()
    print(f"{passed}/{total} passed")
