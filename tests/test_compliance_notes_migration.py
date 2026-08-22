# Guards the real migration SQL (supabase/migrations/
# 20260822120000_compliance_notes_table.sql) against drifting from the
# Python repository code it backs. Same exact pattern as
# test_site_pipeline_migration.py, applied to the new compliance_notes
# table -- a CHECK constraint enforces the same status set at the database
# layer, so a mismatch there would surface as production insert failures on
# a status the repository code itself considers valid.
import json
import os
import re
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.repositories.compliance_notes_repository import _VALID_STATUSES  # noqa: E402

MIGRATION_PATH = os.path.join(
    PROJ, "supabase", "migrations", "20260822120000_compliance_notes_table.sql",
)


def _sql() -> str:
    with open(MIGRATION_PATH, encoding="utf-8") as f:
        return f.read()


def _check_values(sql: str, column: str) -> set:
    # Matches: <column>   text not null default 'x' check (<column> in ('a', 'b', ...))
    m = re.search(rf"{column}\s+text[^\n]*check\s*\(\s*{column}\s+in\s*\(([^)]*)\)\)", sql)
    assert m, f"could not find a CHECK (...) constraint for column {column!r} in the migration"
    return {v.strip().strip("'") for v in m.group(1).split(",")}


def test_migration_file_exists():
    assert os.path.exists(MIGRATION_PATH), f"expected migration at {MIGRATION_PATH}"


def test_compliance_notes_status_check_matches_repository_code():
    sql = _sql()
    assert _check_values(sql, "status") == set(_VALID_STATUSES)


def test_compliance_notes_table_declared():
    sql = _sql()
    assert "create table public.compliance_notes" in sql


def test_compliance_notes_has_rls_enabled():
    sql = _sql()
    assert "alter table public.compliance_notes enable row level security" in sql, (
        "compliance_notes must have RLS enabled -- every other table in this repo's schema does"
    )


def test_compliance_notes_note_id_is_the_primary_key():
    # This table is an overlay keyed by the vendored JSON's own note id
    # (deliberately no separate uuid surrogate key -- see the migration's
    # own header comment for why). Guards against a future edit silently
    # dropping the primary key or switching to a different key column,
    # which would break SupabaseComplianceNotesRepository's upsert(...,
    # on_conflict="note_id") call outright.
    sql = _sql()
    assert re.search(r"note_id\s+text\s+primary key", sql), \
        "note_id must stay the real primary key -- upsert(on_conflict='note_id') depends on it"


def test_all_vendored_notes_start_as_draft():
    # Pins the overlay design's real starting condition: "no row in
    # compliance_notes means implicitly draft" is only honest if the
    # vendored source of truth actually agrees every note starts as
    # draft. If a future regeneration of atomic_notes.json ever ships a
    # note pre-marked ratified/rejected, the overlay's "no row = draft"
    # shortcut would silently misreport that note's real status.
    notes_path = os.path.join(
        PROJ, "knowledge_core", "feeds", "regulatory", "raw_law", "atomic_notes.json",
    )
    with open(notes_path, encoding="utf-8") as f:
        data = json.load(f)

    statuses = []
    for per_file in data["notes_by_file"].values():
        notes = per_file if isinstance(per_file, list) else per_file.get("notes", [])
        statuses.extend(n["status"] for n in notes)
    statuses.extend(n["status"] for n in data.get("orphaned_notes", []))

    assert statuses, "expected to find real vendored notes to check"
    assert set(statuses) == {"draft"}, (
        f"expected every vendored note to start as draft, found: {set(statuses)}"
    )


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
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


if __name__ == "__main__":
    _run_all()
