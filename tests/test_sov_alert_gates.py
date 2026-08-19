"""Standalone tests for Base-path SOV alert interval gates.

SPEC: SPEC_CCC_M8_REPORTING
"""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(PROJ, "backend")
for p in (PROJ, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.sonar.alert_gates import (  # noqa: E402
    evaluate_sov_drop_alert,
    intervals_overlap,
)


def test_overlap_true_when_shared():
    assert intervals_overlap(0.10, 0.40, 0.30, 0.50) is True


def test_overlap_false_when_separated():
    assert intervals_overlap(0.10, 0.20, 0.30, 0.40) is False


def test_large_point_drop_suppressed_when_ci_overlap():
    # Classic B-2 example: 30% → 15% with wide overlapping Wilson-ish bands
    result = evaluate_sov_drop_alert(
        prev_point=0.30,
        curr_point=0.15,
        prev_ci=(0.15, 0.52),
        curr_ci=(0.05, 0.36),
        drop_pp_threshold=10.0,
    )
    assert result["fire"] is False
    assert result["reason"] == "insufficient_sample"
    assert "insufficient sample" in result["message"]


def test_separated_intervals_may_fire():
    result = evaluate_sov_drop_alert(
        prev_point=0.50,
        curr_point=0.20,
        prev_ci=(0.40, 0.60),
        curr_ci=(0.10, 0.25),
        drop_pp_threshold=10.0,
    )
    assert result["fire"] is True
    assert result["reason"] == "interval_separated_drop"


def test_small_drop_below_threshold():
    result = evaluate_sov_drop_alert(
        prev_point=0.30,
        curr_point=0.25,
        prev_ci=(0.20, 0.40),
        curr_ci=(0.15, 0.35),
        drop_pp_threshold=10.0,
    )
    assert result["fire"] is False
    assert result["reason"] == "below_threshold"


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  " + t.__name__)
            passed += 1
        except AssertionError as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
        except Exception as e:
            print("ERROR " + t.__name__ + ": " + type(e).__name__ + ": " + str(e))
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
