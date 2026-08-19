"""
Optimization files persistence.
"""
from typing import Protocol, Any
from pathlib import Path
from datetime import datetime, timezone

FILENAME_TO_TYPE = {
    "robots.txt": "robots", 
    "sitemap.xml": "sitemap",
    "llms.txt": "llms", 
    "llms-full.txt": "llms_full",
}

_VALID_FILE_TYPES = {"llms", "llms_full", "robots", "sitemap", "manifest", "wellknown"}

def opt_file_row(site_id: Any, *, file_type: str, content: str) -> dict:
    if file_type not in _VALID_FILE_TYPES:
        raise ValueError(f"Invalid file_type: {file_type}. Must be one of {_VALID_FILE_TYPES}")
        
    return {
        "site_id": str(site_id),
        "file_type": file_type,
        "content": content,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

class OptimizationFilesRepository(Protocol):
    def save(self, site_id: Any, *, file_type: str, content: str) -> dict: ...
    def latest(self, site_id: Any, file_type: str) -> dict | None: ...
    def save_site_dir(self, site_id: Any, site_dir: Path | str) -> list[dict]: ...

class InMemoryOptimizationFilesRepository:
    def __init__(self):
        # site_id -> list of rows
        self._records: dict[str, list[dict]] = {}

    def save(self, site_id: Any, *, file_type: str, content: str) -> dict:
        sid = str(site_id)
        row = opt_file_row(site_id, file_type=file_type, content=content)
        if sid not in self._records:
            self._records[sid] = []
        self._records[sid].append(row)
        return row

    def latest(self, site_id: Any, file_type: str) -> dict | None:
        sid = str(site_id)
        records = self._records.get(sid, [])
        # Find latest by generated_at
        matches = [r for r in records if r["file_type"] == file_type]
        if not matches:
            return None
        return max(matches, key=lambda x: x["generated_at"])

    def save_site_dir(self, site_id: Any, site_dir: Path | str) -> list[dict]:
        p = Path(site_dir)
        saved = []
        for filename, ftype in FILENAME_TO_TYPE.items():
            fpath = p / filename
            if fpath.exists():
                saved.append(self.save(site_id, file_type=ftype, content=fpath.read_text(encoding="utf-8")))
        return saved


class SupabaseOptimizationFilesRepository:
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

    def save(self, site_id: Any, *, file_type: str, content: str) -> dict:
        row = opt_file_row(site_id, file_type=file_type, content=content)
        db = self._get_client()
        res = db.table("optimization_files").insert(row).execute()
        data = getattr(res, "data", [])
        return data[0] if data else row

    def latest(self, site_id: Any, file_type: str) -> dict | None:
        db = self._get_client()
        res = db.table("optimization_files") \
                .select("*") \
                .eq("site_id", str(site_id)) \
                .eq("file_type", file_type) \
                .order("generated_at", desc=True) \
                .limit(1) \
                .execute()
        data = getattr(res, "data", [])
        return data[0] if data else None

    def save_site_dir(self, site_id: Any, site_dir: Path | str) -> list[dict]:
        p = Path(site_dir)
        saved = []
        for filename, ftype in FILENAME_TO_TYPE.items():
            fpath = p / filename
            if fpath.exists():
                saved.append(self.save(site_id, file_type=ftype, content=fpath.read_text(encoding="utf-8")))
        return saved
