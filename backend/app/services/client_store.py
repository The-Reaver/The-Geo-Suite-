"""Client provisioning store seam — offline InMemory first (RV-PLATFORM-01/02)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4

import httpx


@dataclass
class ClientRecord:
    id: UUID
    business_name: str
    tier: str
    client_type: str
    status: str
    nap: dict[str, Any]
    monthly_fee_cents: int
    margin_alert_pct: float
    owner_user_id: UUID | None = None

    def to_response_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "business_name": self.business_name,
            "tier": self.tier,
            "client_type": self.client_type,
            "status": self.status,
            "nap": dict(self.nap),
            "monthly_fee_cents": self.monthly_fee_cents,
            "margin_alert_pct": self.margin_alert_pct,
            "owner_user_id": self.owner_user_id,
        }


@dataclass
class SiteRecord:
    id: UUID
    client_id: UUID
    domain: str
    status: str = "queued"

    def to_queue_dict(self) -> dict[str, str]:
        return {"status": self.status, "site_id": str(self.id)}


@runtime_checkable
class ClientStore(Protocol):
    """Provisioning seam — InMemory offline; Supabase when env-gated live."""

    def clear(self) -> None: ...

    def create_client(
        self, data: dict[str, Any], *, owner_user_id: UUID | None = None
    ) -> ClientRecord: ...

    def list_clients(self) -> list[ClientRecord]: ...

    def get_client(self, client_id: UUID) -> ClientRecord | None: ...

    def update_client(self, client_id: UUID, data: dict[str, Any]) -> ClientRecord | None: ...

    def create_site(self, client_id: UUID, domain: str) -> SiteRecord | None: ...


class InMemoryClientStore:
    """Process-local store for offline battery. Not a live DB proof."""

    def __init__(self) -> None:
        self._clients: dict[UUID, ClientRecord] = {}
        self._sites: dict[UUID, SiteRecord] = {}
        self._lock = Lock()

    def clear(self) -> None:
        with self._lock:
            self._clients.clear()
            self._sites.clear()

    def create_client(
        self, data: dict[str, Any], *, owner_user_id: UUID | None = None
    ) -> ClientRecord:
        with self._lock:
            rec = ClientRecord(
                id=uuid4(),
                business_name=str(data["business_name"]),
                tier=str(data["tier"]),
                client_type=str(data["client_type"]),
                status=str(data["status"]),
                nap=dict(data.get("nap") or {}),
                monthly_fee_cents=int(data["monthly_fee_cents"]),
                margin_alert_pct=float(data["margin_alert_pct"]),
                owner_user_id=owner_user_id,
            )
            self._clients[rec.id] = rec
            return rec

    def list_clients(self) -> list[ClientRecord]:
        with self._lock:
            return list(self._clients.values())

    def get_client(self, client_id: UUID) -> ClientRecord | None:
        with self._lock:
            return self._clients.get(client_id)

    def update_client(self, client_id: UUID, data: dict[str, Any]) -> ClientRecord | None:
        with self._lock:
            existing = self._clients.get(client_id)
            if existing is None:
                return None
            updated = ClientRecord(
                id=existing.id,
                business_name=str(data["business_name"]),
                tier=str(data["tier"]),
                client_type=str(data["client_type"]),
                status=str(data["status"]),
                nap=dict(data.get("nap") or {}),
                monthly_fee_cents=int(data["monthly_fee_cents"]),
                margin_alert_pct=float(data["margin_alert_pct"]),
                owner_user_id=existing.owner_user_id,
            )
            self._clients[client_id] = updated
            return updated

    def create_site(self, client_id: UUID, domain: str) -> SiteRecord | None:
        with self._lock:
            if client_id not in self._clients:
                return None
            site = SiteRecord(id=uuid4(), client_id=client_id, domain=domain, status="queued")
            self._sites[site.id] = site
            return site


def _row_to_client(row: dict[str, Any]) -> ClientRecord:
    owner = row.get("owner_user_id")
    return ClientRecord(
        id=UUID(str(row["id"])),
        business_name=str(row["business_name"]),
        tier=str(row["tier"]),
        client_type=str(row["client_type"]),
        status=str(row["status"]),
        nap=dict(row.get("nap") or {}),
        monthly_fee_cents=int(row["monthly_fee_cents"]),
        margin_alert_pct=float(row["margin_alert_pct"]),
        owner_user_id=UUID(str(owner)) if owner else None,
    )


class SupabaseClientStore:
    """PostgREST ClientStore via existing supabase settings (RV-PLATFORM-02).

    Not a live proof by itself — only used when factory env-gates it on.
    """

    def __init__(self, *, base_url: str | None = None, headers: dict[str, str] | None = None) -> None:
        # Lazy import keeps offline battery free of settings side effects when unused.
        if base_url is None or headers is None:
            from app.services.supabase_client import _service_headers, is_supabase_configured
            from app.config import get_settings

            if not is_supabase_configured():
                raise RuntimeError("SupabaseClientStore requires configured Supabase credentials")
            settings = get_settings()
            base_url = settings.supabase_url.rstrip("/")
            headers = _service_headers()
        self._base = base_url.rstrip("/")
        self._headers = dict(headers)
        self._headers.setdefault("Content-Type", "application/json")
        self._headers.setdefault("Prefer", "return=representation")

    def clear(self) -> None:
        # Live store has no process-local clear; tests must use InMemory.
        raise NotImplementedError("SupabaseClientStore.clear is offline-only; use InMemoryClientStore")

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self._base, headers=self._headers, timeout=10.0)

    def create_client(
        self, data: dict[str, Any], *, owner_user_id: UUID | None = None
    ) -> ClientRecord:
        body = {
            "business_name": str(data["business_name"]),
            "tier": str(data["tier"]),
            "client_type": str(data["client_type"]),
            "status": str(data["status"]),
            "nap": dict(data.get("nap") or {}),
            "monthly_fee_cents": int(data["monthly_fee_cents"]),
            "margin_alert_pct": float(data["margin_alert_pct"]),
        }
        if owner_user_id is not None:
            body["owner_user_id"] = str(owner_user_id)
        with self._client() as client:
            resp = client.post("/rest/v1/clients", json=body)
            resp.raise_for_status()
            rows = resp.json()
        row = rows[0] if isinstance(rows, list) else rows
        return _row_to_client(row)

    def list_clients(self) -> list[ClientRecord]:
        with self._client() as client:
            resp = client.get("/rest/v1/clients", params={"select": "*"})
            resp.raise_for_status()
            rows = resp.json()
        return [_row_to_client(r) for r in rows]

    def get_client(self, client_id: UUID) -> ClientRecord | None:
        with self._client() as client:
            resp = client.get(
                "/rest/v1/clients",
                params={"select": "*", "id": f"eq.{client_id}"},
            )
            resp.raise_for_status()
            rows = resp.json()
        if not rows:
            return None
        return _row_to_client(rows[0])

    def update_client(self, client_id: UUID, data: dict[str, Any]) -> ClientRecord | None:
        body = {
            "business_name": str(data["business_name"]),
            "tier": str(data["tier"]),
            "client_type": str(data["client_type"]),
            "status": str(data["status"]),
            "nap": dict(data.get("nap") or {}),
            "monthly_fee_cents": int(data["monthly_fee_cents"]),
            "margin_alert_pct": float(data["margin_alert_pct"]),
        }
        with self._client() as client:
            resp = client.patch(
                "/rest/v1/clients",
                params={"id": f"eq.{client_id}"},
                json=body,
            )
            resp.raise_for_status()
            rows = resp.json()
        if not rows:
            return None
        return _row_to_client(rows[0])

    def create_site(self, client_id: UUID, domain: str) -> SiteRecord | None:
        if self.get_client(client_id) is None:
            return None
        # Schema-safe defaults for NOT NULL live columns (init_schema).
        body = {
            "client_id": str(client_id),
            "domain": domain,
            "staging_url": f"https://staging.example.invalid/{client_id}",
            "status": "provisioning",
            "template_version": "v0",
            "health_status": "unknown",
            "ssl_status": "pending",
        }
        with self._client() as client:
            resp = client.post("/rest/v1/sites", json=body)
            resp.raise_for_status()
            rows = resp.json()
        row = rows[0] if isinstance(rows, list) else rows
        return SiteRecord(
            id=UUID(str(row["id"])),
            client_id=UUID(str(row["client_id"])),
            domain=str(row["domain"]),
            status=str(row.get("status") or "provisioning"),
        )


# Module singleton used by the router (tests may call .clear()). Offline default.
CLIENT_STORE: InMemoryClientStore = InMemoryClientStore()


def get_client_store() -> ClientStore:
    """Env-gated factory (RV-PLATFORM-02).

    Returns SupabaseClientStore only when Supabase looks configured AND
    GEO_USE_SUPABASE_CLIENT_STORE=1. Otherwise returns the InMemory singleton
    so verify.py --geo never invents a live round-trip.
    """
    if os.environ.get("GEO_USE_SUPABASE_CLIENT_STORE", "").strip() != "1":
        return CLIENT_STORE
    try:
        from app.services.supabase_client import is_supabase_configured
    except Exception:
        return CLIENT_STORE
    if not is_supabase_configured():
        return CLIENT_STORE
    return SupabaseClientStore()
