# SPEC: SPEC_CCC_SALES_DISCOVERY (prospect source)
"""Standalone prospect-source tests. Offline: every case injects rows or calls
the live adapter with no env, so the battery never touches the network.

Proves the honesty invariant that motivated the build (GEO Brain Trust item 6):
discovery supplies the prospect list and its discoverable facts, and NEVER
fabricates the qualification. A freshly discovered candidate scores INCOMPLETE.
"""
from __future__ import annotations

import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(PROJ, "backend")
for p in (PROJ, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.sales.prospect_source import (  # noqa: E402
    NEEDS_CONFIRMATION,
    discover,
    discover_and_rank,
    http_places_source,
    normalize_place,
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


_ROWS = [
    {
        "name": "North Loop Chiropractic",
        "street": "100 Main St",
        "city": "Austin",
        "state": "TX",
        "website": "https://www.northloopchiro.com/",
        "phone": "512-555-0100",
        "categories": ["Chiropractor", "Wellness center"],
        "rating": 4.7,
        "review_count": 212,
        "place_id": "PID-1",
        "source": "fixture",
    },
    {
        # duplicate of row 1 by place_id, must collapse
        "name": "North Loop Chiropractic (relisted)",
        "city": "Austin",
        "place_id": "PID-1",
    },
    {
        "name": "Riverside Vet Hospital",
        "locality": "Austin",
        "region": "TX",
        "domain": "riversidevet.com",
        "categories": "Veterinary, Animal hospital",
        "place_id": "PID-2",
    },
    {
        # nameless listing must be dropped
        "name": "",
        "city": "Austin",
        "place_id": "PID-3",
    },
]


def test_normalize_discovers_only_real_facts():
    cand = normalize_place(_ROWS[0])
    d = cand["discovered"]
    assert_true(d["name"] == "North Loop Chiropractic", "keeps the discovered name")
    assert_true(d["locality"] == "Austin", "maps city -> locality")
    assert_true(d["region"] == "TX", "maps state -> region")
    assert_true(d["domain"] == "northloopchiro.com", "derives domain from website, strips www")
    assert_true(d["telephone"] == "512-555-0100", "maps phone -> telephone")
    assert_true(cand["auditable"] is True, "a candidate with a site is auditable")
    assert_true(
        list(cand["needs_confirmation"]) == list(NEEDS_CONFIRMATION),
        "names exactly the four undiscoverable keys to confirm",
    )


def test_inferred_type_is_not_fed_to_the_score():
    cand = normalize_place(_ROWS[0])
    assert_true(
        cand["inferred_practice_type"] == "chiropractic",
        "infers practice type from the listing category",
    )
    # ...but the inference must not qualify the lead on its own.
    out = discover_and_rank({"business_type": "chiropractor", "locality": "Austin"}, rows=_ROWS)
    first = next(c for c in out["candidates"] if c["discovered"]["place_id"] == "PID-1")
    assert_true(
        first["score"]["tier"] == "INCOMPLETE",
        "inferred type does NOT move the lead out of INCOMPLETE",
    )


def test_discover_dedupes_and_drops_nameless():
    out = discover({"business_type": "clinic", "locality": "Austin"}, rows=_ROWS)
    assert_true(out["count"] == 2, "PID-1 duplicate collapsed and nameless PID-3 dropped -> 2")
    ids = {c["discovered"]["place_id"] for c in out["candidates"]}
    assert_true(ids == {"PID-1", "PID-2"}, "keeps the two distinct real listings")


def test_fresh_candidates_are_incomplete_by_design():
    out = discover_and_rank({"business_type": "clinic", "locality": "Austin"}, rows=_ROWS)
    assert_true(
        all(c["score"]["tier"] == "INCOMPLETE" for c in out["candidates"]),
        "every freshly discovered lead is INCOMPLETE (qualification not scraped)",
    )
    assert_true(
        out["needs_confirmation_count"] == out["count"],
        "needs_confirmation_count matches the discovered count",
    )
    reasons = " ".join(out["candidates"][0]["score"]["reasons"]).lower()
    assert_true("missing required key" in reasons, "the INCOMPLETE reason names the missing keys")


def test_supplied_audit_does_not_fabricate_qualification():
    # Even with a measured site audit, fit is unknown, so the lead stays
    # INCOMPLETE rather than being rounded up to a real tier.
    out = discover_and_rank(
        {"business_type": "clinic", "locality": "Austin"},
        rows=_ROWS,
        audits={"Riverside Vet Hospital": {"accessibility_gap": 30, "visibility_gap": 35}},
    )
    vet = next(c for c in out["candidates"] if c["discovered"]["name"] == "Riverside Vet Hospital")
    assert_true(
        vet["score"]["tier"] == "INCOMPLETE",
        "a site audit alone never qualifies an unconfirmed lead",
    )


def test_empty_query_yields_honest_empty():
    out = discover({"business_type": "clinic", "locality": "Nowhere"}, rows=[])
    assert_true(out["status"] == "EMPTY", "no listings -> EMPTY status, not a fabricated list")
    assert_true(out["count"] == 0, "no candidates on an empty pull")


def test_live_source_disabled_offline():
    # Guarantee the offline state regardless of the runner's environment.
    for var in ("GEO_PLACES_API_KEY", "GEO_PLACES_API_URL"):
        os.environ.pop(var, None)
    result = http_places_source({"business_type": "chiropractor", "locality": "Austin"})
    assert_true(result["status"] == "DISABLED", "unconfigured live source is DISABLED, not an error")
    assert_true(result["rows"] == [], "DISABLED source returns zero rows")
    assert_true(
        "GEO_PLACES_API_KEY" in result["reason"],
        "the DISABLED reason tells the operator exactly what to set",
    )


if __name__ == "__main__":
    test_normalize_discovers_only_real_facts()
    test_inferred_type_is_not_fed_to_the_score()
    test_discover_dedupes_and_drops_nameless()
    test_fresh_candidates_are_incomplete_by_design()
    test_supplied_audit_does_not_fabricate_qualification()
    test_empty_query_yields_honest_empty()
    test_live_source_disabled_offline()
    print(f"{passed}/{total} passed")
