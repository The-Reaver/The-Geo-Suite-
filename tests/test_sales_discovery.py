# SPEC: SPEC_CCC_SALES_DISCOVERY
"""Standalone sales discovery tests."""
from __future__ import annotations

import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(PROJ, "backend")
for p in (PROJ, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.sales.citations_registry import render_stat
from app.services.sales.discovery_audit import (
    build_prompt_set,
    run_visibility_audit,
    verdict,
)
from app.services.sales.revenue_math import estimate_lost_revenue

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


def test_insufficient_data_not_invisible():
    audit = {"ok_engines": 0, "cited_engines": 0, "seen_engines": 0}
    assert_true(
        verdict(audit) == "INSUFFICIENT_DATA",
        "three engine errors / ok<3 -> INSUFFICIENT_DATA not INVISIBLE",
    )
    biz = {"name": "Hope Clinic", "domains": ["hope.example"], "aliases": ["Hope Clinic"]}
    out = run_visibility_audit(
        biz,
        engines=["chatgpt", "perplexity", "gemini"],
        engine_responses={},  # all missing → UNAVAILABLE
    )
    assert_true(out["verdict"] == "INSUFFICIENT_DATA", "missing engines -> INSUFFICIENT_DATA")


def test_invisible_when_zero_mentions():
    biz = {"name": "Hope Clinic", "domains": ["hope.example"], "aliases": ["Hope Clinic"]}
    responses = {
        eng: {
            "status": "OK",
            "response_text": "No clinics named here.",
            "cited_urls": [],
        }
        for eng in ("chatgpt", "perplexity", "gemini", "claude", "bing")
    }
    out = run_visibility_audit(biz, engines=list(responses), engine_responses=responses)
    assert_true(out["verdict"] == "INVISIBLE", "zero mentions across ok engines -> INVISIBLE")


def test_high_risk_condition_refused():
    built = build_prompt_set({
        "name": "Hope",
        "city": "Austin",
        "condition": "autism",
        "service": "HBOT",
    })
    assert_true(built["ok"] is False, "high-risk condition refused before dispatch")
    assert_true(
        "autism" in (built.get("term") or "") or "autism" in built["reason"],
        f"refusal names the term got {built}",
    )


def test_lost_revenue_interval_and_missing():
    ok = estimate_lost_revenue(
        {"v": 0.0},
        benchmarks={
            "S": (1000, 2000),
            "a": (0.1, 0.2),
            "c": (0.05, 0.1),
            "t": (200, 400),
        },
    )
    assert_true(ok["status"] == "OK", "complete benchmarks -> OK")
    assert_true(ok["lost_lo"] < ok["lost_hi"], "lost_lo < lost_hi")
    assert_true(
        "lost_lo" in ok and "lost_hi" in ok and not isinstance(ok.get("lost"), (int, float)),
        "never a bare scalar lost field",
    )

    missing = estimate_lost_revenue({"v": 0.0}, benchmarks={"S": (1, 2), "a": (0.1, 0.2)})
    assert_true(
        missing["status"] == "INSUFFICIENT_BENCHMARKS",
        "missing benchmark -> INSUFFICIENT_BENCHMARKS",
    )
    assert_true(
        "c" in missing["missing"] and "t" in missing["missing"],
        "names missing terms c and t",
    )

    full = estimate_lost_revenue(
        {"v": 1.0},
        benchmarks={
            "S": (1000, 2000),
            "a": (0.1, 0.2),
            "c": (0.05, 0.1),
            "t": (200, 400),
        },
    )
    assert_true(
        full["lost_lo"] == 0 and full["lost_hi"] == 0,
        "v=1.0 yields zero lost revenue bounds",
    )


def test_unsourced_stats_withheld():
    rendered = render_stat("ai_local_discovery_share")
    assert_true(rendered["shown"] is False, "unsourced stat not shown")
    assert_true(
        rendered["flag"] == "WITHHELD",
        "unsourced stat flagged WITHHELD",
    )
    assert_true(
        "no resolvable primary URL" in (rendered.get("reason") or ""),
        "withhold reason names missing URL",
    )


if __name__ == "__main__":
    test_insufficient_data_not_invisible()
    test_invisible_when_zero_mentions()
    test_high_risk_condition_refused()
    test_lost_revenue_interval_and_missing()
    test_unsourced_stats_withheld()
    print(f"{passed}/{total} passed")
