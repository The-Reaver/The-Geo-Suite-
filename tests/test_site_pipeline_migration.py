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


def _sql() -> str:
    with open(MIGRATION_PATH, encoding="utf-8") as f:
        return f.read()


def _check_values(sql: str, column: str) -> set:
    # Matches: <column>   text not null check (<column> in ('a', 'b', ...))
    m = re.search(rf"{column}\s+text[^\n]*check\s*\(\s*{column}\s+in\s*\(([^)]*)\)\)", sql)
    assert m, f"could not find a CHECK (...) constraint for column {column!r} in the migration"
    return {v.strip().strip("'") for v in m.group(1).split(",")}


def test_migration_file_exists():
    assert os.path.exists(MIGRATION_PATH), f"expected migration at {MIGRATION_PATH}"


def test_content_pages_page_type_check_matches_repository_code():
    sql = _sql()
    assert _check_values(sql, "page_type") == set(_VALID_PAGE_TYPES)


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
