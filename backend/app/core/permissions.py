from functools import lru_cache

import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from .config import settings

security = HTTPBearer()

# 2026-08-16: CurrentUser/get_current_user were imported by app/routers/auth.py
# (the /auth/me endpoint) but never defined anywhere in the codebase -- a real,
# previously undetected bug, only surfaced now because auth.router had also
# never been mounted in main.py (nothing had ever actually imported this
# module before). Implemented here rather than stubbed: reuses
# resolve_profile_from_token, which already does real verification via
# Supabase's own auth.get_user(), not a re-implementation of token validation.
# ProfileResult already carries exactly the fields /me needs (user_id, email,
# client_id, client_name, role, is_operator) -- CurrentUser is that same type,
# named for what auth.py already expects to depend on. No circular import:
# auth_service.py imports only from app.core.supabase_client/app.schemas.auth,
# never from this module.
from app.services.auth_service import AuthError, ProfileResult as CurrentUser, resolve_profile_from_token


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> CurrentUser:
    try:
        return resolve_profile_from_token(credentials.credentials)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


# 2026-08-16: accounts.py, invitations.py, and tools_missed_call.py were all
# written against a membership-based auth model (CurrentMembership,
# require_member, an owner-gated dependency of the same shape) that was never
# actually implemented -- another half of the same previously-undetected bug
# as CurrentUser/get_current_user above (these routers had never been
# imported before today, so nothing had ever hit this).
#
# CurrentMembership is the same underlying type as CurrentUser (ProfileResult
# already carries client_id/role/is_operator, exactly what a "membership"
# means here) -- not a duplicate parallel model, just named for what these
# routers already expect to depend on.
#
# Deliberately NOT named require_owner: that name is already taken by the
# dict-based JWT-payload version above, used throughout sales_preview.py and
# other already-live routes. Reusing the name for an incompatible return type
# would silently break every existing caller. require_owner_membership is a
# distinct function; accounts.py/invitations.py/tools_missed_call.py's own
# imports were updated to match, not the other way around.
CurrentMembership = CurrentUser


def require_member(current_user: CurrentUser = Depends(get_current_user)) -> CurrentMembership:
    """Any authenticated member of a client -- no role restriction beyond
    having a real, resolvable session."""
    return current_user


def require_owner_membership(current_user: CurrentUser = Depends(get_current_user)) -> CurrentMembership:
    """Owner or platform operator only. Mirrors require_owner's dict-based
    role check above, but against ProfileResult's real role/is_operator
    fields instead of a raw JWT app_metadata claim."""
    if current_user.role != "owner" and not current_user.is_operator:
        raise HTTPException(status_code=403, detail="Owner access required")
    return current_user

# 2026-08-17: was a plain function, a brand-new uncached PyJWKClient per
# call -- every request to require_owner/require_sales_agent (the entire
# sales wizard, and today the first time any of it became reachable at
# all) made a live HTTPS round-trip to Supabase's JWKS endpoint before
# doing anything else. jwt_verify.py already has the correct pattern
# (lru_cache + cache_keys=True, PyJWKClient caches the fetched keys itself
# so verification stops hitting the network after the first call in this
# process) -- mirrored here instead of inventing a second one.
@lru_cache(maxsize=1)
def get_jwks_client():
    jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    token = credentials.credentials
    try:
        # Get unverified header to check alg
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg")
        
        if alg in ["RS256", "ES256"]:
            jwks_client = get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience="authenticated"
            )
        elif alg == "HS256":
            # Legacy fallback. Off by default: a live HS256 secret sitting in
            # .env is a forged-admin-token path the moment it leaks, see
            # jwt_verify.py's module docstring and the 2026-08-08 GEO Brain
            # Trust review, Sentinel finding 2. Set SUPABASE_JWT_ALLOW_HS256
            # only for a genuinely legacy Supabase project.
            if not settings.SUPABASE_JWT_ALLOW_HS256:
                raise HTTPException(
                    status_code=401,
                    detail="HS256 verification is disabled. Set "
                    "SUPABASE_JWT_ALLOW_HS256=true only for a genuinely "
                    "legacy Supabase project.",
                )
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated"
            )
        else:
            raise HTTPException(status_code=401, detail="Unsupported signing algorithm")
            
        return payload
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

def require_admin(payload: dict = Depends(verify_token)) -> dict:
    # Assuming role is encoded in the JWT app_metadata or user_metadata
    role = payload.get("app_metadata", {}).get("role")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload

def require_owner(payload: dict = Depends(verify_token)) -> dict:
    role = payload.get("app_metadata", {}).get("role")
    if role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Owner access required")
    return payload

def require_sales_agent(payload: dict = Depends(verify_token)) -> dict:
    """Phase 0 of the sales-agent master panel build (2026-08-16 operator
    ruling: own hires, TONY LLC / Smart Seed Tech, 2-5 agents now scaling to
    a large team within 15 days). Every route a door-to-door agent's own
    pitch flow needs (audit, report, kit, saving a lead, listing their own
    prospects) sits behind this instead of require_owner. owner/admin keep
    full access, same as before -- this only widens the gate, it narrows
    nothing an owner could already do.

    Per the Offline Architecture Brain Trust review's own Phase 0 scope:
    this function plus the "sales_agent" role check is the code half of
    "land the sales_agent role." The other half -- setting app_metadata.role
    = "sales_agent" on a real Supabase user -- happens in the Supabase
    dashboard/Auth admin API, which this codebase cannot and should not do
    on its own (creating or modifying a real user account is the operator's
    action, not code's)."""
    role = payload.get("app_metadata", {}).get("role")
    if role not in ["sales_agent", "owner", "admin"]:
        raise HTTPException(status_code=403, detail="Sales agent access required")
    return payload


def require_lawyer(payload: dict = Depends(verify_token)) -> dict:
    """Compliance ratification mini-slice 2 (2026-08-22 operator decision:
    a real, separate lawyer reviews and ratifies/rejects compliance notes,
    not the operator acting through their own owner login). Mirrors
    require_sales_agent's exact shape and precedent above: owner/admin
    keep full access (this only widens the gate, it narrows nothing an
    owner could already do), and the other half of "land the lawyer
    role" -- setting app_metadata.role = "lawyer" on a real Supabase user
    for whoever the actual lawyer is -- happens in the Supabase dashboard/
    Auth admin API, which this codebase cannot and should not do on its
    own, same as require_sales_agent's own docstring already states for
    that role."""
    role = payload.get("app_metadata", {}).get("role")
    if role not in ["lawyer", "owner", "admin"]:
        raise HTTPException(status_code=403, detail="Lawyer access required")
    return payload
