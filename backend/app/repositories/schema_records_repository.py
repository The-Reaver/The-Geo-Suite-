"""
Schema records persistence.
"""
from typing import Protocol, Any
from ..services.schema_validation import validate_jsonld

def schema_row(site_id: Any, *, page_id: Any, schema_type: str, json_ld: Any, validation_status: str) -> dict:
    return {
        "site_id": str(site_id),
        "page_id": str(page_id),
        "schema_type": schema_type,
        "json_ld": json_ld,
        "validation_status": validation_status
    }

class SchemaRecordsRepository(Protocol):
    def save(self, site_id: Any, *, page_id: Any, schema_type: str, json_ld: Any) -> dict: ...
    def get(self, site_id: Any, page_id: Any) -> dict | None: ...

class InMemorySchemaRecordsRepository:
    def __init__(self):
        # site_id -> page_id -> row
        self._records: dict[str, dict[str, dict]] = {}
        
    def save(self, site_id: Any, *, page_id: Any, schema_type: str, json_ld: Any) -> dict:
        sid, pid = str(site_id), str(page_id)
        
        graph_objects = json_ld
        if isinstance(json_ld, dict):
            if "@graph" in json_ld:
                graph_objects = json_ld["@graph"]
            else:
                graph_objects = [json_ld]
                
        status, _ = validate_jsonld(graph_objects)
        row = schema_row(site_id, page_id=page_id, schema_type=schema_type, json_ld=json_ld, validation_status=status)
        
        if sid not in self._records:
            self._records[sid] = {}
        self._records[sid][pid] = row
        return row
        
    def get(self, site_id: Any, page_id: Any) -> dict | None:
        return self._records.get(str(site_id), {}).get(str(page_id))

class SupabaseSchemaRecordsRepository:
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

    def save(self, site_id: Any, *, page_id: Any, schema_type: str, json_ld: Any) -> dict:
        graph_objects = json_ld
        if isinstance(json_ld, dict):
            if "@graph" in json_ld:
                graph_objects = json_ld["@graph"]
            else:
                graph_objects = [json_ld]
                
        status, _ = validate_jsonld(graph_objects)
        row = schema_row(site_id, page_id=page_id, schema_type=schema_type, json_ld=json_ld, validation_status=status)
        db = self._get_client()
        res = db.table("schema_records").upsert(row, on_conflict="site_id,page_id").execute()
        data = getattr(res, "data", [])
        return data[0] if data else row

    def get(self, site_id: Any, page_id: Any) -> dict | None:
        db = self._get_client()
        res = db.table("schema_records").select("*").eq("site_id", str(site_id)).eq("page_id", str(page_id)).execute()
        data = getattr(res, "data", [])
        return data[0] if data else None
