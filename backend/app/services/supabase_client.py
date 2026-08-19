"""Supabase service client for the backend.

This module gives the rest of the backend one place to talk to Supabase.
It reads every credential from the config loader, which in turn reads only
environment files. Nothing here holds a key in code.

The health check degrades gracefully. When you run the repo on the
placeholder values from .env.example, the check reports "not_configured"
instead of raising, so /health still responds and local development never
blocks on live keys.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings

# Values from .env.example carry one of these markers. When a marker shows
# up in the Supabase URL or key, the platform treats Supabase as not yet
# configured and skips the network call.
_PLACEHOLDER_MARKERS: tuple[str, ...] = (
    "your-project",
    "your_supabase",
    "placeholder",
    "changeme",
    "example",
)

# Short timeout so a slow or unreachable database never stalls /health.
_HEALTH_TIMEOUT_SECONDS: float = 3.0


def _looks_like_placeholder(value: str) -> bool:
    """Return True when a config value still carries a placeholder marker."""
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def is_supabase_configured() -> bool:
    """Return True when real-looking Supabase credentials are present.

    You get False whenever the URL or the service role key is empty or
    still matches the placeholder values shipped in .env.example.
    """
    settings = get_settings()
    if _looks_like_placeholder(settings.supabase_url):
        return False
    if _looks_like_placeholder(settings.supabase_service_role_key):
        return False
    return True


def _service_headers() -> dict[str, str]:
    """Build the headers Supabase expects for service-role requests."""
    settings = get_settings()
    key = settings.supabase_service_role_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


def get_supabase_http_client() -> httpx.AsyncClient:
    """Create an async HTTP client bound to your Supabase project.

    Later modules reuse this factory for REST and auth calls so every
    request shares the same base URL, headers, and timeout policy. The
    caller owns the client and closes it, ideally through an async
    context manager.
    """
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=settings.supabase_url.rstrip("/"),
        headers=_service_headers(),
        timeout=httpx.Timeout(_HEALTH_TIMEOUT_SECONDS),
    )


async def check_database() -> dict[str, Any]:
    """Report database reachability for the /health endpoint.

    Returns a dictionary with a "status" field and a "detail" field.
    Possible statuses:

    - "ok": Supabase answered the REST endpoint with a success code.
    - "not_configured": the env values are still placeholders, which is
      the expected state on a fresh clone of the repo.
    - "unreachable": the network call failed or timed out.
    - "error": Supabase answered with a non-success status code.
    """
    if not is_supabase_configured():
        return {
            "status": "not_configured",
            "detail": (
                "Supabase credentials are placeholders. "
                "Paste real values into your .env file to connect."
            ),
        }

    try:
        async with get_supabase_http_client() as client:
            response = await client.get("/rest/v1/")
    except httpx.HTTPError as exc:
        return {
            "status": "unreachable",
            "detail": f"Could not reach Supabase: {exc.__class__.__name__}",
        }

    if response.is_success:
        return {
            "status": "ok",
            "detail": "Supabase REST endpoint responded.",
        }

    return {
        "status": "error",
        "detail": f"Supabase responded with HTTP {response.status_code}.",
    }