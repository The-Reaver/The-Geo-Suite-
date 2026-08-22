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
from app.core.permissions import require_sales_agent, require_lawyer, verify_token  # noqa: E402

client = TestClient(app)

# Real ids from the vendored corpus (knowledge_core/feeds/regulatory/
# raw_law/atomic_notes.json) -- distinct per test so the module-level
# InMemory repo singleton (compliance.py's _COMPLIANCE_NOTES_REPO, same
# pattern as sites.py's get_site_repos()) can't leak ratify/reject state
# from one test into another's assertions.
_NOTE_A = "1c1c70554f20409e9862949567b7f8fe"
_NOTE_B = "f70d4c5105b54f4bb40675f4d36f8085"
_NOTE_C = "66aac55b1a824071badba685cd647656"
_LAWYER_SUB = "22222222-2222-2222-2222-222222222222"


def _fake_sales_agent():
    return {"sub": "11111111-1111-1111-1111-111111111111", "role": "sales_agent", "app_metadata": {"role": "sales_agent"}}


def _fake_lawyer():
    return {"sub": _LAWYER_SUB, "app_metadata": {"role": "lawyer"}}


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


def test_library_carries_real_detection_status_per_domain():
    # 2026-08-20: proves each domain honestly reports whether an automated
    # check exists for it and whether that check is actually enforced --
    # not just that citations exist, which was already true before any
    # check was written for ai-claims-*.
    app.dependency_overrides[require_sales_agent] = _fake_sales_agent
    try:
        resp = client.get("/compliance/library")
    finally:
        app.dependency_overrides.clear()
    data = resp.json()
    status_by_domain = {d["domain"]: d["detection_status"] for d in data["domains"]}

    assert status_by_domain["Medical marketing claims"]["has_check"] is True
    assert status_by_domain["Medical marketing claims"]["wired_into_publish_gate"] is True

    assert status_by_domain["Patient data privacy"]["has_check"] is True
    assert status_by_domain["Patient data privacy"]["wired_into_publish_gate"] is True

    # The one real gap: no automated lead-contact check exists, and the
    # response must say so plainly, not omit the field or claim otherwise.
    assert status_by_domain["Lead-contact compliance"]["has_check"] is False
    assert status_by_domain["Lead-contact compliance"]["wired_into_publish_gate"] is False
    assert status_by_domain["Lead-contact compliance"]["note"]

    # The new real check: built, tested, deliberately not yet enforced.
    ai_status = status_by_domain["AI-visibility / AI-generated content"]
    assert ai_status["has_check"] is True
    assert ai_status["wired_into_publish_gate"] is False
    assert ai_status["note"]


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
    samples = by_file["17-ftc-v-workado-complaint.md"]["sample_notes"]
    assert samples, "a file with real notes must return sample text"


def test_library_sample_notes_carry_real_ids_and_status():
    # 2026-08-22, mini-slice 3: sample_notes must carry each note's real id
    # (so the frontend can build a ratify/reject control) and its real
    # current status (draft by default -- "no row" still means draft,
    # same overlay semantics as everywhere else). Not just non-empty text.
    app.dependency_overrides[require_sales_agent] = _fake_sales_agent
    try:
        resp = client.get("/compliance/library")
    finally:
        app.dependency_overrides.clear()
    data = resp.json()
    samples = next(
        s["sample_notes"] for d in data["domains"] for s in d["sources"]
        if s["file"] == "17-ftc-v-workado-complaint.md"
    )
    assert samples
    for note in samples:
        assert isinstance(note["id"], str) and len(note["id"]) == 32, note
        assert isinstance(note["body"], str) and note["body"]
        assert note["status"] == "draft", "no ratification has happened for these notes in this test"


def test_ratify_requires_auth():
    app.dependency_overrides.clear()
    resp = client.post(f"/compliance/library/notes/{_NOTE_A}/ratify", json={})
    assert resp.status_code in (401, 403)


def test_sales_agent_alone_cannot_ratify():
    # 2026-08-22, the actual reason mini-slice 2 was blocked for a full day
    # this session: require_sales_agent would have let any sales agent
    # ratify/reject legal compliance notes. require_lawyer is a distinct
    # gate -- a sales_agent-role real token must be rejected here.
    #
    # Overrides verify_token (require_lawyer's own upstream dependency),
    # not require_lawyer itself -- overriding require_lawyer directly would
    # replace its whole body, including the role check this test exists to
    # exercise, and silently prove nothing (caught by running this exact
    # mistake first: it returned 200).
    app.dependency_overrides[verify_token] = _fake_sales_agent
    try:
        resp = client.post(f"/compliance/library/notes/{_NOTE_A}/ratify", json={})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_lawyer_can_ratify_a_real_note_and_reviewed_by_comes_from_the_token():
    # 2026-08-22, Opus 5 review of 902c4e1, finding F3: the first version
    # of this test (and test_owner_can_also_ratify below) overrode
    # require_lawyer directly -- the identical mistake
    # test_sales_agent_alone_cannot_ratify was rewritten to avoid.
    # Mutation-proven: with that version, changing require_lawyer's role
    # list to ["laywer", ...] (a typo of the one role this slice exists to
    # add) still passed 11/11, because "lawyer" was never actually
    # exercised through the real dependency. Overriding verify_token
    # instead forces the real require_lawyer body -- role list, typos and
    # all -- to run for every case below.
    app.dependency_overrides[verify_token] = _fake_lawyer
    try:
        # An attacker-controlled reviewed_by in the body must be ignored --
        # RatificationRequest has no such field, so Pydantic drops it
        # silently (default extra="ignore"); this proves it end-to-end,
        # not just that the field is absent from the schema.
        resp = client.post(
            f"/compliance/library/notes/{_NOTE_B}/ratify",
            json={"reason": "Verified against the statute text.", "reviewed_by": "someone-else"},
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ratified"
    assert data["reviewed_by"] == _LAWYER_SUB, "reviewed_by must come from the verified token, never the request body"
    assert data["reason"] == "Verified against the statute text."


def test_owner_can_also_ratify():
    # require_lawyer widens the gate, it doesn't narrow owner's existing
    # full access -- same precedent as require_sales_agent's own owner/admin
    # carve-out. Overrides verify_token, not require_lawyer -- see the
    # comment on the lawyer test above for why that distinction is real.
    def _fake_owner():
        return {"sub": "33333333-3333-3333-3333-333333333333", "app_metadata": {"role": "owner"}}

    app.dependency_overrides[verify_token] = _fake_owner
    try:
        resp = client.post(f"/compliance/library/notes/{_NOTE_C}/reject", json={"reason": "Not applicable."})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"


def test_admin_can_also_ratify():
    def _fake_admin():
        return {"sub": "44444444-4444-4444-4444-444444444444", "app_metadata": {"role": "admin"}}

    app.dependency_overrides[verify_token] = _fake_admin
    try:
        resp = client.post("/compliance/library/notes/bf744b65ee5d49a5b0dda52d7f7237c7/ratify", json={})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ratified"


def test_missing_sub_claim_is_rejected():
    # 2026-08-22, Opus 5 review finding F5: _reviewer_id()'s guard against
    # a sub-less token was real but untested -- mutation-proven that
    # replacing its `if not reviewer` check with `if False` still passed
    # 11/11. A token with no sub would otherwise reach
    # note_status_to_row() and 500 instead of 401.
    def _fake_no_sub():
        return {"app_metadata": {"role": "lawyer"}}

    app.dependency_overrides[verify_token] = _fake_no_sub
    try:
        resp = client.post(f"/compliance/library/notes/{_NOTE_A}/ratify", json={})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 401


def test_ratify_with_no_body_uses_the_default_empty_reason():
    # 2026-08-22, Opus 5 review finding F7: RatificationRequest's own
    # default of "" for `reason` is meaningless if FastAPI still requires
    # a body to be sent at all -- a bare "ratify, no comment" click must
    # work with an empty POST body, not just an explicit `{}`.
    app.dependency_overrides[verify_token] = _fake_lawyer
    try:
        resp = client.post("/compliance/library/notes/eca3321283a74bc1b1a33e70df7c7922/ratify")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    assert resp.json()["reason"] is None or resp.json()["reason"] == ""


def test_unknown_note_id_is_rejected():
    app.dependency_overrides[require_lawyer] = _fake_lawyer
    try:
        resp = client.post("/compliance/library/notes/not-a-real-note-id/ratify", json={})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404


def test_reason_length_is_bounded():
    app.dependency_overrides[require_lawyer] = _fake_lawyer
    try:
        resp = client.post(
            f"/compliance/library/notes/{_NOTE_A}/ratify",
            json={"reason": "x" * 2001},
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422


def test_library_sample_note_status_reflects_a_real_ratification():
    # Proves sample_notes' status field is actually wired to the real
    # overlay repository, not a hardcoded "draft" -- ratify one of file
    # 17's own real sample notes, confirm the SAME id's status flips in
    # the next GET.
    target_note = "5843d77055494e67a62874faffdc63fa"
    app.dependency_overrides[require_lawyer] = _fake_lawyer
    app.dependency_overrides[require_sales_agent] = _fake_sales_agent
    try:
        ratify_resp = client.post(f"/compliance/library/notes/{target_note}/ratify", json={})
        assert ratify_resp.status_code == 200, ratify_resp.text
        resp = client.get("/compliance/library")
    finally:
        app.dependency_overrides.clear()
    data = resp.json()
    samples = next(
        s["sample_notes"] for d in data["domains"] for s in d["sources"]
        if s["file"] == "17-ftc-v-workado-complaint.md"
    )
    by_id = {n["id"]: n for n in samples}
    assert by_id[target_note]["status"] == "ratified"


def test_library_reflects_a_real_ratification():
    # End-to-end proof the two routes actually talk to the same repository
    # GET /compliance/library reads from -- not two disconnected paths that
    # happen to compile.
    fresh_note = "920da5848d1342cca3c420763adf6801"
    app.dependency_overrides[require_lawyer] = _fake_lawyer
    app.dependency_overrides[require_sales_agent] = _fake_sales_agent
    try:
        before = client.get("/compliance/library").json()["lawyer_ratified_count"]
        ratify_resp = client.post(f"/compliance/library/notes/{fresh_note}/ratify", json={})
        assert ratify_resp.status_code == 200, ratify_resp.text
        after = client.get("/compliance/library").json()["lawyer_ratified_count"]
    finally:
        app.dependency_overrides.clear()
    assert after == before + 1


if __name__ == "__main__":
    tests = [test_library_requires_auth, test_library_returns_all_20_sources_across_four_domains,
              test_library_carries_real_detection_status_per_domain,
              test_library_carries_real_vendored_note_counts,
              test_library_sample_notes_carry_real_ids_and_status,
              test_library_sample_note_status_reflects_a_real_ratification,
              test_ratify_requires_auth, test_sales_agent_alone_cannot_ratify,
              test_lawyer_can_ratify_a_real_note_and_reviewed_by_comes_from_the_token,
              test_owner_can_also_ratify, test_admin_can_also_ratify,
              test_missing_sub_claim_is_rejected, test_ratify_with_no_body_uses_the_default_empty_reason,
              test_unknown_note_id_is_rejected,
              test_reason_length_is_bounded, test_library_reflects_a_real_ratification]
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
