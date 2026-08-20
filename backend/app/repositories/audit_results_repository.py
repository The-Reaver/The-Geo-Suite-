"""
Audit results persistence — write and read AuditResult.

Follows the pure-mapper + InMemory + Supabase pattern.
"""
from __future__ import annotations

import datetime
from typing import Any, Protocol

from ..services.audit_engine import AuditResult, result_to_breakdown


def audit_result_to_row(site_id: Any, result: AuditResult, *, trigger: str, build_id: Any = None) -> dict:
    """Map an AuditResult to a row dictionary for storage."""
    return {
        "site_id": str(site_id),
        "build_id": str(build_id) if build_id else None,
        "score": result.normalized_score,
        "passed": result.passed,
        "breakdown": result_to_breakdown(result),
        "trigger": trigger,
        "run_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


class AuditResultsRepository(Protocol):
    def save(self, site_id: Any, result: AuditResult, *, trigger: str, build_id: Any = None) -> dict: ...
    def latest(self, site_id: Any) -> dict | None: ...
    def list_latest_per_site(self) -> list[dict]: ...


class InMemoryAuditResultsRepository:
    """Test/local repository."""

    def __init__(self):
        self._rows: list[dict] = []

    def save(self, site_id: Any, result: AuditResult, *, trigger: str, build_id: Any = None) -> dict:
        row = audit_result_to_row(site_id, result, trigger=trigger, build_id=build_id)
        row["id"] = str(len(self._rows) + 1)
        self._rows.append(row)
        return row

    def latest(self, site_id: Any) -> dict | None:
        site_rows = [r for r in self._rows if r.get("site_id") == str(site_id)]
        if not site_rows:
            return None
        return sorted(site_rows, key=lambda r: r.get("run_at", ""), reverse=True)[0]

    def list_latest_per_site(self) -> list[dict]:
        # Pipeline slice 2: the Pipeline list page's data source. One row
        # per distinct site_id -- its most recent audit -- newest first.
        by_site: dict[str, dict] = {}
        for row in self._rows:
            sid = row.get("site_id", "")
            current = by_site.get(sid)
            if current is None or row.get("run_at", "") > current.get("run_at", ""):
                by_site[sid] = row
        return sorted(by_site.values(), key=lambda r: r.get("run_at", ""), reverse=True)


class SupabaseAuditResultsRepository:
    """Production repository."""

    def __init__(self, client: Any = None):
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        # 2026-08-08 fix, GEO Brain Trust review: this used to read
        # settings.SUPABASE_URL / settings.SUPABASE_KEY from app.core.config,
        # a field (SUPABASE_KEY) no .env or .env.example in this repo has
        # ever populated, so this raised even after real Supabase credentials
        # were supplied. Routes through the same already-correct
        # service-role factory admin_service.py and operator_guard.py use.
        from ..core.supabase_client import SupabaseConfigError, get_supabase_admin
        try:
            self._client = get_supabase_admin()
        except SupabaseConfigError as exc:
            raise RuntimeError(str(exc)) from exc
        return self._client

    def save(self, site_id: Any, result: AuditResult, *, trigger: str, build_id: Any = None) -> dict:
        row = audit_result_to_row(site_id, result, trigger=trigger, build_id=build_id)
        db = self._get_client()
        res = db.table("audit_results").insert(row).execute()
        data = getattr(res, "data", None)
        if not data:
            raise RuntimeError("Failed to insert audit_result")
        return data[0]

    def latest(self, site_id: Any) -> dict | None:
        db = self._get_client()
        res = (db.table("audit_results")
               .select("*")
               .eq("site_id", str(site_id))
               .order("run_at", desc=True)
               .limit(1)
               .execute())
        data = getattr(res, "data", None)
        if not data:
            return None
        return data[0]

    def list_latest_per_site(self) -> list[dict]:
        # Pipeline slice 2: the Pipeline list page's data source. postgrest's
        # fluent query builder has no DISTINCT ON, so this fetches every row
        # newest-first and dedupes by site_id in Python, keeping the first
        # (newest) occurrence -- correct at today's real scale (a handful of
        # saved prospects), and a real, deliberate simplification: if
        # audit_results genuinely grows past what's comfortable to fetch
        # whole, that's the trigger to replace this with a DISTINCT ON query
        # or a materialized view, not a reason to build one pre-emptively.
        db = self._get_client()
        res = db.table("audit_results").select("*").order("run_at", desc=True).execute()
        data = getattr(res, "data", None) or []
        seen: set[str] = set()
        latest: list[dict] = []
        for row in data:
            sid = row.get("site_id", "")
            if sid in seen:
                continue
            seen.add(sid)
            latest.append(row)
        return latest
