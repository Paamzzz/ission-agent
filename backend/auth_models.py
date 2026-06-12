"""
Pydantic models for GitHub OAuth authentication.
"""

from datetime import datetime

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Public user data returned to the frontend. Never includes the token."""

    login: str
    avatar_url: str
    name: str | None


class SessionData(BaseModel):
    """Server-side session. Never serialized to any HTTP response."""

    access_token: str
    user: AuthenticatedUser
    expires_at: datetime


class CallbackRequest(BaseModel):
    """Payload received from the frontend after the GitHub redirect."""

    code: str
    code_verifier: str


class AuthLoginResponse(BaseModel):
    """Response for GET /auth/github/login."""

    authorization_url: str


class ErrorResponse(BaseModel):
    detail: str
