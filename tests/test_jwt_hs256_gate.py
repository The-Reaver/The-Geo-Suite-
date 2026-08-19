"""HS256 opt-in gate for Supabase JWT verification — standalone battery twin.

Promoted 2026-08-08 from backend/tests/test_jwt_hs256_gate.py (pytest,
quarantined) into the run battery, per QUARANTINE.md rule 3: rewrite as a
standalone file (no `import pytest`, a `__main__` runner that prints N/N),
then delete the superseded pytest copy. Like its SSRF sibling, the prior
session left this fix's only proof in the tree ci_verify_geo.py never runs.

Proves Sentinel finding 2 is closed on BOTH verification call sites —
app.core.jwt_verify.verify_supabase_jwt and app.core.permissions.verify_token
— which both now refuse HS256 tokens unless SUPABASE_JWT_ALLOW_HS256 is set,
and, with the flag on, still reject a token signed with the wrong secret (the
flag is the opt-in, the secret match is the actual control). Env and settings
patching is done by hand with save/restore so the file runs as a plain script.
"""

import os
import sys
import time

import jwt as pyjwt

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (PROJ, os.path.join(PROJ, "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Placeholder env so importing the app package never reaches a live Supabase.
for _k, _v in {
    "SUPABASE_URL": "https://placeholder.supabase.co",
    "SUPABASE_ANON_KEY": "placeholder-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
}.items():
    os.environ.setdefault(_k, _v)

from app.core import jwt_verify, permissions

HS256_SECRET = "test-only-hs256-secret-do-not-use-in-prod"


def _make_hs256_token(secret=HS256_SECRET, **claim_overrides):
    now = int(time.time())
    claims = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "aud": "authenticated",
        "exp": now + 3600,
        "iat": now,
        "app_metadata": {"role": "owner"},
    }
    claims.update(claim_overrides)
    return pyjwt.encode(claims, secret, algorithm="HS256")


def _set_env(name, value):
    """Set or delete an env var; return a restore thunk."""
    had = name in os.environ
    old = os.environ.get(name)

    def restore():
        if had:
            os.environ[name] = old
        else:
            os.environ.pop(name, None)

    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    return restore


def _set_attr(obj, name, value):
    old = getattr(obj, name)

    def restore():
        setattr(obj, name, old)

    setattr(obj, name, value)
    return restore


# --- app.core.jwt_verify.verify_supabase_jwt --------------------------------

def test_jwtverify_hs256_rejected_when_flag_unset():
    restores = [_set_env("SUPABASE_JWT_ALLOW_HS256", None), _set_env("SUPABASE_JWT_SECRET", HS256_SECRET)]
    try:
        token = _make_hs256_token()
        try:
            jwt_verify.verify_supabase_jwt(token)
        except pyjwt.InvalidAlgorithmError:
            pass
        else:
            raise AssertionError("HS256 must be refused when the flag is unset")
    finally:
        for r in restores:
            r()


def test_jwtverify_hs256_rejected_when_flag_false():
    restores = [_set_env("SUPABASE_JWT_ALLOW_HS256", "false"), _set_env("SUPABASE_JWT_SECRET", HS256_SECRET)]
    try:
        token = _make_hs256_token()
        try:
            jwt_verify.verify_supabase_jwt(token)
        except pyjwt.InvalidAlgorithmError:
            pass
        else:
            raise AssertionError("HS256 must be refused when the flag is explicitly false")
    finally:
        for r in restores:
            r()


def test_jwtverify_hs256_accepted_when_flag_set_and_secret_correct():
    restores = [_set_env("SUPABASE_JWT_ALLOW_HS256", "true"), _set_env("SUPABASE_JWT_SECRET", HS256_SECRET)]
    try:
        claims = jwt_verify.verify_supabase_jwt(_make_hs256_token())
        assert claims["sub"] == "11111111-1111-1111-1111-111111111111", "verified claims should carry the subject"
    finally:
        for r in restores:
            r()


def test_jwtverify_hs256_rejected_when_flag_set_but_secret_wrong():
    # A forged token signed with an attacker-guessed secret must still fail even
    # with the flag on. This is what actually blocks the forged-admin-token path.
    restores = [_set_env("SUPABASE_JWT_ALLOW_HS256", "true"), _set_env("SUPABASE_JWT_SECRET", HS256_SECRET)]
    try:
        forged = _make_hs256_token(secret="attacker-guessed-secret")
        try:
            jwt_verify.verify_supabase_jwt(forged)
        except pyjwt.PyJWTError:
            pass
        else:
            raise AssertionError("a token signed with the wrong secret must be refused")
    finally:
        for r in restores:
            r()


# --- app.core.permissions.verify_token (the parallel, older path) -----------

class _FakeCredentials:
    def __init__(self, token):
        self.credentials = token


def test_permissions_hs256_rejected_when_flag_unset():
    restores = [
        _set_attr(permissions.settings, "SUPABASE_JWT_ALLOW_HS256", False),
        _set_attr(permissions.settings, "JWT_SECRET", HS256_SECRET),
    ]
    try:
        creds = _FakeCredentials(_make_hs256_token())
        try:
            permissions.verify_token(creds)
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 401, "disabled HS256 must return 401"
        else:
            raise AssertionError("HS256 must be refused by verify_token when the flag is off")
    finally:
        for r in restores:
            r()


def test_permissions_hs256_accepted_when_flag_set_and_secret_correct():
    restores = [
        _set_attr(permissions.settings, "SUPABASE_JWT_ALLOW_HS256", True),
        _set_attr(permissions.settings, "JWT_SECRET", HS256_SECRET),
    ]
    try:
        payload = permissions.verify_token(_FakeCredentials(_make_hs256_token()))
        assert payload["sub"] == "11111111-1111-1111-1111-111111111111", "verified payload should carry the subject"
    finally:
        for r in restores:
            r()


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  " + t.__name__)
            passed += 1
        except Exception as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
    print(f"{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
