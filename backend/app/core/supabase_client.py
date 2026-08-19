"""Supabase client factory for the backend.

Note on the other supabase_client.py: app/services/supabase_client.py is a
separate, intentionally distinct module -- a lightweight httpx-based
"is Supabase configured / can we reach it" probe for the /health endpoint
only. It does not use the Python SDK client this file builds and never
runs real queries. Investigated during the 2026-08-19 split out of
Stag-GEO-Platform (where an earlier audit flagged the two same-named files
as drift-risk duplication); they turned out to serve genuinely different
purposes, so both are kept, not merged.

This module gives you two clients and one request-scoped helper.

- get_supabase_anon() returns a client bound to the anon key. Use it for
  calls that must respect row-level security on behalf of a user.
- get_supabase_admin() returns a client bound to the service-role key. Use
  it only inside trusted service code, such as creating the first owner
  membership at signup or reading invitations by token. Never expose it to
  request handlers that pass through user input unchecked.
- get_user_client(access_token) returns a client that acts as the signed-in
  user, so every query runs under that user's RLS policies.

All keys load from environment variables. No key ever lives in code.

Required environment variables:
  SUPABASE_URL              your project URL
  SUPABASE_ANON_KEY         the public anon key
  SUPABASE_SERVICE_ROLE_KEY the service-role key, backend only
"""

from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client


class SupabaseConfigError(RuntimeError):
    """Raised when a required Supabase environment variable is missing."""


def _require_env(name: str) -> str:
    """Read one environment variable or fail loudly at startup."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise SupabaseConfigError(
            f"Missing required environment variable {name}. "
            "Set it in your environment file before starting the backend."
        )
    return value


@lru_cache(maxsize=1)
def get_supabase_anon() -> Client:
    """Return the shared anon-key client.

    Queries through this client run with the anon role and obey RLS.
    Use it for public reads and for auth calls such as sign-up and
    sign-in, where Supabase itself enforces the rules.
    """
    url = _require_env("SUPABASE_URL")
    anon_key = _require_env("SUPABASE_ANON_KEY")
    return create_client(url, anon_key)


@lru_cache(maxsize=1)
def get_supabase_admin() -> Client:
    """Return the shared service-role client.

    This client bypasses RLS. Keep its use inside service-layer code
    that has already validated the caller, such as:
      - creating the client row and owner membership on first signup
      - looking up an invitation by its token
      - operator maintenance jobs

    Never hand this client to a code path that trusts raw user input.
    """
    url = _require_env("SUPABASE_URL")
    service_key = _require_env("SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, service_key)


def get_user_client(access_token: str) -> Client:
    """Return a client that acts as the signed-in user.

    The returned client attaches the user's JWT to PostgREST calls, so
    every query runs under that user's row-level security policies.
    Build one per request. Do not cache it, because tokens expire and
    differ per user.

    Args:
        access_token: the Supabase JWT taken from the Authorization
            header of the incoming request, without the Bearer prefix.

    Raises:
        ValueError: when the token is empty.
    """
    token = (access_token or "").strip()
    if not token:
        raise ValueError("get_user_client needs a non-empty access token.")

    url = _require_env("SUPABASE_URL")
    anon_key = _require_env("SUPABASE_ANON_KEY")
    client = create_client(url, anon_key)
    client.postgrest.auth(token)
    return client


def reset_cached_clients() -> None:
    """Clear cached clients. Test suites call this between cases so a
    changed environment takes effect."""
    get_supabase_anon.cache_clear()
    get_supabase_admin.cache_clear()