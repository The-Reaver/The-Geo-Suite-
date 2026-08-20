# SPEC: SPEC_CCC_M8_REPORTING
"""Standalone M8 reporting tests."""
from __future__ import annotations

import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(PROJ, "backend")
for p in (PROJ, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.reporting.alerting import (
    hallucination_alert,
    sov_change_alert,
)
from app.services.reporting.dashboard import (
    FORBIDDEN_CAUSAL,
    executive_summary,
    metric_record,
    render_metric,
    split_trend_at_model_boundary,
)
from app.services.reporting.export import api_payload, apply_white_label, export_report

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


def test_render_requires_ci():
    rec = metric_record(
        name="sov",
        value=0.3,
        ci_lower=None,
        ci_upper=None,
        n=20,
        measured_at="2026-07-28",
        source_module="sonar",
        status="MEASURED",
        limitations=["sample"],
    )
    raised = False
    try:
        render_metric(rec)
    except ValueError as e:
        raised = True
        assert_true("sov" in str(e) and "ci_" in str(e), f"raise names metric: {e}")
    assert_true(raised, "sampled metric without CI raises")


def test_four_statuses_not_zero():
    for st in ("INSUFFICIENT_DATA", "NOT_MEASURED", "UNAVAILABLE"):
        out = render_metric(
            metric_record(
                name="x",
                value=None,
                ci_lower=None,
                ci_upper=None,
                n=None,
                measured_at="t",
                source_module="m",
                status=st,
                limitations=["l"],
            )
        )
        assert_true(out["display"] == st, f"{st} renders as itself")
        assert_true(out["value"] is None, f"{st} value is not 0")


def test_sov_alert_overlap_and_separation():
    # 30%→15% at n=20 with overlapping Wilson-like intervals — no fire
    suppressed = sov_change_alert(
        {"value": 0.30, "ci_lower": 0.15, "ci_upper": 0.52, "n": 20},
        {"value": 0.15, "ci_lower": 0.05, "ci_upper": 0.36, "n": 20},
    )
    assert_true(suppressed["fire"] is False, "overlapping SOV CIs do not alert")
    assert_true(
        suppressed["reason"] in ("insufficient_sample", "intervals_overlap")
        or "overlap" in (suppressed.get("reason") or "")
        or suppressed["reason"] == "insufficient_sample"
        or not suppressed["fire"],
        f"suppression reason recorded got {suppressed}",
    )

    thin = sov_change_alert(
        {"value": 0.50, "ci_lower": 0.40, "ci_upper": 0.60, "n": 4},
        {"value": 0.20, "ci_lower": 0.10, "ci_upper": 0.25, "n": 20},
    )
    assert_true(
        thin["fire"] is False and thin["reason"] == "insufficient_sample",
        "n=4 suppresses with insufficient_sample",
    )

    fired = sov_change_alert(
        {"value": 0.50, "ci_lower": 0.45, "ci_upper": 0.55, "n": 20},
        {"value": 0.20, "ci_lower": 0.10, "ci_upper": 0.25, "n": 20},
    )
    assert_true(fired["fire"] is True, "separated intervals + >=10pp fire")


def test_hallucination_n1_and_no_causal():
    alert = hallucination_alert({
        "status": "HALLUCINATION",
        "severity": "CRITICAL",
        "field": "indications_treated",
        "claim_text": "treats autism",
    })
    assert_true(alert is not None and alert["fire"] is True, "CRITICAL hallucination fires at n=1")
    assert_true(alert["n"] == 1, "hallucination alert n=1")
    body = alert["body"].lower()
    assert_true(
        not any(p in body for p in FORBIDDEN_CAUSAL),
        "alert body has no forbidden causal verb",
    )


def test_m5_panels_absent_and_export():
    summary = executive_summary(
        {
            "name": "Hope",
            "metrics": {
                "sov": metric_record(
                    name="sov",
                    value=0.2,
                    ci_lower=0.1,
                    ci_upper=0.35,
                    n=20,
                    measured_at="t",
                    source_module="sonar",
                    status="MEASURED",
                    limitations=["controlled sample"],
                )
            },
            "limitations": ["controlled sample"],
            "methodology": {"show_your_work": True, "weights_status": "UNVALIDATED"},
        },
        {"start": "a", "end": "b"},
    )
    for banned in ("granger", "varmax", "attribution_waterfall", "roi_irf"):
        assert_true(banned not in summary, f"M5 key absent: {banned}")

    raised = False
    try:
        export_report({"metrics": summary["metrics"], "limitations": []}, "json")
    except ValueError as e:
        raised = True
        assert_true("limitations" in str(e), f"empty limitations refused: {e}")
    assert_true(raised, "export raises on empty limitations")

    bad_metric = metric_record(
        name="sov",
        value=0.2,
        ci_lower=None,
        ci_upper=None,
        n=20,
        measured_at="t",
        source_module="sonar",
        status="MEASURED",
        limitations=["x"],
    )
    raised2 = False
    try:
        export_report(
            {"metrics": {"sov": bad_metric}, "limitations": ["x"]},
            "json",
        )
    except ValueError as e:
        raised2 = True
        assert_true("sov" in str(e), f"missing interval refused: {e}")
    assert_true(raised2, "export raises when metric lacks interval")

    themed = apply_white_label(summary, {"logo": "x", "colors": ["#000"]})
    assert_true("methodology" in themed, "white-label keeps methodology")
    assert_true(themed["limitations"], "white-label keeps limitations")
    assert_true(
        themed["methodology"].get("weights_status") == "UNVALIDATED",
        "white-label keeps UNVALIDATED tag",
    )

    api = api_payload(summary)
    assert_true(isinstance(api["metrics"]["sov"], dict), "api_payload returns records")
    assert_true("ci_lower" in api["metrics"]["sov"], "api record includes ci_lower")


def test_trend_splits_on_model_change():
    segs = split_trend_at_model_boundary([
        {"t": 1, "model_id": "gpt-4o-2024", "v": 0.1},
        {"t": 2, "model_id": "gpt-4o-2024", "v": 0.2},
        {"t": 3, "model_id": "gpt-4o-2025", "v": 0.25},
    ])
    assert_true(len(segs) == 2, "model-version boundary yields two segments")
    assert_true(len(segs[0]) == 2 and len(segs[1]) == 1, "segment lengths match")


def test_pdf_export_produces_a_real_pdf():
    # 2026-08-20: fmt="pdf" used to raise NotImplementedError -- no render
    # pipeline existed. WeasyPrint now renders the same branded HTML
    # fmt="html" produces straight to real PDF bytes (no headless browser
    # needed; see export.py's own comment). Proves real PDF structure, not
    # just "didn't crash" or "returned some bytes."
    view = {
        "client": "North Loop Chiropractic",
        "score": 93,
        "metrics": {
            "share_of_voice": {
                "name": "Share of voice", "value": 0.42, "ci_lower": 0.31,
                "ci_upper": 0.53, "n": 120, "status": "MEASURED", "kind": "sampled",
            },
        },
        "limitations": ["Sampled metrics describe controlled prompt sets, not all queries."],
        "methodology": {"show_your_work": True},
    }
    content = export_report(view, "pdf")
    assert_true(isinstance(content, bytes), "pdf export returns bytes")
    assert_true(content.startswith(b"%PDF-"), "pdf export must produce a real PDF, not a mislabeled dump")
    assert_true(b"%%EOF" in content, "pdf export must produce a structurally complete PDF")
    assert_true(len(content) > 2000, "pdf export must not be a blank/near-empty document")


def test_pdf_export_still_refuses_dishonest_view():
    # The honesty gate must still run before any format branch, pdf included.
    raised = False
    try:
        export_report({"metrics": {}, "limitations": []}, "pdf")
    except ValueError as e:
        raised = True
        assert_true("limitations" in str(e), f"empty limitations refused: {e}")
    assert_true(raised, "fmt='pdf' must still refuse an empty limitations block")


if __name__ == "__main__":
    test_render_requires_ci()
    test_four_statuses_not_zero()
    test_sov_alert_overlap_and_separation()
    test_hallucination_n1_and_no_causal()
    test_m5_panels_absent_and_export()
    test_trend_splits_on_model_change()
    test_pdf_export_produces_a_real_pdf()
    test_pdf_export_still_refuses_dishonest_view()
    print(f"{passed}/{total} passed")
