"""Pydantic schemas for authentication.

Repaired in the Step 0 auth, accounts, and invitations rebuild so the
schemas, the service, and the router all agree on one shape and match the
real database schema in supabase/migrations.

The first signup creates the client and the owner membership. is_operator
is read only here; no request body can set it. It lives only in the
database seed for the founder operator.
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    """Payload for the first signup, which creates a client and its owner."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    business_name: str = Field(min_length=1, max_length=120)
    full_name: Optional[str] = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    """Payload for email and password login through Supabase auth."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class SessionResponse(BaseModel):
    """Session tokens returned by Supabase after signup or login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SignupResponse(BaseModel):
    """Everything the frontend needs right after a successful signup."""

    user_id: str
    client_id: str
    membership_id: str
    role: str
    session: SessionResponse


class LoginResponse(BaseModel):
    """Everything the frontend needs right after a successful login."""

    user_id: str
    email: str
    client_id: str
    role: str
    is_operator: bool
    session: SessionResponse


class MeResponse(BaseModel):
    """Response for the current-user endpoint used by route guards."""

    user_id: str
    email: str
    client_id: str
    client_name: str
    role: str
    is_operator: bool
