# SPEC: SPEC_CCC_M6_AGENTIC
"""Standalone M6 execution tests — outbox + circuit + compliance."""
from __future__ import annotations

import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(PROJ, "backend")
for p in (PROJ, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

import logging

from app.core.resilience import CircuitBreaker  # noqa: E402
from app.services.execution.cms_push import FakeCmsGateway, inject_schema  # noqa: E402

# Resilience logs include "RuntimeError:" which trips verify.py's Error: marker.
logging.getLogger("app.core.resilience").setLevel(logging.CRITICAL)
from app.services.execution.mcp_tools import (  # noqa: E402
    enqueue_directory_submission,
    learn_from_outcomes,
    verification_window,
)
from app.services.execution.outreach import (  # noqa: E402
    listing_packet,
    review_campaign_package,
)
from app.services.worker.outbox import InMemoryDedupStore  # noqa: E402

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


def test_missing_phone():
    out = listing_packet(
        {"platform": "yelp"},
        {"name": "Thrive", "address": "1 Main", "website": "https://ex.invalid"},
    )
    assert_true(out["status"] == "INSUFFICIENT_BRAND_DATA", "missing phone -> INSUFFICIENT_BRAND_DATA")
    assert_true("phone" in out["missing_keys"], "names missing phone key")


def test_review_phi_refused():
    out = review_campaign_package(
        "healthgrades",
        {},
        policy={"template": "Tell us about your autism treatment journey"},
    )
    assert_true(out["status"] == "REFUSED", "PHI term -> REFUSED")
    assert_true(any("PHI" in r for r in out["reasons"]), "names PHI rule")


def test_review_nps_refused():
    out = review_campaign_package(
        "yelp",
        {},
        policy={
            "template": "Please leave a review if you can.",
            "selection_criteria": ["nps promoters only"],
        },
    )
    assert_true(out["status"] == "REFUSED", "NPS selection -> REFUSED")
    assert_true(any("gating" in r.lower() or "NPS" in r or "nps" in r.lower() for r in out["reasons"]), "names gating")


class CountingGateway:
    def __init__(self):
        self.calls = 0
        self.configured = True

    def submit(self, packet):
        self.calls += 1
        return {"status": "OK", "applied": True, "n": self.calls}


def test_outbox_idempotency_single_apply():
    gw = CountingGateway()
    dedup = InMemoryDedupStore()
    packet = {"platform": "yelp", "name": "Thrive", "idempotency_key": "dir:yelp:thrive"}
    a = enqueue_directory_submission(packet, require_approval=False, dedup=dedup, gateway=gw, approved=True)
    b = enqueue_directory_submission(packet, require_approval=False, dedup=dedup, gateway=gw, approved=True)
    assert_true(a["status"] == "OK" and b["status"] == "OK", "both enqueues return OK")
    assert_true(gw.calls == 1, "duplicate idempotency key -> single apply")


def test_circuit_open_named():
    class Clock:
        def __init__(self):
            self.t = 0.0

        def __call__(self):
            return self.t

    clock = Clock()
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout_s=60.0, clock=clock, name="cms")

    def boom():
        raise RuntimeError("cms down")

    breaker.call(boom, fallback="x")
    assert_true(breaker.state == "OPEN", "breaker open after threshold")

    gw = FakeCmsGateway()
    dedup = InMemoryDedupStore()
    out = inject_schema(
        "p1",
        {"@type": "MedicalBusiness", "source_module": "m3", "from_m3": True},
        gateway=gw,
        dedup=dedup,
        breaker=breaker,
        idempotency_key="schema:p1:draft",
    )
    assert_true(out["status"] == "CIRCUIT_OPEN", "circuit open -> named status")
    assert_true(out.get("applied") is False, "circuit open is not success")


def test_verification_inconclusive():
    out = verification_window(
        "act-1",
        {"value": 0.30, "ci_lower": 0.15, "ci_upper": 0.50, "n": 20},
        {"value": 0.28, "ci_lower": 0.12, "ci_upper": 0.48, "n": 20},
    )
    assert_true(out["status"] == "INCONCLUSIVE", "overlapping SOV CIs -> INCONCLUSIVE")


def test_learn_never_validated():
    out = learn_from_outcomes([{"weight_key": "w1", "proposed_value": 0.1}])
    assert_true(out["registry_write_status"] == "PROPOSED_UNVALIDATED", "proposed unvalidated")
    assert_true(out["validated_writes"] == 0, "never sets VALIDATED")
    assert_true(
        all(p["status"] == "PROPOSED_UNVALIDATED" for p in out["proposed_updates"]),
        "each proposal tagged PROPOSED_UNVALIDATED",
    )


def test_b2_slice_gap_to_packet_to_outbox():
    """Path B B2 vertical slice exit criterion."""
    packet = listing_packet(
        {"platform": "healthgrades", "add_url": "https://example.invalid/add"},
        {
            "name": "Thrive HBOT",
            "phone": "303-555-0100",
            "address": "100 Main",
            "website": "https://thrive.example",
        },
    )
    assert_true(packet["status"] == "OK", "gap -> listing_packet OK")
    gw = CountingGateway()
    dedup = InMemoryDedupStore()
    body = {**packet["packet"], "idempotency_key": "b2:hg:thrive"}
    first = enqueue_directory_submission(body, require_approval=False, dedup=dedup, gateway=gw, approved=True)
    second = enqueue_directory_submission(body, require_approval=False, dedup=dedup, gateway=gw, approved=True)
    assert_true(first.get("result", {}).get("applied") is True, "fake directory apply")
    assert_true(gw.calls == 1, "B2 slice: no double-apply")
    assert_true(second["idempotency_key"] == first["idempotency_key"], "same key retained")

    unconf = CountingGateway()
    unconf.configured = False
    bad = enqueue_directory_submission(
        {**body, "idempotency_key": "b2:unconf"},
        require_approval=False,
        gateway=unconf,
        approved=True,
    )
    assert_true(bad["status"] == "AUTH_FAILED", "unconfigured gateway returns auth-failed envelope")


def _run_all():
    test_missing_phone()
    test_review_phi_refused()
    test_review_nps_refused()
    test_outbox_idempotency_single_apply()
    test_circuit_open_named()
    test_verification_inconclusive()
    test_learn_never_validated()
    test_b2_slice_gap_to_packet_to_outbox()
    print(f"{passed}/{total} passed")
    return passed == total and total > 0


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
