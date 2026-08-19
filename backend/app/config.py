"""Configuration loader for the GEO Suite backend.

Every secret comes from environment variables, loaded from a .env file in
local development and from the host environment in deployment. No key ever
lives in code. Each field carries a placeholder default so the repo runs
locally before you paste real values. See .env.example at the repo root for
the full list of key names and where each one comes from.

Trimmed 2026-08-19 from Stag-GEO-Platform's app/config.py during the GEO
Suite repo split: dropped every tool-set-only setting (Stripe, Twilio,
Resend, Railway-specific fields, prospect retention) and the
Perplexity/OpenAI/Gemini keys (those only fed the excluded analytics/*
FakeAdapter-by-default pipeline, confirmed via a repo-wide grep that no
copied v1 module references any of them). Add settings back here only when
a real v1 feature needs them.
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# The single env file lives at the repo root (see .env.example there). Resolve
# it from this file's location so it loads no matter what directory the process
# starts in -- running from backend/ (as uvicorn and the boot check do) must not
# pick up a stray backend/.env. In deployment Railway injects real env vars and
# this file simply won't exist, which is fine: the host environment wins.
_REPO_ROOT_ENV = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".env")
)


class Settings(BaseSettings):
    """Typed view of every environment variable the backend reads."""

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -------------------------------------------------------
    app_env: str = "local"
    app_name: str = "geo-suite-backend"
    port: int = 8000
    # Comma-separated list of origins allowed to call this API.
    frontend_origin: str = "http://localhost:3000"
    log_level: str = "INFO"

    # --- Supabase ----------------------------------------------------------
    # supabase_url and supabase_anon_key serve client-scoped reads under RLS.
    # supabase_service_role_key bypasses RLS and stays server-side only.
    # supabase_db_url is the direct Postgres connection string the health
    # check uses.
    supabase_url: str = "https://placeholder-project.supabase.co"
    supabase_anon_key: str = "placeholder-anon-key"
    supabase_service_role_key: str = "placeholder-service-role-key"
    supabase_db_url: str = (
        "postgresql://postgres:placeholder@localhost:5432/postgres"
    )
    supabase_jwt_secret: str = "placeholder-jwt-secret"
    # Off by default -- a live HS256 secret is a forged-admin-token path the
    # moment it leaks. Only set it for a genuinely legacy Supabase project
    # still issuing HS256; modern projects sign RS256/ES256.
    supabase_jwt_allow_hs256: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origins(self) -> list[str]:
        """Split the configured origins into a clean list for CORS setup."""
        return [
            origin.strip()
            for origin in self.frontend_origin.split(",")
            if origin.strip()
        ]

    def using_placeholders(self) -> list[str]:
        """Return the names of secrets still holding placeholder values.

        The health route surfaces this list in local mode so you can see at
        a glance which keys still need real values pasted into .env.
        """
        placeholder_markers = {
            "supabase_url": "placeholder-project",
            "supabase_anon_key": "placeholder-anon-key",
            "supabase_service_role_key": "placeholder-service-role-key",
            "supabase_db_url": "placeholder@",
            "supabase_jwt_secret": "placeholder-jwt-secret",
        }
        return [
            field
            for field, marker in placeholder_markers.items()
            if marker in getattr(self, field)
        ]


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance.

    Import this function and call it inside request handlers or use it as a
    FastAPI dependency. The cache means the .env file loads once per process.
    Tests can call get_settings.cache_clear() to reload after monkeypatching
    environment variables.
    """
    return Settings()
