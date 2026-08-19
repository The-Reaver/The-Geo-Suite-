#!/usr/bin/env python3
# Real tests for the GEO-D3 AI-Search Readiness audit engine (Sprint days 3-5).
# These prove the engine reads real artifacts and branches on them — the thing the
# quarantined stub (hardcoded 95, inspected nothing) never did.
#
# Runnable standalone (python tests/test_audit_engine.py) and pytest-collectable,
# matching tests/test_auth_and_schema.py. No pytest/bs4 dependency.

import os
import re
import shutil
import sys
import tempfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)

from backend.app.core import rubric                         # noqa: E402
from backend.app.services.audit_engine import run_audit     # noqa: E402

FIX = os.path.join(PROJ, "tests", "fixtures")
PASS_DIR = os.path.join(FIX, "site_pass")
FAIL_DIR = os.path.join(FIX, "site_fail")
GOOD_CWV = {"lcp_s": 1.8, "inp_ms": 120, "cls": 0.05}


def _copy_site(src):
    """Copy a fixture to a throwaway temp dir so a test can mutate it safely."""
    dst = tempfile.mkdtemp(prefix="geo_audit_")
    for name in os.listdir(src):
        shutil.copy(os.path.join(src, name), os.path.join(dst, name))
    return dst


# --- 1. the passing fixture genuinely clears the publish gate -----------------

def test_site_pass_scores_and_passes():
    r = run_audit(PASS_DIR, cwv=GOOD_CWV)
    assert r.normalized_score >= 90, f"pass fixture scored {r.normalized_score}, expected >= 90"
    assert r.passed is True, "pass fixture did not pass the publish gate"
    assert r.tier == "AI-Optimized", f"tier was {r.tier!r}, expected AI-Optimized"
    # documented-only subtotal must be reported and be a real number below the total.
    assert 0 < r.documented_subtotal <= r.points_earned


# --- 2. the failing fixture is blocked and names all five defects -------------

def test_site_fail_blocked_and_itemizes_five_defects():
    r = run_audit(FAIL_DIR, cwv=GOOD_CWV)
    assert r.normalized_score < 90, f"fail fixture scored {r.normalized_score}, expected < 90"
    assert r.passed is False, "fail fixture was not blocked"
    blob = " ".join(r.fix_list).lower()
    # The five injected defects, each must surface by name in the fix list.
    assert "subtype" in blob, "defect 1 (generic LocalBusiness subtype) not named"
    assert "perplexitybot" in blob, "defect 2 (PerplexityBot blocked) not named"
    assert "phone" in blob, "defect 3 (footer phone mismatch) not named"
    assert "broken internal link" in blob, "defect 4 (broken internal link) not named"
    assert "canonical" in blob, "defect 5 (missing canonical) not named"


# --- 3. category 7 is always not_measured and excluded from the denominator ---

def test_category7_always_excluded_and_denominator():
    with_cwv = run_audit(PASS_DIR, cwv=GOOD_CWV)
    cat7 = next(c for c in with_cwv.categories if c.id == 7)
    assert cat7.status == "not_measured"
    assert cat7.earned == 0.0
    assert cat7.name in with_cwv.not_measured
    # With CWV, categories 1-6 are measured -> denominator 90 (cat 7's 10 excluded).
    assert with_cwv.points_available == 90, with_cwv.points_available
    # Without CWV, category 5 (15) also drops out -> denominator 75.
    without = run_audit(PASS_DIR, cwv=None)
    assert without.points_available == 75, without.points_available
    cat7b = next(c for c in without.categories if c.id == 7)
    assert cat7b.status == "not_measured"


# --- 4. no-CWV run marks category 5 not_measured and awards it no points ------

def test_no_cwv_defers_performance():
    r = run_audit(PASS_DIR, cwv=None)
    cat5 = next(c for c in r.categories if c.id == 5)
    assert cat5.status == "not_measured", "category 5 must not be scored without CWV data"
    assert cat5.earned == 0.0, "category 5 awarded points with no CWV data (assumed a pass)"
    assert cat5.name in r.not_measured
    assert cat5.not_measured_reason and "Core Web Vitals" in cat5.not_measured_reason


# --- 5. anti-stub: removing the JSON-LD changes category 1's score ------------

def test_reads_input_structured_data_changes_score():
    baseline = run_audit(PASS_DIR, cwv=GOOD_CWV)
    cat1_before = next(c for c in baseline.categories if c.id == 1).earned

    tmp = _copy_site(PASS_DIR)
    try:
        idx = os.path.join(tmp, "index.html")
        with open(idx, "r", encoding="utf-8") as fh:
            html = fh.read()
        # Strip every JSON-LD block entirely.
        stripped = re.sub(
            r'<script type="application/ld\+json">.*?</script>',
            "", html, flags=re.S)
        assert stripped != html, "test setup failed: no JSON-LD block was removed"
        with open(idx, "w", encoding="utf-8") as fh:
            fh.write(stripped)
        mutated = run_audit(tmp, cwv=GOOD_CWV)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    cat1_after = next(c for c in mutated.categories if c.id == 1).earned
    assert cat1_after < cat1_before, (
        f"category 1 did not change when JSON-LD was removed "
        f"({cat1_before} -> {cat1_after}) — the engine is not reading its input")
    assert mutated.normalized_score < baseline.normalized_score


# --- 6. rubric integrity: weights sum to 100 and match the reference doc ------

def test_rubric_integrity():
    rubric.assert_rubric_integrity()
    assert rubric.TOTAL_WEIGHT == 100
    # Verbatim from geo_platform_build/reference/GEO-optimization-standards.md.
    expected = {
        1: ("Structured Data and Schema", 20),
        2: ("Semantic HTML and Content Structure (GEO-SFE)", 20),
        3: ("AI Crawler Access and llms.txt", 12),
        4: ("Entity Consistency and Off-Page Authority", 13),
        5: ("Technical Performance and Core Web Vitals", 15),
        6: ("Data Integrity", 10),
        7: ("Actual AI Citation Presence", 10),
    }
    for cid, (name, weight) in expected.items():
        assert rubric.CATEGORY_NAME[cid] == name, cid
        assert rubric.CATEGORY_WEIGHT[cid] == weight, cid


# --- 7. a malformed JSON-LD block is itemized, not crashed on -----------------

def test_malformed_jsonld_is_itemized_not_fatal():
    tmp = _copy_site(PASS_DIR)
    try:
        idx = os.path.join(tmp, "index.html")
        with open(idx, "r", encoding="utf-8") as fh:
            html = fh.read()
        # Inject a broken JSON-LD block (trailing comma, unquoted) before </head>.
        broken = '<script type="application/ld+json">{ "@type": "Service", }</script>'
        html = html.replace("</head>", broken + "\n</head>")
        with open(idx, "w", encoding="utf-8") as fh:
            fh.write(html)
        r = run_audit(tmp, cwv=GOOD_CWV)  # must not raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    cat1 = next(c for c in r.categories if c.id == 1)
    assert any("malformed" in f.lower() for f in cat1.findings), \
        "malformed JSON-LD block was not itemized as a finding"


_TESTS = [
    test_site_pass_scores_and_passes,
    test_site_fail_blocked_and_itemizes_five_defects,
    test_category7_always_excluded_and_denominator,
    test_no_cwv_defers_performance,
    test_reads_input_structured_data_changes_score,
    test_rubric_integrity,
    test_malformed_jsonld_is_itemized_not_fatal,
]


if __name__ == "__main__":
    failures = 0
    for t in _TESTS:
        try:
            t()
            print("PASS  " + t.__name__)
        except AssertionError as e:
            failures += 1
            print("FAIL  " + t.__name__ + " :: " + str(e))
        except Exception as e:  # noqa: BLE001
            failures += 1
            print("ERROR " + t.__name__ + " :: " + type(e).__name__ + ": " + str(e))
    print("\n%d/%d passed" % (len(_TESTS) - failures, len(_TESTS)))
    sys.exit(1 if failures else 0)
