"""Standalone tests for the ranking-factor audit engine (verify.py --geo battery).

No pytest. Run directly: python projects/geo_platform/tests/test_factor_audit.py

Three inline fixtures drive the branching: a strong page that satisfies the
catalog, a weak page that fails it, and the strong page with no field metrics so
the `not_measured` path is exercised. Assertions name specific factor ids, gap
strings, and scores rather than booleans.
"""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.ranking.factor_audit import (  # noqa: E402
    DEFAULT_WEIGHTS,
    FACTORS,
    STATUS_MEASURED,
    STATUS_NOT_MEASURED,
    audit_ranking,
    scorecard_markdown,
    visibility_gap_from_ranking,
)

GOOD_METRICS = {"lcp_s": 1.8, "inp_ms": 120, "cls": 0.04}
BAD_METRICS = {"lcp_s": 4.8, "inp_ms": 460, "cls": 0.31}

STRONG_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>Hyperbaric Oxygen Therapy | Bayview Wellness Clinic</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="https://bayviewwellness.example/hbot">
  <link rel="sitemap" type="application/xml" href="https://bayviewwellness.example/sitemap.xml">
  <script type="application/ld+json">
  {"@context":"https://schema.org","@graph":[
    {"@type":"MedicalClinic","name":"Bayview Wellness Clinic",
     "address":{"@type":"PostalAddress","streetAddress":"18 Harbour Road",
                "addressLocality":"Portland","addressRegion":"ME","postalCode":"04101"},
     "telephone":"(207) 555-0134",
     "openingHours":"Mo-Fr 08:00-18:00",
     "author":{"@type":"Person","name":"Dr. Helen Marsh"}},
    {"@type":"Service","name":"Hyperbaric Oxygen Therapy"},
    {"@type":"FAQPage","name":"HBOT questions"},
    {"@type":"Review","reviewBody":"Careful, professional care."}
  ]}
  </script>
</head>
<body>
<main>
  <h1>Hyperbaric Oxygen Therapy in Portland</h1>
  <p class="author-byline">Reviewed by Dr. Helen Marsh, M.D., medical director at
     Bayview Wellness Clinic since 2014.</p>
  <p>Bayview Wellness Clinic has delivered more than 4,200 sessions since
     January 2014. A standard course runs 20 sessions at 90 minutes each, at
     2.0 atmospheres absolute. Published trials from Tel Aviv University and
     Karolinska Institute report measurable outcomes for chronic wounds.</p>
  <ul>
    <li>Chronic non-healing wounds: 30 sessions typical</li>
    <li>Radiation tissue injury: 40 sessions typical</li>
    <li>Post-surgical recovery: 10 sessions typical</li>
  </ul>
  <blockquote>Our protocol follows Undersea Hyperbaric Medical Society guidance,
     updated March 2024.</blockquote>
  <h2>What the evidence shows</h2>
  <p>A 2021 review covering 1,600 patients found improvement in 78 percent of
     chronic wound cases treated across 12 months. Outcomes vary by indication
     and are assessed individually by our physicians before any course begins.
     Every plan is reviewed by Helen Marsh and documented in writing so patients
     understand the schedule, the cost, and the expected recovery window before
     they commit to a course of treatment at this clinic in Portland Maine.</p>
  <h2>Visit us</h2>
  <p>Bayview Wellness Clinic, 18 Harbour Road, Portland, ME 04101.
     Call <a href="tel:+12075550134">(207) 555-0134</a> to book an assessment.
     Our full accessibility and privacy policies are published on this site and
     reviewed each year by an independent auditor for accuracy and clarity.</p>
  <p><a href="https://bayviewwellness.example/llms.txt">AI crawler policy</a></p>
</main>
</body>
</html>"""

WEAK_HTML = """<html>
<head>
  <title>HBOT</title>
  <meta name="robots" content="noindex">
</head>
<body>
  <h1>Hyperbaric Therapy</h1>
  <p>We offer therapy. Call us today to feel better. Our team is here for you.</p>
  <img src="http://insecure.example/hero.jpg">
</body>
</html>"""


def _factor(result, factor_id):
    for row in result["factors"]:
        if row["id"] == factor_id:
            return row
    raise AssertionError(f"factor {factor_id} missing from result")


def test_strong_page_scores_high():
    r = audit_ranking(STRONG_HTML, metrics=GOOD_METRICS)
    assert r["overall_score"] >= 80, (
        f"Strong page should score >= 80, got {r['overall_score']} "
        f"(gaps: {[g['id'] for g in r['top_gaps']]})"
    )
    assert r["not_measured"] == [], f"All factors measurable here, got {r['not_measured']}"


def test_weak_page_scores_low_and_differs_from_strong():
    weak = audit_ranking(WEAK_HTML, metrics=BAD_METRICS)
    strong = audit_ranking(STRONG_HTML, metrics=GOOD_METRICS)
    assert weak["overall_score"] <= 25, (
        f"Weak page should score <= 25, got {weak['overall_score']}"
    )
    assert strong["overall_score"] - weak["overall_score"] >= 50, (
        f"Strong and weak must separate clearly: "
        f"{strong['overall_score']} vs {weak['overall_score']}"
    )


def test_missing_metrics_are_not_measured_not_zero():
    with_metrics = audit_ranking(STRONG_HTML, metrics=GOOD_METRICS)
    without = audit_ranking(STRONG_HTML)
    assert sorted(without["not_measured"]) == ["C1", "C2", "C3"], (
        f"Only the CWV factors should be unmeasured, got {without['not_measured']}"
    )
    for fid in ("C1", "C2", "C3"):
        row = _factor(without, fid)
        assert row["status"] == STATUS_NOT_MEASURED
        assert row["pass"] is None, f"{fid} pass must be None, got {row['pass']}"
        assert row["measured"] == "not measured", f"{fid} measured = {row['measured']}"
    # The absent factors are dropped from the denominator, not scored as zero.
    earned = sum(r["weight"] for r in without["factors"]
                 if r["status"] == STATUS_MEASURED and r["pass"])
    if_zeroed = round(earned / sum(DEFAULT_WEIGHTS.values()) * 100)
    assert without["overall_score"] > if_zeroed, (
        f"Unmeasured CWV must be excluded, not counted against the page: "
        f"scored {without['overall_score']}, would be {if_zeroed} if zeroed"
    )
    assert with_metrics["overall_score"] is not None


def test_unmeasured_factors_are_excluded_from_the_denominator():
    """A page failing everything except CWV scores the same measured or not."""
    without = audit_ranking(WEAK_HTML)
    measured_weight = sum(r["weight"] for r in without["factors"]
                          if r["status"] == STATUS_MEASURED)
    cwv_weight = sum(DEFAULT_WEIGHTS[f] for f in ("C1", "C2", "C3"))
    total_weight = sum(DEFAULT_WEIGHTS[f.id] for f in FACTORS)
    assert measured_weight == total_weight - cwv_weight, (
        f"Denominator should drop the {cwv_weight} CWV points: got {measured_weight}"
    )


def test_bad_metrics_name_value_and_threshold():
    r = audit_ranking(STRONG_HTML, metrics=BAD_METRICS)
    lcp = _factor(r, "C1")
    assert lcp["pass"] is False, "LCP 4.8s must fail the 2.5s threshold"
    assert lcp["measured"] == "4.8s", f"Measured value not reported: {lcp['measured']}"
    assert lcp["threshold"] == "<= 2.5s", f"Threshold not reported: {lcp['threshold']}"
    assert "4.8s against a 2.5s threshold" in lcp["gap_note"], (
        f"Gap note must name both numbers: {lcp['gap_note']}"
    )
    inp = _factor(r, "C2")
    assert inp["measured"] == "460ms" and inp["pass"] is False
    cls = _factor(r, "C3")
    assert cls["measured"] == "0.31" and cls["pass"] is False


def test_non_numeric_metric_is_not_measured_rather_than_guessed():
    r = audit_ranking(STRONG_HTML, metrics={"lcp_s": "fast", "inp_ms": 120, "cls": 0.04})
    lcp = _factor(r, "C1")
    assert lcp["status"] == STATUS_NOT_MEASURED, "A non-numeric metric must not be scored"
    assert "not a number" in lcp["gap_note"], f"Reason not given: {lcp['gap_note']}"
    assert _factor(r, "C2")["status"] == STATUS_MEASURED


def test_seo_and_geo_are_scored_separately():
    r = audit_ranking(STRONG_HTML, metrics=BAD_METRICS)
    assert r["seo_score"] != r["geo_score"], (
        "The strong page with bad vitals should split SEO from GEO, "
        f"both were {r['seo_score']}"
    )
    assert r["geo_score"] > r["seo_score"], (
        f"Bad vitals are an SEO cost, so GEO should lead: "
        f"geo={r['geo_score']} seo={r['seo_score']}"
    )
    for key in ("overall_score", "seo_score", "geo_score"):
        assert 0 <= r[key] <= 100, f"{key} out of range: {r[key]}"


def test_top_gaps_are_ordered_by_weight():
    r = audit_ranking(WEAK_HTML, metrics=BAD_METRICS)
    weights = [g["weight"] for g in r["top_gaps"]]
    assert weights == sorted(weights, reverse=True), (
        f"top_gaps must lead with the biggest lever, got {weights}"
    )
    assert r["top_gaps"][0]["id"] == "E1", (
        f"E1 (weight 9) is the heaviest failing factor, got {r['top_gaps'][0]['id']}"
    )
    assert all(g["pass"] is False for g in r["top_gaps"]), "Only failures are gaps"


def test_weak_page_names_specific_failures():
    r = audit_ranking(WEAK_HTML, metrics=BAD_METRICS)
    failed = {g["id"] for g in r["top_gaps"]}
    for fid in ("A1", "A3", "B1", "B2", "B3", "B4", "D1", "E1"):
        assert fid in failed, f"{fid} should fail on the weak page; failures were {failed}"
    assert "noindex" in _factor(r, "B1")["gap_note"]
    assert _factor(r, "B3")["measured"] == "1 insecure http:// reference"
    assert "300-word" in _factor(r, "A3")["gap_note"], _factor(r, "A3")["gap_note"]
    assert _factor(r, "D1")["measured"] == "0 JSON-LD node(s)"


def test_weights_come_from_a_parameter_not_hardcoded():
    base = audit_ranking(WEAK_HTML, metrics=GOOD_METRICS)
    reweighted = audit_ranking(WEAK_HTML, metrics=GOOD_METRICS, weights={"D1": 100})
    assert _factor(base, "D1")["pass"] is False, "D1 must be a failing factor here"
    assert _factor(reweighted, "D1")["weight"] == 100.0
    assert reweighted["overall_score"] < base["overall_score"], (
        f"Raising a failing factor's weight must lower the score: "
        f"{reweighted['overall_score']} vs {base['overall_score']}"
    )
    assert _factor(base, "D1")["weight"] == float(DEFAULT_WEIGHTS["D1"])


def test_registry_is_data_driven():
    """Every factor carries its own metadata, so a catalog row is a new entry."""
    assert len(FACTORS) == len(DEFAULT_WEIGHTS), (
        "Every factor needs a weight and every weight a factor"
    )
    ids = [f.id for f in FACTORS]
    assert len(set(ids)) == len(ids), f"Duplicate factor ids: {ids}"
    for f in FACTORS:
        assert f.id in DEFAULT_WEIGHTS, f"{f.id} has no default weight"
        assert f.threshold, f"{f.id} has no threshold"
        assert f.source, f"{f.id} has no authoritative source"
        assert f.axis in ("seo", "geo", "both"), f"{f.id} bad axis {f.axis}"
    families = {f.family[0] for f in FACTORS}
    assert families == {"A", "B", "C", "D", "E"}, (
        f"All five catalog families must be represented, got {families}"
    )


def test_scorecard_reports_not_measured_never_a_number():
    r = audit_ranking(STRONG_HTML)
    card = scorecard_markdown(r, business_name="Bayview Wellness Clinic")
    assert card.startswith("# Search & AI Visibility Scorecard - Bayview Wellness Clinic")
    assert card.isascii(), "The scorecard must stay ASCII so it renders in any console"
    assert "Not measured (excluded from the score)" in card
    assert "Largest Contentful Paint" in card
    assert "| C1 Largest Contentful Paint | not measured | <= 2.5s | not measured |" in card, (
        "CWV rows must read 'not measured', never a fabricated value"
    )
    assert "**Overall:**" in card and "/100" in card


def test_scorecard_leads_with_the_top_three_gaps_and_cites_them():
    r = audit_ranking(WEAK_HTML, metrics=BAD_METRICS)
    card = scorecard_markdown(r, business_name="Acme HBOT")
    assert "## The three biggest opportunities" in card
    assert "**1. Fact density**" in card, "The heaviest gap must lead"
    assert "*Source: ranking-factors-seo-geo-2026-07-26 brief.*" in card
    top_ids = [g["id"] for g in r["top_gaps"][:3]]
    for fid in top_ids:
        row = _factor(r, fid)
        assert row["label"] in card, f"{fid} label missing from scorecard"
    assert "**4." not in card, "Only the top three gaps are shown"


def test_empty_input_is_an_honest_empty_state():
    r = audit_ranking("   ")
    assert r["overall_score"] is None, "No HTML means no score, not zero"
    assert r["factors"] == []
    assert "empty input" in r["error"]
    card = scorecard_markdown(r, business_name="Nobody")
    assert "No scorecard could be produced" in card
    assert "/100" not in card, "An empty audit must not print a score"


def test_visibility_gap_feeds_the_lead_scorer():
    strong = audit_ranking(STRONG_HTML, metrics=GOOD_METRICS)
    weak = audit_ranking(WEAK_HTML, metrics=BAD_METRICS)
    strong_gap = visibility_gap_from_ranking(strong)
    weak_gap = visibility_gap_from_ranking(weak)
    assert weak_gap > strong_gap, (
        f"A worse site is a bigger opportunity: weak={weak_gap} strong={strong_gap}"
    )
    assert 0 <= strong_gap <= 40 and 0 <= weak_gap <= 40, (
        f"Gap must stay on the scorer's 0-40 axis: {strong_gap}, {weak_gap}"
    )
    assert visibility_gap_from_ranking({"overall_score": None}) == 0.0
    assert visibility_gap_from_ranking(None) == 0.0


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
