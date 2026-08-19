"""Auth router: signup, login, and the current-user profile.

Repaired in the Step 0 rebuild so the router imports match the function
names the service actually defines, and the response models match the
schemas. The first signup creates the client and the owner membership.
Later users join as staff through the invitations router.

Operator status is never grantable here. is_operator is seeded directly in
the database and this router only reads it.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.permissions import CurrentUser, get_current_user
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    SignupRequest,
    SignupResponse,
)
from app.services.auth_service import (
    AuthError,
    get_profile,
    log_in,
    resolve_profile_from_token,
    sign_up_owner,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResponse, status_code=201)
def signup(payload: SignupRequest) -> SignupResponse:
    """Register the first user of a new client as its owner."""
    try:
        result = sign_up_owner(payload)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return SignupResponse(
        user_id=result.user_id,
        client_id=result.client_id,
        membership_id=result.membership_id,
        role=result.role,
        session=result.session,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    """Exchange email and password for a session plus membership context."""
    try:
        session = log_in(payload)
        profile = resolve_profile_from_token(session.access_token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return LoginResponse(
        user_id=profile.user_id,
        email=profile.email,
        client_id=profile.client_id,
        role=profile.role,
        is_operator=profile.is_operator,
        session=session,
    )


@router.get("/me", response_model=MeResponse)
def me(current_user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    """Return the profile for the bearer token on the request."""
    try:
        profile = get_profile(current_user.user_id)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return MeResponse(
        user_id=profile.user_id,
        email=profile.email,
        client_id=profile.client_id,
        client_name=profile.client_name,
        role=profile.role,
        is_operator=profile.is_operator,
    )
