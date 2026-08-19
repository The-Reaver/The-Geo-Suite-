# SPEC: SPEC_CCC_M1_INGESTION
"""Standalone ingestion tests — offline fakes only."""
from __future__ import annotations

import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(PROJ, "backend")
for p in (PROJ, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.ingestion.content_parse import parse_html_document, resolve_freshness_date
from app.services.ingestion.ecosystem_crawl import crawl_platforms
from app.services.ingestion.gateways.llm_gateway import multi_model_identical
from app.services.ingestion.gateways.serp_gateway import fetch_serp
from app.services.ingestion.llm_ingest import assert_budget, run_stability_sample

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


def test_empty_vs_failure_statuses():
    ok_empty = fetch_serp("q", fake={"status": "OK", "data": {"aio": None}})
    assert_true(ok_empty["status"] == "OK", "legitimate empty AIO is OK")
    assert_true(ok_empty["data"]["aio"] is None, "OK envelope may carry aio null")
    failed = fetch_serp("q", fake={"status": "TIMEOUT", "error": "timed out"})
    assert_true(failed["status"] == "TIMEOUT", "TIMEOUT status distinct from OK")
    unconf = fetch_serp("q")
    assert_true(unconf["status"] == "AUTH_FAILED", "unconfigured credentials -> auth error envelope")


def test_prompt_identity_and_n20():
    batch = multi_model_identical(
        "same prompt",
        ["chatgpt", "gemini"],
        fakes={
            "chatgpt": {"status": "OK", "data": {"text": "a"}, "model_id": "gpt-x"},
            "gemini": {"status": "OK", "data": {"text": "b"}, "model_id": "gem-x"},
        },
    )
    assert_true(batch["prompt_identical"] is True, "multi-model asserts identical prompt")
    sample = run_stability_sample(
        "same prompt",
        ["chatgpt"],
        n_iterations=20,
        fakes_by_iter=[{"chatgpt": {"status": "OK", "data": {}, "model_id": "gpt-x"}}] * 20,
    )
    assert_true(sample["n_iterations"] == 20, "default/stability n_iterations is 20")
    assert_true(sample["iterations"][0]["results"]["chatgpt"]["model_id"] == "gpt-x", "model_id recorded")


def test_budget_exhausted():
    out = assert_budget(remaining=1.0, cost=5.0)
    assert_true(out["status"] == "BUDGET_EXHAUSTED", "over-ceiling -> BUDGET_EXHAUSTED")
    assert_true(out["allowed"] is False, "budget refuse named")


def test_blocked_crawl_not_absent():
    out = crawl_platforms(
        ["healthgrades", "zocdoc"],
        fakes={
            "healthgrades": {"status": "BLOCKED", "error": "tos"},
            "zocdoc": {"status": "OK", "data": {"exists": True}},
        },
    )
    by_p = {r["platform"]: r for r in out["listings"]}
    assert_true(by_p["healthgrades"]["status"] == "NOT_CHECKED", "BLOCKED -> NOT_CHECKED not ABSENT")
    assert_true(by_p["zocdoc"]["status"] == "PRESENT", "OK exists -> PRESENT")
    assert_true("checked 1 of 2" in out["coverage"], "coverage statement present")


def test_freshness_unknown_and_parse_failure():
    unknown = resolve_freshness_date()
    assert_true(unknown["freshness_date"] is None, "unknown freshness is NULL")
    assert_true(unknown["status"] == "UNKNOWN", "unknown status named")
    failed = parse_html_document("<html></html>", crawl_status="BLOCKED")
    assert_true(failed["classification"] == "FAILURE", "blocked crawl is extraction-miss not thin")
    assert_true(failed["status"] == "BLOCKED", "blocked status preserved")
    parsed = parse_html_document(
        '<html><script type="application/ld+json">'
        '{"@type":"MedicalClinic","dateModified":"2026-01-15"}'
        "</script></html>"
    )
    assert_true(parsed["status"] == "OK", "html parses OK")
    assert_true(
        parsed["freshness"]["freshness_date"] == "2026-01-15",
        "schema dateModified wins freshness order",
    )


if __name__ == "__main__":
    test_empty_vs_failure_statuses()
    test_prompt_identity_and_n20()
    test_budget_exhausted()
    test_blocked_crawl_not_absent()
    test_freshness_unknown_and_parse_failure()
    print(f"{passed}/{total} passed")
