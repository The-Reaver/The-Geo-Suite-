# SPEC: SPEC_CCC_M6_AGENTIC
"""CMS connect / schema / brief push behind outbox + circuit breaker (EXE-6.2)."""
from __future__ import annotations

from typing import Any, Callable

from app.core.resilience import CircuitBreaker, CircuitOpenError
from app.services.worker.outbox import InMemoryDedupStore, handle_idempotent


class FakeCmsGateway:
    """Offline CMS adapter for tests — counts mutations."""

    def __init__(self, *, configured: bool = True):
        self.configured = configured
        self.calls: list[dict] = []

    def connect(self, config: dict) -> dict:
        if not self.configured or not (config or {}).get("api_key"):
            return {"status": "AUTH_FAILED", "reason": "CMS credentials not configured"}
        return {"status": "OK", "site_id": (config or {}).get("site_id") or "site-1"}

    def write_schema(self, page_id: str, jsonld: dict, *, draft: bool) -> dict:
        self.calls.append({"op": "schema", "page_id": page_id, "draft": draft})
        return {"status": "OK", "page_id": page_id, "draft": draft, "applied": True}

    def write_brief(self, brief: dict, *, draft: bool) -> dict:
        self.calls.append({"op": "brief", "draft": draft})
        return {"status": "OK", "draft": draft, "applied": True}


def connect_cms(config: dict, *, gateway: Any = None) -> dict:
    """EXE-6.2.1 — unconfigured → AUTH_FAILED."""
    gw = gateway if gateway is not None else FakeCmsGateway(configured=bool((config or {}).get("api_key")))
    return gw.connect(config or {})


def _mutate_via_outbox(
    *,
    idempotency_key: str,
    dedup: InMemoryDedupStore | None,
    breaker: CircuitBreaker | None,
    fn: Callable[[], dict],
) -> dict:
    dedup = dedup or InMemoryDedupStore()
    key = (idempotency_key or "").strip()
    if not key:
        return {
            "status": "INVALID",
            "reason": "idempotency key required — refusing mutation without outbox key",
        }

    def _run() -> dict:
        if breaker is None:
            return fn()
        try:
            return breaker.call(fn)
        except CircuitOpenError as exc:
            return {
                "status": "CIRCUIT_OPEN",
                "reason": str(exc) or "circuit open — CMS unavailable",
                "applied": False,
            }

    return handle_idempotent(dedup, key, _run)


def inject_schema(
    page_id: str,
    jsonld: dict,
    *,
    draft: bool = True,
    gateway: Any = None,
    dedup: InMemoryDedupStore | None = None,
    breaker: CircuitBreaker | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """EXE-6.2.2 — JSON-LD must be supplied (from M3); default draft=True."""
    if not jsonld:
        return {
            "status": "INSUFFICIENT_DATA",
            "reason": "jsonld missing — refuse to invent ratings/schema",
            "applied": False,
        }
    if any(k in (jsonld or {}) for k in ("aggregateRating", "ratingValue")) and not (
        jsonld or {}
    ).get("from_m3"):
        # Soft guard: only accept ratings when marked as M3-sourced
        if not (jsonld or {}).get("source_module") == "m3":
            return {
                "status": "REFUSED",
                "reason": "ratings in JSON-LD must come from M3 generate_attribute_rich_jsonld",
                "applied": False,
            }
    gw = gateway if gateway is not None else FakeCmsGateway()
    key = idempotency_key or f"schema:{page_id}:{draft}"

    def _fn() -> dict:
        return gw.write_schema(page_id, jsonld, draft=draft)

    return _mutate_via_outbox(idempotency_key=key, dedup=dedup, breaker=breaker, fn=_fn)


def push_content_brief(
    brief: dict,
    *,
    draft: bool = True,
    gateway: Any = None,
    dedup: InMemoryDedupStore | None = None,
    breaker: CircuitBreaker | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """EXE-6.2.3 — enqueue via outbox; draft default."""
    if not brief:
        return {"status": "EMPTY", "reason": "brief missing", "applied": False}
    gw = gateway if gateway is not None else FakeCmsGateway()
    key = idempotency_key or f"brief:{(brief or {}).get('id') or 'anon'}:{draft}"

    def _fn() -> dict:
        return gw.write_brief(brief, draft=draft)

    return _mutate_via_outbox(idempotency_key=key, dedup=dedup, breaker=breaker, fn=_fn)


def onpage_suggestions(cii_gaps: dict, page_text: str) -> list[dict]:
    """EXE-6.2.4 — suggestion list from CII gaps; offline heuristic."""
    gaps = (cii_gaps or {}).get("gaps") or (cii_gaps or {}).get("missing_entities") or []
    text = (page_text or "").lower()
    out = []
    for g in gaps:
        name = g if isinstance(g, str) else (g.get("entity") or g.get("name") or str(g))
        present = name.lower() in text
        out.append(
            {
                "suggestion": f"Consider covering '{name}' on-page" if not present else f"'{name}' already present",
                "entity": name,
                "present": present,
                "priority": "high" if not present else "low",
            }
        )
    return out
