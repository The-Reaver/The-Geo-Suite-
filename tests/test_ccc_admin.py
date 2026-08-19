# SPEC: SPEC_CCC_M9_ADMIN
"""Standalone M9 admin tests — offline, real N/N."""
from __future__ import annotations

import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(PROJ, "backend")
for p in (PROJ, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.admin.prompt_clustering import (  # noqa: E402
    cluster_prompts,
    ingest_prompts,
    select_representatives,
    tag_journey_stage,
)
from app.services.admin.workspace import (  # noqa: E402
    _reset_store_for_tests,
    budget_status,
    create_workspace,
    list_workspaces,
    path_a_data_flow,
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


def test_empty_ingest():
    out = ingest_prompts([])
    assert_true(out["status"] == "EMPTY", "empty ingest yields EMPTY")
    assert_true(out["prompts"] == [], "empty ingest has no seeded fake pool")


def test_lexical_clustering_multi_intent():
    prompts = [
        "what is hyperbaric oxygen therapy",
        "hbot benefits explained",
        "hbot cost near me",
        "book hbot appointment denver",
        "hbot vs surgery alternatives",
        "compare hbot options",
    ]
    out = cluster_prompts(prompts, embedder=None)
    assert_true(out["method"] == "lexical_fallback", "no embedder tags lexical_fallback")
    assert_true(out["weights_status"] == "UNVALIDATED", "weights UNVALIDATED")
    assert_true(len(out["clusters"]) >= 1, "multi-intent fixture yields >=1 cluster")


def test_representatives_from_membership():
    cluster = {
        "cluster_id": "c0",
        "members": [
            "what is hbot",
            "hbot cost near me",
            "hbot benefits explained",
            "book hbot clinic",
            "hbot review recommend",
            "random filler phrase about oxygen",
        ],
    }
    reps = select_representatives(cluster, k=5)
    assert_true(len(reps) <= 5, "representative set size <= registry k")
    members = set(cluster["members"])
    assert_true(
        all(r["prompt"] in members and r["from_membership"] for r in reps),
        "every representative drawn from cluster membership",
    )


def test_untagged_journey():
    stage = tag_journey_stage({"members": ["zzzzzyxq unique nonsense tokens"]})
    assert_true(stage == "UNTAGGED", "untaggable prompt -> UNTAGGED")


def test_budget_exhausted():
    st = budget_status(
        "ws1",
        usage={"openai": 100.0, "gemini": 10.0},
        caps={"openai": 100.0, "gemini": 100.0},
    )
    assert_true(st["status"] == "BUDGET_EXHAUSTED", "100% cap -> BUDGET_EXHAUSTED")
    assert_true(st["throttle"] is True, "throttle flag set at exhaust")
    assert_true(st["engines"]["openai"]["status"] == "BUDGET_EXHAUSTED", "engine status named")
    unknown = budget_status("ws1", usage={}, caps={"openai": 50})
    assert_true(
        unknown["engines"]["openai"]["status"] == "UNKNOWN_USAGE",
        "missing usage is not invented as 0 spend",
    )


def test_path_a_flow_no_live_m5():
    flow = path_a_data_flow()
    labels = {n["id"]: n for n in flow["nodes"]}
    assert_true("M2" in labels and "M3" in labels, "includes Sonar and CII")
    assert_true("M4" in labels and "M8" in labels and "Sales" in labels, "Footprint/Reporting/Sales")
    edge_pairs = {(e["from"], e["to"]) for e in flow["edges"]}
    assert_true(("M1", "M2") in edge_pairs, "M1->M2 edge")
    assert_true(("M8", "Sales") in edge_pairs, "Reporting->Sales edge")
    assert_true(labels["M5"]["status"] == "DEFERRED", "M5 is DEFERRED not live")
    assert_true(
        ("M5", "M8") not in edge_pairs and ("M8", "M5") not in edge_pairs,
        "does not claim live M5 Granger edges",
    )
    assert_true(any("Granger" in a.get("reason", "") for a in flow["absent_edges"]), "absent edges named")


def test_zero_workspaces_honest_empty():
    _reset_store_for_tests()
    empty = list_workspaces()
    assert_true(empty == [], "zero workspaces -> honest empty list")
    create_workspace({"workspace_id": "w1", "name": "Thrive"})
    assert_true(len(list_workspaces()) == 1, "created workspace listed")


def _run_all():
    test_empty_ingest()
    test_lexical_clustering_multi_intent()
    test_representatives_from_membership()
    test_untagged_journey()
    test_budget_exhausted()
    test_path_a_flow_no_live_m5()
    test_zero_workspaces_honest_empty()
    print(f"{passed}/{total} passed")
    return passed == total and total > 0


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
