#!/usr/bin/env python3
# Real tests for the facts-persistence layer (facts_repository).
# Prove: only confirmed facts feed generation; EAV rows map to BusinessFacts;
# NAP JSONB fills gaps; missing required facts fail loudly; and the by-site-id
# audit now runs end to end from stored rows to a score >= 90.
# Runnable standalone and pytest-collectable. No pytest/bs4 dependency.

import json
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)

from backend.app.repositories.facts_repository import (            # noqa: E402
    map_to_business_facts, InMemoryFactsRepository, FactsNotConfirmed,
    _confirmed, _nap_value)
from backend.app.services import audit_engine                      # noqa: E402

GOOD_CWV = {"lcp_s": 1.8, "inp_ms": 120, "cls": 0.05}
SITE_ID = "11111111-1111-1111-1111-111111111111"


def _full_rows():
    return [
        {"field_name": "subtype", "field_value": "Dentist", "confirmed": True},
        {"field_name": "service_areas",
         "field_value": json.dumps(["Portland", "Beaverton", "Lake Oswego"]), "confirmed": True},
        {"field_name": "services", "field_value": json.dumps([
            {"name": "Preventive cleanings", "description": "Exams, digital X-rays, and hygiene visits."},
            {"name": "Dental implants", "description": "Permanent tooth replacement placed in-house."},
            {"name": "Emergency care", "description": "Same-day appointments for pain and breaks."}]),
         "confirmed": True},
        {"field_name": "faqs", "field_value": json.dumps([
            {"question": "Do you accept new patients?", "answer": "Yes, and most PPO plans."},
            {"question": "Do you offer emergency care?", "answer": "Yes, same-day Monday to Friday."}]),
         "confirmed": True},
        {"field_name": "credentials", "field_value": json.dumps(["ADA membership"]), "confirmed": True},
        {"field_name": "same_as", "field_value": json.dumps(["https://g.page/cedar-ridge-dental"]),
         "confirmed": True},
        {"field_name": "hours", "field_value": json.dumps(["Mon-Fri 8:00-17:00"]), "confirmed": True},
        {"field_name": "rating", "field_value": json.dumps({"value": 4.9, "count": 218}), "confirmed": True},
        {"field_name": "last_updated", "field_value": "2026-07-24", "confirmed": True},
    ]


def _site():
    return {"id": SITE_ID, "client_id": "c1", "domain": "cedarridgedental.example"}


def _client():
    return {"id": "c1", "business_name": "Cedar Ridge Dental",
            "nap": {"street": "1200 Cedar Road", "city": "Portland", "state": "OR",
                    "zip": "97201", "phone": "+1-503-555-0142"}}


def _repo(rows=None):
    return InMemoryFactsRepository({SITE_ID: _site()}, {"c1": _client()},
                                   {"c1": _full_rows() if rows is None else rows})


# 1. Confirmed-only invariant — an unconfirmed fact does not exist.
def test_unconfirmed_facts_are_ignored():
    rows = _full_rows() + [{"field_name": "tagline", "field_value": "DO NOT USE", "confirmed": False}]
    collapsed = _confirmed(rows)
    assert "tagline" not in collapsed
    assert collapsed["subtype"] == "Dentist"


# 2. JSON-encoded facts decode into structured values.
def test_json_facts_decode():
    c = _confirmed(_full_rows())
    assert isinstance(c["services"], list) and c["services"][0]["name"] == "Preventive cleanings"
    assert c["rating"]["count"] == 218


# 3. NAP JSONB fills scalar gaps under alias variants.
def test_nap_aliases_fill_gaps():
    assert _nap_value({"city": "Portland"}, "locality") == "Portland"
    assert _nap_value({"zip": "97201"}, "postal_code") == "97201"
    assert _nap_value({"phone": "+1-503-555-0142"}, "telephone") == "+1-503-555-0142"


# 4. Missing required facts fail loudly — no defaulting, no publish on a guess.
def test_missing_required_raises():
    thin = [{"field_name": "subtype", "field_value": "Dentist", "confirmed": True}]
    try:
        map_to_business_facts({"id": SITE_ID, "domain": "x.example"},
                              {"business_name": "X", "nap": {}}, thin)
        assert False, "expected FactsNotConfirmed"
    except FactsNotConfirmed as e:
        assert "street" in str(e) or "locality" in str(e) or "telephone" in str(e)


# 5. Mapper builds a complete BusinessFacts, pulling phone/city from NAP.
def test_mapper_builds_business_facts():
    bf = _repo().load_business_facts(SITE_ID)
    assert bf.business_name == "Cedar Ridge Dental"
    assert bf.subtype == "Dentist"
    assert bf.telephone == "+1-503-555-0142"     # from NAP fallback
    assert bf.locality == "Portland"             # from NAP fallback
    assert len(bf.services) == 3 and bf.rating.count == 218


# 6. End to end — run_ai_readiness_audit(site_id) loads, generates, grades >= 90.
def test_run_ai_readiness_audit_by_id():
    out = audit_engine.run_ai_readiness_audit(SITE_ID, repo=_repo(), cwv=GOOD_CWV)
    assert out["passed"] is True
    assert out["score"] >= 90
    assert out["normalized_score"] >= 90


# 7. A site whose facts are unconfirmed cannot be audited.
def test_unconfirmed_site_cannot_audit():
    unconfirmed = [dict(r, confirmed=False) for r in _full_rows()]
    try:
        audit_engine.run_ai_readiness_audit(SITE_ID, repo=_repo(unconfirmed), cwv=GOOD_CWV)
        assert False, "expected FactsNotConfirmed for an unconfirmed site"
    except FactsNotConfirmed:
        pass


# 8. Per-service faqs survive the round trip through this repository.
#
# 2026-08-21, Opus 5 review of §6 sub-slice 2b: map_to_business_facts()
# rebuilt each Service as Service(name=..., description=...), dropping any
# "faqs" key entirely -- BusinessFacts.model_dump() (the write side) already
# persists Service.faqs, so a real business's confirmed per-service FAQ
# content was silently discarded on every load through this repository.
# Reproduced directly: stored with a real faqs list, reloaded with
# faqs == []. This is the real production path (run_ai_readiness_audit /
# map_to_business_facts), not just the site_engine rendering layer, so a
# rendering-level test alone could never have caught it.
def test_service_faqs_survive_the_confirmed_facts_round_trip():
    rows = _full_rows()
    for r in rows:
        if r["field_name"] == "services":
            r["field_value"] = json.dumps([
                {"name": "Preventive cleanings", "description": "Exams, digital X-rays, and hygiene visits."},
                {"name": "Dental implants", "description": "Permanent tooth replacement placed in-house.",
                 "faqs": [{"question": "Are implants covered by insurance?", "answer": "Coverage varies by plan."}]},
                {"name": "Emergency care", "description": "Same-day appointments for pain and breaks."}])
    bf = _repo(rows).load_business_facts(SITE_ID)
    implants = next(s for s in bf.services if s.name == "Dental implants")
    assert len(implants.faqs) == 1, "per-service faqs were dropped on load from the real facts repository"
    assert implants.faqs[0].question == "Are implants covered by insurance?"
    # Services with no faqs key at all must not crash or fabricate anything.
    cleanings = next(s for s in bf.services if s.name == "Preventive cleanings")
    assert cleanings.faqs == []


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {e.__class__.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
