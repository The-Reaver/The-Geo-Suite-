"""Tests for GET /compliance/library -- the real Compliance Library data,
replacing the frontend's fake, hardcoded "3 pending" badge.
"""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

PLACEHOLDER_ENV = {
    "APP_ENV": "test",
    "APP_NAME": "geo-suite-backend",
    "SUPABASE_URL": "https://placeholder.supabase.co",
    "SUPABASE_ANON_KEY": "placeholder-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
}
for key, value in PLACEHOLDER_ENV.items():
    os.environ.setdefault(key, value)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core.permissions import require_sales_agent  # noqa: E402

client = TestClient(app)


def _fake_sales_agent():
    return {"sub": "11111111-1111-1111-1111-111111111111", "role": "sales_agent", "app_metadata": {"role": "sales_agent"}}


def test_library_requires_auth():
    app.dependency_overrides.clear()
    resp = client.get("/compliance/library")
    assert resp.status_code in (401, 403), f"unauthenticated library must be rejected, got {resp.status_code}"


def test_library_returns_all_20_sources_across_four_domains():
    app.dependency_overrides[require_sales_agent] = _fake_sales_agent
    try:
        resp = client.get("/compliance/library")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert len(data["domains"]) == 4
    assert data["total_sources"] == 20, f"all 20 raw_law files must appear, got {data['total_sources']}"
    for domain in data["domains"]:
        for source in domain["sources"]:
            assert source["verification_status"] == "Not yet lawyer-reviewed"
            assert isinstance(source["note_count"], int), "note_count must be a real int, never null/fabricated"


def test_library_carries_real_vendored_note_counts():
    # 2026-08-20: proves the vendored atomic_notes.json actually reaches the
    # API, not just that the endpoint returns a well-formed empty shape.
    app.dependency_overrides[require_sales_agent] = _fake_sales_agent
    try:
        resp = client.get("/compliance/library")
    finally:
        app.dependency_overrides.clear()
    data = resp.json()
    assert data["total_draft_notes"] == 88, f"expected 88 matched draft notes, got {data['total_draft_notes']}"
    assert data["orphaned_notes_count"] == 3

    by_file = {s["file"]: s for d in data["domains"] for s in d["sources"]}
    assert by_file["02-ftc-health-products-compliance-guidance.md"]["note_count"] == 16
    assert by_file["10-ftc-ai-claims-guidance.md"]["note_count"] == 0, \
        "file 10's own header predicts zero notes from it -- must not fabricate any"
    assert by_file["17-ftc-v-workado-complaint.md"]["sample_notes"], "a file with real notes must return sample text"


if __name__ == "__main__":
    tests = [test_library_requires_auth, test_library_returns_all_20_sources_across_four_domains,
              test_library_carries_real_vendored_note_counts]
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
