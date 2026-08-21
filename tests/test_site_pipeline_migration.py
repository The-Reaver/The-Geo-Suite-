# Guards the real migration SQL (supabase/migrations/
# 20260820160000_site_pipeline_tables.sql) against drifting from the Python
# repository code it backs. This is exactly the class of bug this session
# already found and fixed once: content_pages_repository.py's
# _VALID_PAGE_TYPES silently didn't match what site_pipeline.py actually
# produced. A CHECK constraint enforces the same set at the database layer,
# so a mismatch there would surface as production insert failures on a page
# type or file type the repository code itself considers valid --
# comparing the two sets directly here catches that before it ships.
import os
import re
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.repositories.content_pages_repository import (  # noqa: E402
    _VALID_PAGE_TYPES,
    _VALID_STATUSES,
)
from app.repositories.optimization_files_repository import _VALID_FILE_TYPES  # noqa: E402

MIGRATION_PATH = os.path.join(
    PROJ, "supabase", "migrations", "20260820160000_site_pipeline_tables.sql",
)
# 2026-08-21: the original migration file above is left untouched (already
# applied to the live project) -- this later ALTER is the real, live-applied
# widening of content_pages.page_type's CHECK constraint to add 'menu'. The
# guard test below must check the CUMULATIVE effective constraint (this file
# supersedes the original's page_type check), not just the original file, or
# it would silently stop catching drift the moment a later migration is the
# one that's actually correct.
MENU_TYPE_MIGRATION_PATH = os.path.join(
    PROJ, "supabase", "migrations", "20260821180000_content_pages_add_menu_type.sql",
)


def _sql() -> str:
    with open(MIGRATION_PATH, encoding="utf-8") as f:
        return f.read()


def _menu_migration_sql() -> str:
    with open(MENU_TYPE_MIGRATION_PATH, encoding="utf-8") as f:
        return f.read()


def _check_values(sql: str, column: str) -> set:
    # Matches: <column>   text not null check (<column> in ('a', 'b', ...))
    m = re.search(rf"{column}\s+text[^\n]*check\s*\(\s*{column}\s+in\s*\(([^)]*)\)\)", sql)
    assert m, f"could not find a CHECK (...) constraint for column {column!r} in the migration"
    return {v.strip().strip("'") for v in m.group(1).split(",")}


def _check_values_generic(sql: str, column: str) -> set:
    # Same idea as _check_values, but for an `alter table ... add constraint
    # ... check (<column> in (...))` statement, which doesn't redeclare the
    # column's type inline the way a CREATE TABLE column definition does.
    m = re.search(rf"check\s*\(\s*{column}\s+in\s*\(([^)]*)\)\)", sql)
    assert m, f"could not find a CHECK (...) constraint for column {column!r} in the migration"
    return {v.strip().strip("'") for v in m.group(1).split(",")}


def test_migration_file_exists():
    assert os.path.exists(MIGRATION_PATH), f"expected migration at {MIGRATION_PATH}"
    assert os.path.exists(MENU_TYPE_MIGRATION_PATH), f"expected migration at {MENU_TYPE_MIGRATION_PATH}"


def test_content_pages_page_type_check_matches_repository_code():
    # The original migration's own inline CHECK is left as historical fact
    # (already applied live, never edited after the fact) -- the later
    # ALTER migration is what actually governs the live constraint today,
    # so that file, not the original, must match the current Python set.
    sql = _menu_migration_sql()
    assert _check_values_generic(sql, "page_type") == set(_VALID_PAGE_TYPES)


def test_original_content_pages_page_type_check_is_a_subset_of_the_current_set():
    # The original migration's CHECK is deliberately stale (superseded by
    # the ALTER above), but it should still be a real subset of what's
    # valid today -- never referencing a page_type the repository code has
    # since removed, which would mean the ALTER silently dropped support
    # for something still declared valid elsewhere.
    original = _check_values(_sql(), "page_type")
    assert original <= set(_VALID_PAGE_TYPES)


def test_content_pages_status_check_matches_repository_code():
    sql = _sql()
    assert _check_values(sql, "status") == set(_VALID_STATUSES)


def test_optimization_files_file_type_check_matches_repository_code():
    sql = _sql()
    assert _check_values(sql, "file_type") == set(_VALID_FILE_TYPES)


def test_all_four_tables_declared():
    sql = _sql()
    for table in ("content_pages", "schema_records", "optimization_files", "audit_results"):
        assert f"create table public.{table}" in sql, f"missing create table for {table}"


def test_all_four_tables_have_rls_enabled():
    sql = _sql()
    for table in ("content_pages", "schema_records", "optimization_files", "audit_results"):
        assert f"alter table public.{table} enable row level security" in sql, (
            f"{table} must have RLS enabled -- every other table in this repo's schema does"
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
