"""Compatibility shim over the canonical settings loader (app/config.py).

2026-08-08 GEO Brain Trust review, config-canonicalization decision (open item,
HELD note): GEO had three config sources reading divergent env var names —
app/config.py (typed, rich, used by the data layer), this module (a separate
thin Settings class), and app/core/jwt_verify.py (raw os.environ). An operator
setting Railway env vars from .env.example fed the data layer but not the auth
layer, because permissions.py read env `JWT_SECRET` while everything else read
`SUPABASE_JWT_SECRET`.

Ruling (operator, 2026-08-08): unify on app/config.py as the single source of
truth. This module no longer defines its own settings; it exposes the historical
UPPERCASE names that permissions.py and facts_repository.py read, every value
sourced from app.config.get_settings(). Env var names are now unified:

    SUPABASE_URL          -> supabase_url
    SUPABASE_KEY (legacy) -> supabase_service_role_key   (the server-side key
                             the data layer needs; the old bare SUPABASE_KEY env
                             var, which no .env ever set, is retired)
    JWT_SECRET (legacy)   -> supabase_jwt_secret          (env SUPABASE_JWT_SECRET)
    SUPABASE_JWT_ALLOW_HS256 -> supabase_jwt_allow_hs256

Attributes stay writable so the JWT-gate battery can monkeypatch
permissions.settings.JWT_SECRET / .SUPABASE_JWT_ALLOW_HS256 for a single test
and restore them, exactly as before. In deployment the process environment is
loaded once by app.config; this shim snapshots it at import, which is correct
because those values do not change during a running process.
"""
from app.config import get_settings


class _CoreSettingsShim:
    """Uppercase-named, writable view over the canonical Settings."""

    def __init__(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        s = get_settings()
        self.SUPABASE_URL = s.supabase_url
        # Server-side key: this shim historically fed facts_repository's
        # create_client(url, key), which needs a real server key, not the anon.
        self.SUPABASE_KEY = s.supabase_service_role_key
        self.JWT_SECRET = s.supabase_jwt_secret
        self.SUPABASE_JWT_ALLOW_HS256 = s.supabase_jwt_allow_hs256


settings = _CoreSettingsShim()
