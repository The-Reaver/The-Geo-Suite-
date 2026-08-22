"""Tests for cfr_watch.py's diff_baseline() -- pure comparison logic,
no live eCFR call. The HTTP-fetch layer (fetch_live_amendment_date) is
verified separately, against real GitHub Actions runner output, since
this sandbox cannot reach ecfr.gov (EGRESS_BLOCKED)."""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)

sys.path.insert(0, os.path.join(PROJ, "backend", "scripts"))
import cfr_watch  # noqa: E402


def _baseline(parts):
    return {"parts": parts}


def _part(title=16, part="255", law="Test law", citation_file="test.md", last_known_amendment_date=None):
    return {
        "title": title, "part": part, "law": law,
        "citation_file": citation_file, "last_known_amendment_date": last_known_amendment_date,
    }


def test_unchanged_when_live_matches_baseline():
    baseline = _baseline([_part(last_known_amendment_date="2024-01-01")])
    live = {"16:255": ("2024-01-01", None)}
    rows = cfr_watch.diff_baseline(baseline, live)
    assert len(rows) == 1
    assert rows[0]["status"] == "unchanged"


def test_changed_when_live_differs_from_baseline():
    baseline = _baseline([_part(last_known_amendment_date="2024-01-01")])
    live = {"16:255": ("2025-06-15", None)}
    rows = cfr_watch.diff_baseline(baseline, live)
    assert rows[0]["status"] == "changed"
    assert rows[0]["baseline_date"] == "2024-01-01"
    assert rows[0]["live_date"] == "2025-06-15"


def test_unseeded_when_baseline_date_is_null():
    baseline = _baseline([_part(last_known_amendment_date=None)])
    live = {"16:255": ("2025-06-15", None)}
    rows = cfr_watch.diff_baseline(baseline, live)
    assert rows[0]["status"] == "unseeded"


def test_fetch_failed_reported_distinctly_from_a_real_change():
    # A fetch error must never be silently reported as "unchanged" (would
    # hide a real API problem) or "changed" (would fabricate a finding).
    baseline = _baseline([_part(last_known_amendment_date="2024-01-01")])
    live = {"16:255": (None, "request failed: timeout")}
    rows = cfr_watch.diff_baseline(baseline, live)
    assert rows[0]["status"] == "fetch_failed"
    assert rows[0]["error"] == "request failed: timeout"


def test_multiple_parts_are_independent():
    baseline = _baseline([
        _part(title=16, part="255", last_known_amendment_date="2024-01-01"),
        _part(title=21, part="801", last_known_amendment_date="2024-01-01"),
    ])
    live = {
        "16:255": ("2024-01-01", None),  # unchanged
        "21:801": ("2025-03-01", None),  # changed
    }
    rows = cfr_watch.diff_baseline(baseline, live)
    by_part = {r["part"]: r for r in rows}
    assert by_part["255"]["status"] == "unchanged"
    assert by_part["801"]["status"] == "changed"


def test_real_baseline_file_loads_and_has_the_four_expected_parts():
    # Guards against a malformed/renamed baseline file breaking the
    # watcher silently -- proves the real committed file this repo ships
    # is genuinely loadable and shaped as cfr_watch.py expects.
    baseline = cfr_watch.load_baseline()
    parts = {(p["title"], p["part"]) for p in baseline["parts"]}
    assert parts == {(16, "255"), (16, "318"), (21, "801"), (45, "164")}
    for p in baseline["parts"]:
        assert p["citation_file"]
        # Every part starts unseeded (null) until a real GitHub Actions
        # run's observed date is committed -- see the baseline file's own
        # _provenance note for why nothing here is fabricated offline.
        assert p["last_known_amendment_date"] is None or isinstance(p["last_known_amendment_date"], str)


def test_format_summary_flags_changed_and_unseeded_parts():
    rows = [
        {"title": 16, "part": "255", "law": "L1", "baseline_date": "2024-01-01",
         "live_date": "2025-01-01", "status": "changed", "error": None},
        {"title": 21, "part": "801", "law": "L2", "baseline_date": None,
         "live_date": "2025-01-01", "status": "unseeded", "error": None},
    ]
    out = cfr_watch.format_summary(rows)
    assert "CHANGED" in out
    assert "no baseline yet" in out.lower() or "1 part(s) have no baseline yet" in out


if __name__ == "__main__":
    tests = [
        test_unchanged_when_live_matches_baseline,
        test_changed_when_live_differs_from_baseline,
        test_unseeded_when_baseline_date_is_null,
        test_fetch_failed_reported_distinctly_from_a_real_change,
        test_multiple_parts_are_independent,
        test_real_baseline_file_loads_and_has_the_four_expected_parts,
        test_format_summary_flags_changed_and_unseeded_parts,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  " + t.__name__)
            passed += 1
        except AssertionError as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
    print(f"\n{passed}/{len(tests)} passed")
    if passed < len(tests):
        sys.exit(1)
