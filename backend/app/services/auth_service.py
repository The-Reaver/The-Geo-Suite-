"""Authentication service: signup, login, and profile resolution.

Repaired in the Step 0 rebuild so every table and column it touches exists
in supabase/migrations, and so the function names match what the router
imports.

Key schema facts this service relies on:
  - A database trigger, handle_new_user, mirrors every auth user into
    public.users automatically. This service never inserts a users row.
  - public.clients has only id, name, created_at. There is no
    owner_user_id column; ownership is expressed by a memberships row with
    role 'owner'.
  - is_operator lives on public.users and is seeded directly in the
    database. No path in this service ever sets it.
  - Secrets load from environment configuration through the Supabase client
    factory, never from code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.supabase_client import get_supabase_admin, get_supabase_anon
from app.schemas.auth import LoginRequest, SessionResponse, SignupRequest

logger = logging.getLogger(__name__)

OWNER_ROLE = "owner"
STAFF_ROLE = "staff"


class AuthError(Exception):
    """Raised when an auth operation fails in a way the caller must handle."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class SignupResult:
    """The full outcome of a first signup: user, client, membership, session."""

    user_id: str
    client_id: str
    membership_id: str
    role: str
    session: SessionResponse


@dataclass(frozen=True)
class ProfileResult:
    """The caller resolved to user, client, role, and operator flag."""

    user_id: str
    email: str
    client_id: str
    client_name: str
    role: str
    is_operator: bool


def sign_up_owner(payload: SignupRequest) -> SignupResult:
    """Create the auth user, the client, and the owner membership.

    The handle_new_user trigger creates the public.users row from the auth
    user, so we only insert the client and the owner membership here. If any
    step after user creation fails, we remove the auth user so the email
    stays free for a retry.
    """
    admin = get_supabase_admin()

    # 2026-08-17: found live, via a real signup + sales-wizard call: this
    # never set app_metadata.role, so every route gated by require_owner /
    # require_sales_agent (app/core/permissions.py, both read
    # payload["app_metadata"]["role"] off the raw JWT) rejected a brand-new
    # owner with 403 immediately after signup, even though the memberships
    # row below correctly says role=owner. The membership-based checks
    # (require_owner_membership, used by accounts.py/invitations.py) read
    # the real memberships table instead and were never affected. This gap
    # hits every router still on the older dict/JWT-based dependency --
    # confirmed via import, that's clients.py, client.py, sites.py,
    # prospecting.py, and sales_preview.py (the sales wizard), not just the
    # one router this was first found through. Setting it here fixes new
    # signups; it does not backfill any account created before this fix,
    # since none should exist yet on a database that only had its schema
    # applied for the first time today. Two other things worth knowing
    # about the scope of this fix, not closed by it: (1) nothing currently
    # updates app_metadata after signup, so a future promotion/demotion
    # path (there isn't one yet) would need to keep both role systems in
    # sync itself; (2) invitation_service.py's accept_invitation() inserts
    # memberships.role='staff' and never sets app_metadata either -- a
    # currently-inert gap only because nothing grants sales_agent-gated
    # access to staff yet, not because it's handled.
    created = admin.auth.admin.create_user(
        {
            "email": payload.email,
            "password": payload.password,
            "email_confirm": True,
            "user_metadata": {"full_name": payload.full_name or ""},
            "app_metadata": {"role": OWNER_ROLE},
        }
    )
    user = getattr(created, "user", None)
    if user is None or user.id is None:
        raise AuthError("Signup failed. The account could not be created.", 400)
    user_id = str(user.id)

    try:
        client_row = admin.table("clients").insert({"name": payload.business_name}).execute()
        if not client_row.data:
            raise AuthError("Signup failed while creating the client record.", 500)
        client_id = str(client_row.data[0]["id"])

        membership_row = (
            admin.table("memberships")
            .insert({"client_id": client_id, "user_id": user_id, "role": OWNER_ROLE})
            .execute()
        )
        if not membership_row.data:
            raise AuthError("Signup failed while creating the owner membership.", 500)
        membership_id = str(membership_row.data[0]["id"])
    except AuthError:
        _cleanup_orphan_user(user_id)
        raise
    except Exception as exc:
        _cleanup_orphan_user(user_id)
        logger.exception("Signup rollback for user %s", user_id)
        raise AuthError("Signup failed. Please try again.", 500) from exc

    session = log_in(LoginRequest(email=payload.email, password=payload.password))
    logger.info("New client %s created by owner %s", client_id, user_id)

    return SignupResult(
        user_id=user_id,
        client_id=client_id,
        membership_id=membership_id,
        role=OWNER_ROLE,
        session=session,
    )


def log_in(payload: LoginRequest) -> SessionResponse:
    """Sign the user in with email and password and return session tokens."""
    anon = get_supabase_anon()
    try:
        result = anon.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as exc:
        logger.info("Login rejected for %s", payload.email)
        raise AuthError("Invalid email or password.", 401) from exc

    session = getattr(result, "session", None)
    user = getattr(result, "user", None)
    if session is None or user is None:
        raise AuthError("Invalid email or password.", 401)

    return SessionResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        token_type="bearer",
        expires_in=session.expires_in or 3600,
    )


def get_profile(user_id: str) -> ProfileResult:
    """Resolve one user id into user, client, role, and operator flag.

    Reads is_operator from public.users (never from memberships) and the
    client name through the memberships to clients relation.
    """
    admin = get_supabase_admin()

    user_row = (
        admin.table("users")
        .select("id, email, is_operator")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if not user_row.data:
        raise AuthError("Your account profile was not found.", 404)

    # 2026-08-17: no ORDER BY -- for a user with more than one membership
    # (memberships.unique(user_id, client_id) allows several different
    # client_ids per user), which client_id .limit(1) returns was
    # arbitrary per-request. Ordered by created_at so it's always the
    # membership they've held longest, deterministically, not whichever
    # row Postgres happens to return first.
    membership = (
        admin.table("memberships")
        .select("client_id, role, clients(name)")
        .eq("user_id", user_id)
        .order("created_at")
        .limit(1)
        .maybe_single()
        .execute()
    )
    if not membership.data:
        raise AuthError("Your account has no active membership.", 403)

    client = membership.data.get("clients") or {}
    return ProfileResult(
        user_id=user_id,
        email=user_row.data.get("email", ""),
        client_id=str(membership.data["client_id"]),
        client_name=client.get("name", ""),
        role=membership.data["role"],
        is_operator=bool(user_row.data.get("is_operator", False)),
    )


def resolve_profile_from_token(access_token: str) -> ProfileResult:
    """Verify a bearer token and return the caller's profile."""
    anon = get_supabase_anon()
    try:
        result = anon.auth.get_user(access_token)
    except Exception as exc:
        raise AuthError("Your session is invalid or expired.", 401) from exc
    user = getattr(result, "user", None)
    if user is None or user.id is None:
        raise AuthError("Your session is invalid or expired.", 401)
    return get_profile(str(user.id))


def _cleanup_orphan_user(user_id: str) -> None:
    """Remove an auth user left behind by a failed signup."""
    try:
        get_supabase_admin().auth.admin.delete_user(user_id)
        logger.info("Removed orphan auth user %s after failed signup", user_id)
    except Exception:
        logger.exception("Could not remove orphan auth user %s", user_id)
