# SPEC: SPEC_CCC_M8_REPORTING (branded report renderer)
"""Standalone tests for the branded HTML report renderer (GEO item 7).

Offline: pure string rendering, no network, no PDF binary. Proves the branded
document carries the same honesty the JSON/text exporters enforce — withheld
metrics never render as a number, measured metrics always show their interval,
and a view with no limitations cannot be rendered at all.
"""
from __future__ import annotations

import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(PROJ, "backend")
for p in (PROJ, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.reporting.export import export_report  # noqa: E402
from app.services.reporting.render_html import render_report_html  # noqa: E402

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


def _view():
    return {
        "client": "North Loop Chiropractic",
        "window": {"start": "2026-07-01", "end": "2026-07-31"},
        "score": 93,
        "categories": {"Structured": 18, "Semantic": 17, "Crawler": 11},
        "metrics": {
            "share_of_voice": {
                "name": "Share of voice", "value": 0.42, "ci_lower": 0.31,
                "ci_upper": 0.53, "n": 120, "status": "MEASURED", "kind": "sampled",
            },
            "near_me_rank": {
                "name": "Near-me rank", "value": None, "status": "INSUFFICIENT_DATA",
                "kind": "sampled",
            },
        },
        "limitations": ["Sampled metrics describe controlled prompt sets, not all queries."],
        "methodology": {"show_your_work": True, "weights_status": "UNVALIDATED"},
    }


def test_renders_branded_document():
    html = render_report_html(_view(), branding={"colors": {"accent": "#0a7d33"}})
    assert_true(html.startswith("<!doctype html>"), "produces a full HTML document")
    assert_true("North Loop Chiropractic" in html, "shows the client name in the header")
    assert_true("#0a7d33" in html, "applies the client brand accent color")
    assert_true("<svg" in html, "includes inline SVG charts, not raw JSON")


def test_measured_metric_shows_its_interval():
    html = render_report_html(_view())
    assert_true("Share of voice" in html, "renders the measured metric name")
    assert_true("95% CI [0.31, 0.53]" in html, "measured metric shows its confidence interval")


def test_withheld_metric_is_not_a_zero():
    html = render_report_html(_view())
    assert_true("INSUFFICIENT_DATA" in html, "withheld metric shows its status label")
    assert_true(
        "zero would be a lie" in html,
        "withheld metric explicitly is not rendered as a number",
    )


def test_score_gauge_and_gate():
    html = render_report_html(_view())
    assert_true("gate 93" in html, "score gauge draws the 93-point publish gate")
    assert_true("clears the publish gate" in html, "93 is reported as clearing the gate")


def test_unvalidated_weights_badge_shown():
    html = render_report_html(_view())
    assert_true("weights: UNVALIDATED" in html, "UNVALIDATED weights surfaced as a badge, not hidden")


def test_refuses_dishonest_view():
    bad = _view()
    bad["limitations"] = []
    try:
        render_report_html(bad)
    except ValueError:
        assert_true(True, "a view with no limitations block is refused, like every other export")
    else:
        assert_true(False, "renderer must refuse an empty-limitations view")


def test_value_and_savings_block():
    v = _view()
    v["value"] = {"agency_range": [24000, 83500], "price": 6900, "savings_range": [17100, 76600]}
    html = render_report_html(v)
    assert_true("Value &amp; Savings" in html, "renders the Value & Savings section")
    assert_true("$24,000" in html and "$83,500" in html, "shows the assembled-vendor range")
    assert_true("$17,100" in html and "$76,600" in html, "shows the documented savings range")
    assert_true("not a guarantee" in html or "not a quote" in html, "carries the honesty methodology note")


def test_value_block_absent_when_no_value():
    html = render_report_html(_view())  # no 'value' key
    assert_true("Value &amp; Savings" not in html, "no value section when none supplied")


def _pillar_view():
    """A view using the rich per-category shape dashboard.category_pillars()
    produces from a real AuditResult -- findings, tier, status, not-measured
    reason, not just a points bar."""
    v = _view()
    v["categories"] = [
        {
            "id": 1, "name": "Structured Data", "weight": 20, "earned": 13,
            "tier": "hypothesis", "status": "measured",
            "findings": ["Missing Organization schema", "No sameAs links found"],
        },
        {
            "id": 2, "name": "Semantic Clarity", "weight": 20, "earned": 20,
            "tier": "documented", "status": "measured", "findings": [],
        },
        {
            "id": 3, "name": "Crawler Access", "weight": 12, "earned": 0,
            "tier": "documented", "status": "not_measured",
            "not_measured_reason": "This live preview only fetches the homepage.",
        },
    ]
    v["fix_list"] = [
        "[Structured Data, up to 7 pts] Missing Organization schema",
        "[Structured Data, up to 7 pts] No sameAs links found",
    ]
    return v


def test_pillar_findings_render_per_category():
    html = render_report_html(_pillar_view())
    assert_true("Pillar-by-pillar findings" in html, "renders the pillar-by-pillar section")
    assert_true("Missing Organization schema" in html, "shows a real per-category finding")
    assert_true("No sameAs links found" in html, "shows a second real finding under the same pillar")


def test_pillar_marks_hypothesis_tier():
    html = render_report_html(_pillar_view())
    assert_true("hypothesis" in html, "hypothesis-tier pillar carries a visible badge")


def test_pillar_clean_category_says_so():
    html = render_report_html(_pillar_view())
    assert_true("No findings" in html, "a clean pillar (zero findings) says so explicitly, not a blank section")


def test_not_measured_pillar_shows_reason_not_a_score():
    html = render_report_html(_pillar_view())
    assert_true("NOT MEASURED" in html, "excluded pillar is labeled, never rendered as a score")
    assert_true(
        "only fetches the homepage" in html,
        "excluded pillar shows its real not-measured reason",
    )
    assert_true(
        "excluded from the score, not assumed to pass" in html,
        "excluded pillar states explicitly it was not assumed to pass",
    )


def test_fix_list_renders_real_recommendations():
    html = render_report_html(_pillar_view())
    assert_true("Recommended fixes" in html, "renders the fix-list section")
    assert_true(
        "[Structured Data, up to 7 pts] Missing Organization schema" in html,
        "fix list shows the real, prioritized fix text from AuditResult.fix_list",
    )


def test_fix_list_absent_when_no_fixes():
    html = render_report_html(_view())  # no fix_list key
    assert_true("Recommended fixes" not in html, "no fix-list section when none supplied")


def test_old_points_only_categories_shape_still_works():
    html = render_report_html(_view())  # {"Structured": 18, ...} dict shape
    assert_true("Rubric breakdown" in html, "old dict-of-points categories shape still renders")
    assert_true("Structured" in html, "old shape's category names still show")


def test_cover_details_render_rating_and_prepared_for():
    v = _view()
    v["report_date"] = "2026-08-16"
    html = render_report_html(v)
    assert_true("Prepared for" in html, "cover section shows a prepared-for line")
    assert_true("North Loop Chiropractic" in html, "prepared-for line names the real client")
    assert_true("AI-Optimized" in html, "score 93 maps to the real AI-Optimized tier, not a placeholder")
    assert_true("2026-08-16" in html, "cover shows the real report date")


def test_scope_summary_counts_measured_and_excluded():
    v = _pillar_view()
    html = render_report_html(v)
    assert_true("Measured 2 of 3 rubric categories" in html, "scope line counts real measured/excluded categories")
    assert_true("Crawler Access" in html, "scope line names the real excluded category")


def test_governing_framework_absent_when_no_compliance_findings():
    html = render_report_html(_view())  # no compliance_findings key
    assert_true("Governing framework" not in html, "no governing-framework section when none supplied")


def test_governing_framework_renders_real_findings_grouped_by_area():
    v = _view()
    v["compliance_findings"] = [
        {"rule": "wcag-lang", "severity": "error", "element": "html", "message": "Missing lang attribute."},
        {"rule": "phi-unauthorized-testimonial", "severity": "error", "element": "div",
         "message": "Testimonial lacks data-hipaa-authorized marker."},
    ]
    html = render_report_html(v)
    assert_true("Governing framework" in html, "renders the governing-framework section")
    assert_true("Accessibility" in html, "groups a wcag- finding under Accessibility")
    assert_true("Patient privacy" in html, "groups a phi- finding under patient privacy")
    assert_true("Missing lang attribute" in html, "shows the real finding message")
    assert_true(
        "not a legal compliance determination" in html,
        "governing framework carries its structural-check-not-legal-advice disclosure",
    )


def test_cross_reference_section_is_honest_not_fabricated():
    html = render_report_html(_view())
    assert_true("Cross-reference against your own materials" in html, "cross-reference section always present")
    assert_true("Not yet available" in html, "cross-reference is honestly labeled not-yet-available, not faked")


def test_evidence_attribution_defaults_to_not_yet_available():
    html = render_report_html(_view())
    assert_true("Evidence-attribution triage" in html, "evidence-attribution section always present")
    assert_true(
        "citation-rigor Phase 2" in html,
        "explains the real reason it's not populated -- blocked on the lawyer relationship",
    )


def test_evidence_attribution_renders_real_citation_records():
    v = _view()
    v["citation_records"] = [{"claim": "Rated #1 clinic in the region", "attribution_status": "unsupported"}]
    html = render_report_html(v)
    assert_true("Rated #1 clinic in the region" in html, "renders a real citation record when supplied")
    assert_true("unsupported" in html, "renders the real attribution status")


def test_competitor_block_absent_by_default():
    html = render_report_html(_view())
    assert_true("Competitor comparison" not in html, "no fabricated competitor section when none supplied")


def test_competitor_block_renders_real_scores_when_supplied():
    v = _view()
    v["competitors"] = [{"name": "Rival Clinic", "score": 71}]
    html = render_report_html(v)
    assert_true("Competitor comparison" in html, "renders when real competitor data is supplied")
    assert_true("Rival Clinic" in html, "shows the real competitor name")


def test_glossary_always_renders():
    html = render_report_html(_view())
    assert_true("Glossary" in html, "glossary section always renders")
    assert_true("Publish gate" in html, "glossary defines the publish gate")
    assert_true("93-point threshold" in html,
                "glossary's publish-gate definition uses the real rubric.PUBLISH_THRESHOLD value")


def test_export_report_html_format():
    out = export_report(_view(), "html", branding={"colors": {"accent": "#0a7d33"}})
    assert_true(isinstance(out, bytes), "export_report('html') returns bytes")
    assert_true(b"<!doctype html>" in out, "html format routes through the branded renderer")


if __name__ == "__main__":
    test_renders_branded_document()
    test_measured_metric_shows_its_interval()
    test_withheld_metric_is_not_a_zero()
    test_score_gauge_and_gate()
    test_unvalidated_weights_badge_shown()
    test_refuses_dishonest_view()
    test_value_and_savings_block()
    test_value_block_absent_when_no_value()
    test_pillar_findings_render_per_category()
    test_pillar_marks_hypothesis_tier()
    test_pillar_clean_category_says_so()
    test_not_measured_pillar_shows_reason_not_a_score()
    test_fix_list_renders_real_recommendations()
    test_fix_list_absent_when_no_fixes()
    test_old_points_only_categories_shape_still_works()
    test_cover_details_render_rating_and_prepared_for()
    test_scope_summary_counts_measured_and_excluded()
    test_governing_framework_absent_when_no_compliance_findings()
    test_governing_framework_renders_real_findings_grouped_by_area()
    test_cross_reference_section_is_honest_not_fabricated()
    test_evidence_attribution_defaults_to_not_yet_available()
    test_evidence_attribution_renders_real_citation_records()
    test_competitor_block_absent_by_default()
    test_competitor_block_renders_real_scores_when_supplied()
    test_glossary_always_renders()
    test_export_report_html_format()
    print(f"{passed}/{total} passed")
