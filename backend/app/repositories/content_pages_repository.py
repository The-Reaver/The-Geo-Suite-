"""
Content pages persistence.
"""
from typing import Protocol, Any

# "privacy" and "accessibility" match the real pages generate_site() writes
# (privacy.html, accessibility.html) -- before this they had no valid
# page_type of their own and got silently mislabeled "about" by
# site_pipeline.py's old fallback branch. "faq" stays even though
# generate_site() never writes a standalone FAQ page (FAQs render as a
# section of index.html) -- removing it would be a behavior change to a
# public-shaped constant with no evidence it's actually unused elsewhere.
# "menu" added 2026-08-21 alongside site_engine.py's new menu.html page --
# must stay in sync with the real DB CHECK constraint in
# supabase/migrations/20260820160000_site_pipeline_tables.sql (widened in
# the same commit as this constant, per tests/test_site_pipeline_migration.py's
# own guard against exactly this kind of drift).
_VALID_PAGE_TYPES = {"home", "service", "menu", "faq", "about", "privacy", "accessibility"}
_VALID_STATUSES = {"draft", "in_review", "approved", "published"}

def page_to_row(site_id: Any, *, slug: str, title: str, page_type: str, body_json: Any, status: str = "draft", version: int = 1) -> dict:
    if page_type not in _VALID_PAGE_TYPES:
        raise ValueError(f"Invalid page_type: {page_type}. Must be one of {_VALID_PAGE_TYPES}")
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {_VALID_STATUSES}")
        
    return {
        "site_id": str(site_id),
        "slug": slug,
        "title": title,
        "page_type": page_type,
        "body_json": body_json,
        "status": status,
        "version": version
    }

class ContentPagesRepository(Protocol):
    def save_page(self, site_id: Any, *, slug: str, title: str, page_type: str, body_json: Any, status: str = "draft") -> dict: ...
    def get_page(self, site_id: Any, slug: str) -> dict | None: ...
    def list_pages(self, site_id: Any) -> list[dict]: ...

class InMemoryContentPagesRepository:
    def __init__(self):
        # Dict mapping str(site_id) -> dict mapping slug -> row
        self._pages: dict[str, dict[str, dict]] = {}
        
    def save_page(self, site_id: Any, *, slug: str, title: str, page_type: str, body_json: Any, status: str = "draft") -> dict:
        sid = str(site_id)
        if sid not in self._pages:
            self._pages[sid] = {}
            
        existing = self._pages[sid].get(slug)
        version = 1
        if existing:
            version = existing["version"] + 1
            
        row = page_to_row(site_id, slug=slug, title=title, page_type=page_type, body_json=body_json, status=status, version=version)
        self._pages[sid][slug] = row
        return row
        
    def get_page(self, site_id: Any, slug: str) -> dict | None:
        return self._pages.get(str(site_id), {}).get(slug)
        
    def list_pages(self, site_id: Any) -> list[dict]:
        return list(self._pages.get(str(site_id), {}).values())

class SupabaseContentPagesRepository:
    """Production repository for content pages."""
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

    def save_page(self, site_id: Any, *, slug: str, title: str, page_type: str, body_json: Any, status: str = "draft") -> dict:
        db = self._get_client()
        sid = str(site_id)
        
        # Check if exists to determine version
        res = db.table("content_pages").select("version").eq("site_id", sid).eq("slug", slug).execute()
        existing = getattr(res, "data", [])
        version = 1
        if existing:
            version = existing[0]["version"] + 1
            
        row = page_to_row(site_id, slug=slug, title=title, page_type=page_type, body_json=body_json, status=status, version=version)
        
        # Upsert
        res = db.table("content_pages").upsert(row, on_conflict="site_id,slug").execute()
        data = getattr(res, "data", [])
        return data[0] if data else row

    def get_page(self, site_id: Any, slug: str) -> dict | None:
        db = self._get_client()
        res = db.table("content_pages").select("*").eq("site_id", str(site_id)).eq("slug", slug).execute()
        data = getattr(res, "data", [])
        return data[0] if data else None

    def list_pages(self, site_id: Any) -> list[dict]:
        db = self._get_client()
        res = db.table("content_pages").select("*").eq("site_id", str(site_id)).execute()
        return getattr(res, "data", [])
