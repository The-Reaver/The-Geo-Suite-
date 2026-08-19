"""Verify Supabase-issued access tokens.

Supabase signs access tokens one of two ways:

  * Legacy projects use a symmetric HS256 secret (SUPABASE_JWT_SECRET).
  * Current projects use an asymmetric key (ES256 or RS256) whose public
    half is published at the project JWKS endpoint
    ``{SUPABASE_URL}/auth/v1/.well-known/jwks.json``.

This module verifies both. It reads the token header's ``alg``: asymmetric
algorithms verify against the JWKS public key selected by the token's ``kid``;
HS256 verifies against the shared secret. Callers get the decoded claims or a
``jwt.PyJWTError`` (which includes JWKS lookup failures), so the existing 401
handling in the auth dependencies covers every failure path unchanged.

2026-08-08, GEO Brain Trust review, Sentinel finding 2: the HS256 secret this
module falls back to is already populated in a live ``.env``. That makes the
practical risk of a forged HS256 admin token real today, not theoretical, the
moment that secret ever leaves the operator's machine. The HS256 branch is
gated behind ``SUPABASE_JWT_ALLOW_HS256`` (default off) so a project that only
ever issues asymmetric tokens has no live HS256 acceptance path at all.

2026-08-08 config-canonicalization ruling: this module reads SUPABASE_URL,
SUPABASE_JWT_SECRET and SUPABASE_JWT_ALLOW_HS256 straight from the process
environment on purpose — that is the same environment app/config.py loads from,
so the var *names* are the single source of truth shared with the typed loader
and its app/core/config.py shim. Reading env directly here (rather than the
cached get_settings()) is what lets the JWT-gate battery toggle these three vars
per-test without a cache-clear. Names unified; no divergent JWT_SECRET path.
"""

import os
from functools import lru_cache

import jwt
from jwt import PyJWKClient

# Supabase stamps this audience on every user access token.
SUPABASE_JWT_AUDIENCE = "authenticated"

# Algorithms whose keys live in the JWKS rather than in SUPABASE_JWT_SECRET.
_ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")

# Every Supabase token must carry a subject and an expiry.
_REQUIRED_CLAIMS = {"require": ["sub", "exp"]}

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _hs256_allowed() -> bool:
    """Read the HS256 opt-in flag fresh on every call, so tests can toggle it
    with monkeypatch.setenv without reimporting this module."""
    return os.environ.get("SUPABASE_JWT_ALLOW_HS256", "").strip().lower() in _TRUE_VALUES


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    """Return a cached JWKS client for the project.

    PyJWKClient caches the fetched keys, so verification does not hit the
    network on every request. The client is built once per process from
    SUPABASE_URL.
    """
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    if not url:
        raise jwt.InvalidKeyError(
            "SUPABASE_URL is not set, so asymmetric tokens cannot be verified."
        )
    return PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json", cache_keys=True)


def verify_supabase_jwt(token: str) -> dict:
    """Verify a Supabase access token and return its claims.

    Raises a ``jwt.PyJWTError`` subclass on any verification failure, including
    an unfetchable or mismatched JWKS key. The auth dependencies map that to a
    401 exactly as they did for HS256.
    """
    header = jwt.get_unverified_header(token)
    algorithm = header.get("alg", "")

    if algorithm in _ASYMMETRIC_ALGORITHMS:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=list(_ASYMMETRIC_ALGORITHMS),
            audience=SUPABASE_JWT_AUDIENCE,
            options=_REQUIRED_CLAIMS,
        )

    # Legacy symmetric signing. Off by default, see the module docstring.
    if not _hs256_allowed():
        raise jwt.InvalidAlgorithmError(
            "HS256 verification is disabled. Set SUPABASE_JWT_ALLOW_HS256=true "
            "only for a genuinely legacy Supabase project still issuing HS256 "
            "tokens."
        )
    secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if not secret:
        raise jwt.InvalidKeyError(
            "SUPABASE_JWT_SECRET is not set, so HS256 tokens cannot be verified."
        )
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience=SUPABASE_JWT_AUDIENCE,
        options=_REQUIRED_CLAIMS,
    )
