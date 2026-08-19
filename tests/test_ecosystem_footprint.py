"""Standalone tests for M4 ecosystem presence detection (unweighted)."""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.ecosystem import (  # noqa: E402
    STATUS_ABSENT,
    STATUS_NOT_CHECKED,
    audit_nap_consistency,
    build_presence_grid,
    ecosystem_gap_axis,
    tag_ai_source_type,
)
from app.services.sonar import tag_source_type  # noqa: E402


def test_absent_vs_not_checked_are_distinct():
    grid = build_presence_grid(
        [
            {"platform": "healthgrades", "status": "ABSENT"},
            {
                "platform": "vitals",
                "status": "NOT_CHECKED",
                "reason": "rate limited",
            },
            {
                "platform": "yelp",
                "exists": True,
                "name": "Thrive HBOT",
                "phone": "303-555-0100",
            },
        ],
        platforms=("healthgrades", "vitals", "yelp"),
        checked_at="2026-07-26",
    )
    by = {c["platform"]: c for c in grid["cells"]}
    assert by["healthgrades"]["status"] == STATUS_ABSENT
    assert by["healthgrades"]["health"] == 0
    assert by["vitals"]["status"] == STATUS_NOT_CHECKED
    assert by["vitals"]["health"] is None
    assert by["healthgrades"] != by["vitals"]
    assert "checked 2 of 3" in grid["coverage"]["coverage_statement"]


def test_unregistered_domain_tags_unknown_both_axes():
    assert tag_ai_source_type("https://random.example") == "UNKNOWN"
    assert tag_source_type("https://random.example") == "UNKNOWN"
    assert tag_ai_source_type("https://yelp.com/biz/x") == "CONSENSUS_CRITICAL"
    assert tag_source_type("https://yelp.com/biz/x") == "DIRECTORY"


def test_nap_null_with_one_platform_and_excludes_unsupported():
    one = audit_nap_consistency(
        [{"platform": "yelp", "name": "Thrive", "phone": "3035550100"}],
        {"name": "Thrive", "phone": "303-555-0100"},
    )
    assert one["consistency"] is None
    assert "fewer than two" in one["reason"]

    two = audit_nap_consistency(
        [
            {
                "platform": "yelp",
                "name": "Thrive HBOT",
                "phone": "(303) 555-0100",
                "supports": ["name", "phone", "address"],
            },
            {
                "platform": "uhms",
                "name": "Thrive HBOT",
                "phone": "3035550100",
                "supports": ["name", "phone"],  # no address support
                "address": None,
            },
        ],
        {
            "name": "Thrive HBOT",
            "phone": "303-555-0100",
            "address": "100 Main Street",
        },
    )
    assert two["consistency"] is not None
    # address on uhms unsupported → not counted as mismatch
    assert all(
        m["field"] != "address" or m["platform"] != "uhms"
        for m in two["mismatches"]
    ), two


def test_ecosystem_gap_axis_worsens_as_presence_drops():
    rich = build_presence_grid(
        [
            {"platform": p, "exists": True, "name": "X"}
            for p in ("google_business_profile", "healthgrades", "yelp")
        ],
        platforms=("google_business_profile", "healthgrades", "yelp"),
    )
    poor = build_presence_grid(
        [],
        platforms=("google_business_profile", "healthgrades", "yelp"),
    )
    gap_rich = ecosystem_gap_axis(rich)
    gap_poor = ecosystem_gap_axis(poor)
    assert 0 <= gap_rich <= 40, gap_rich
    assert 0 <= gap_poor <= 40, gap_poor
    assert gap_poor > gap_rich, (gap_poor, gap_rich)


def test_backlink_unknown_null_and_partial_da():
    from app.services.ecosystem.link_intelligence import score_backlink

    unknown = score_backlink({"domain": "https://random-unknown.example/x"})
    assert unknown["score"] is None, unknown
    assert unknown["source_type"] == "UNKNOWN"
    assert "NULL" in unknown["reason"] or unknown["score"] is None

    partial = score_backlink({
        "domain": "https://yelp.com/biz/x",
        "placement": "in-content",
        "anchor_relevance": 0.5,
    })
    assert partial["partial"] is True, partial
    assert "domain_authority" in partial["missing"]


def test_platform_health_absent_vs_not_checked():
    from app.services.ecosystem.footprint_manager import platform_health

    absent = platform_health({"platform": "healthgrades", "status": "ABSENT"})
    assert absent["health"] == 0 and absent["status"] == STATUS_ABSENT
    missing = platform_health({"platform": "healthgrades", "status": "NOT_CHECKED"})
    assert missing["health"] is None and missing["status"] == STATUS_NOT_CHECKED
    assert absent != missing


def test_review_campaign_refuses_phi_and_gating():
    from app.services.ecosystem.review_campaign import plan_review_campaign

    phi = plan_review_campaign(
        "yelp",
        {"health": 20},
        policy={"template": "Thanks for your autism treatment visit — leave a review!"},
    )
    assert phi["status"] == "REFUSED", phi
    assert any("PHI" in r for r in phi["reasons"]), phi["reasons"]

    gated = plan_review_campaign(
        "yelp",
        {"health": 20},
        policy={
            "template": "Please leave a review.",
            "selection_criteria": ["high NPS promoters only"],
        },
    )
    assert gated["status"] == "REFUSED", gated
    assert any("gating" in r.lower() for r in gated["reasons"]), gated["reasons"]


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
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
