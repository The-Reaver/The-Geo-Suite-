#!/usr/bin/env python3
"""Jasiah tests — ClientStore Protocol / factory / InMemory (RV-PLATFORM-02).

Standalone: no pytest. Offline only — never requires live Supabase.
"""
from __future__ import annotations

import os
import sys
from uuid import UUID, uuid4

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(PROJ, "backend")
for p in (PROJ, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.app.services.client_store import (  # noqa: E402
    CLIENT_STORE,
    ClientStore,
    InMemoryClientStore,
    SupabaseClientStore,
    get_client_store,
)


def _sample_client_data() -> dict:
    return {
        "business_name": "Acme Clinic",
        "tier": "starter",
        "client_type": "established",
        "status": "active",
        "nap": {"city": "Austin"},
        "monthly_fee_cents": 9900,
        "margin_alert_pct": 20.0,
    }


def test_inmemory_is_client_store_protocol() -> None:
    store = InMemoryClientStore()
    assert isinstance(store, ClientStore), "InMemoryClientStore must satisfy ClientStore Protocol"


def test_factory_defaults_to_inmemory_singleton() -> None:
    os.environ.pop("GEO_USE_SUPABASE_CLIENT_STORE", None)
    store = get_client_store()
    assert store is CLIENT_STORE, "factory must return InMemory singleton when live flag unset"
    assert isinstance(store, InMemoryClientStore), "default store must be InMemoryClientStore"


def test_factory_ignores_flag_without_configured_supabase() -> None:
    """Even with flag=1, placeholders must not force a live store in battery.

    This must hold regardless of what .env actually has on the machine
    running the battery (a dev box may have real Supabase creds pasted in
    for the live RLS proof). So force the settings singleton back to
    placeholder-shaped values for the duration of this one test, then
    restore it exactly, per the cache_clear()/monkeypatch pattern documented
    on app.config.get_settings.
    """
    from app.config import get_settings

    os.environ["GEO_USE_SUPABASE_CLIENT_STORE"] = "1"
    settings = get_settings()
    original_url = settings.supabase_url
    original_service_key = settings.supabase_service_role_key
    settings.supabase_url = "https://placeholder-project.supabase.co"
    settings.supabase_service_role_key = "placeholder-service-role-key"
    try:
        store = get_client_store()
        assert isinstance(store, InMemoryClientStore), (
            "factory must stay InMemory when Supabase not configured"
        )
    finally:
        settings.supabase_url = original_url
        settings.supabase_service_role_key = original_service_key
        os.environ.pop("GEO_USE_SUPABASE_CLIENT_STORE", None)


def test_inmemory_create_get_list_update_site() -> None:
    store = InMemoryClientStore()
    store.clear()
    rec = store.create_client(_sample_client_data(), owner_user_id=uuid4())
    assert isinstance(rec.id, UUID), "create_client must assign a UUID id"
    assert store.get_client(rec.id) is not None, "get_client must find created record"
    assert len(store.list_clients()) == 1, "list_clients must include created client"
    updated = store.update_client(
        rec.id,
        {**_sample_client_data(), "business_name": "Acme Updated"},
    )
    assert updated is not None and updated.business_name == "Acme Updated", (
        "update_client must persist business_name"
    )
    site = store.create_site(rec.id, "example.com")
    assert site is not None and site.status == "queued", "create_site must queue offline"
    missing = store.create_site(uuid4(), "nope.com")
    assert missing is None, "create_site for unknown client must return None"


def test_supabase_store_clear_refuses() -> None:
    live = SupabaseClientStore(
        base_url="https://example.invalid",
        headers={"apikey": "x", "Authorization": "Bearer x"},
    )
    try:
        live.clear()
        raise AssertionError("SupabaseClientStore.clear must raise NotImplementedError")
    except NotImplementedError as exc:
        assert "offline-only" in str(exc), "clear error must name offline-only reason"


def main() -> int:
    tests = [
        test_inmemory_is_client_store_protocol,
        test_factory_defaults_to_inmemory_singleton,
        test_factory_ignores_flag_without_configured_supabase,
        test_inmemory_create_get_list_update_site,
        test_supabase_store_clear_refuses,
    ]
    passed = 0
    for fn in tests:
        try:
            fn()
            passed += 1
            print(f"PASS {fn.__name__}")
        except Exception as exc:
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
