"""
auth_router.py — FastAPI router for GitHub OAuth authentication.

Provides:
  - sessions: in-memory session store
  - get_current_token: FastAPI dependency that reads the session cookie
    and returns the user's access token, or None if the session is
    missing or expired.

OAuth endpoints (login, callback, me, logout) are added in tasks 3.1–3.4.
"""

import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from auth_models import AuthenticatedUser, AuthLoginResponse, CallbackRequest, SessionData

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

sessions: dict[str, SessionData] = {}
"""
Maps session_id (secrets.token_urlsafe(32)) → SessionData.

NOTE: This is intentionally in-process storage for the current sprint.
A Redis-backed store is the planned follow-up for production.
"""

# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def get_current_token(request: Request) -> str | None:
    """
    FastAPI dependency that resolves the caller's GitHub access token.

    Reads the ``session_id`` cookie, looks up the corresponding
    :class:`SessionData` entry, verifies it has not expired, and returns
    the stored ``access_token``.

    Returns ``None`` when:
    - the ``session_id`` cookie is absent,
    - no matching session exists in the store, or
    - the session has expired (``expires_at`` is in the past).

    Expired sessions are removed from the store on access.
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    session = sessions.get(session_id)
    if session is None:
        return None

    if session.expires_at < datetime.utcnow():
        # Clean up the expired entry eagerly
        sessions.pop(session_id, None)
        return None

    return session.access_token


# ---------------------------------------------------------------------------
# GET /auth/github/login
# ---------------------------------------------------------------------------

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_DEFAULT_REDIRECT_URI = "http://localhost:4200/auth/callback"


@router.get("/auth/github/login", response_model=AuthLoginResponse)
def github_login() -> AuthLoginResponse:
    """
    Return the GitHub authorization URL for the OAuth flow.

    GitHub does NOT support PKCE (code_challenge / code_verifier), so
    we use a plain state-only flow.  The frontend generates a ``state``
    value via the Web Crypto API, stores it in sessionStorage, and appends
    it to the URL returned here before redirecting the user.

    Returns 503 when ``GITHUB_CLIENT_ID`` is not configured.
    """
    client_id = os.getenv("GITHUB_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth not configured",
        )

    redirect_uri = os.getenv("GITHUB_REDIRECT_URI", _DEFAULT_REDIRECT_URI)

    # NOTE: Do NOT include code_challenge_method — GitHub does not support PKCE.
    # The state parameter is appended by the frontend after generating it via
    # the Web Crypto API.
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "repo user",
    }

    authorization_url = f"{_GITHUB_AUTHORIZE_URL}?{urlencode(params)}"
    return AuthLoginResponse(authorization_url=authorization_url)


# ---------------------------------------------------------------------------
# POST /auth/github/callback
# ---------------------------------------------------------------------------

_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"


@router.post("/auth/github/callback", response_model=AuthenticatedUser)
async def github_callback(
    body: CallbackRequest,
    response: Response,
) -> AuthenticatedUser:
    """
    Exchange a GitHub authorization code for a session.

    Accepts ``{code}``, exchanges the code for a GitHub access token,
    fetches the user's profile, creates a server-side session, and returns
    the public :class:`AuthenticatedUser` data.

    NOTE: GitHub does NOT support PKCE.  The ``code_verifier`` field in
    :class:`CallbackRequest` is intentionally ignored here — it is kept in
    the model only for forward-compatibility and is never forwarded to GitHub.

    The session ID is delivered via an ``HttpOnly; SameSite=Lax``
    cookie — the access token is never included in the response body.

    Returns:
        - **200** with :class:`AuthenticatedUser` on success.
        - **400** if GitHub returns an error during token exchange.
        - **503** if ``GITHUB_CLIENT_ID`` or ``GITHUB_CLIENT_SECRET`` are
          not configured.
    """
    # 1. Validate required env vars
    client_id = os.getenv("GITHUB_CLIENT_ID")
    client_secret = os.getenv("GITHUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth not configured",
        )

    # 2. Resolve redirect_uri
    redirect_uri = os.getenv("GITHUB_REDIRECT_URI", _DEFAULT_REDIRECT_URI)

    # 3. Exchange code for token.
    # NOTE: code_verifier is deliberately excluded — GitHub does not support PKCE.
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            _GITHUB_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": body.code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )

    token_data = token_response.json()

    # 4. Return 400 on GitHub error — do NOT log code or partial token
    if "error" in token_data:
        raise HTTPException(
            status_code=400,
            detail=token_data.get("error_description", "GitHub OAuth error"),
        )

    access_token: str = token_data["access_token"]

    # 5. Fetch user profile
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            _GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )

    if user_response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail="Failed to fetch GitHub user profile",
        )

    user_json = user_response.json()
    user_data = AuthenticatedUser(
        login=user_json["login"],
        avatar_url=user_json["avatar_url"],
        name=user_json.get("name"),
    )

    # 6. Generate session ID
    session_id = secrets.token_urlsafe(32)

    # 7. Compute session expiry
    ttl_hours = int(os.getenv("SESSION_TTL_HOURS", "8"))
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

    # 8. Persist session
    sessions[session_id] = SessionData(
        access_token=access_token,
        user=user_data,
        expires_at=expires_at,
    )

    # 9. Set HttpOnly session cookie.
    # SameSite=Lax is required: the callback arrives via a top-level GET
    # redirect from github.com, which SameSite=Strict would block from
    # receiving the cookie on subsequent requests.
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        path="/",
    )

    # 10. Return only the public user data — never the token
    return user_data


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@router.get("/auth/me", response_model=AuthenticatedUser)
def get_me(request: Request) -> AuthenticatedUser:
    """
    Return the authenticated user's public profile.

    Reads the ``session_id`` cookie, validates that the session exists
    and has not expired, and returns the stored :class:`AuthenticatedUser`.

    Returns:
        - **200** with :class:`AuthenticatedUser` when the session is valid.
        - **401** when the cookie is absent, the session is not found, or
          the session has expired (expired entries are removed eagerly).
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if session.expires_at < datetime.utcnow():
        sessions.pop(session_id, None)
        raise HTTPException(status_code=401, detail="Not authenticated")

    return session.user


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


@router.post("/auth/logout")
def logout(request: Request, response: Response) -> dict:
    """
    Invalidate the current session and clear the session cookie.

    This endpoint is idempotent — it returns 200 regardless of whether a
    valid session exists.  The session cookie is always cleared from the
    response, and any matching session entry is removed from the store.

    Returns:
        - **200** with ``{"message": "Logged out"}`` in all cases.
    """
    session_id = request.cookies.get("session_id")
    if session_id:
        sessions.pop(session_id, None)

    response.delete_cookie(key="session_id", path="/", httponly=True, samesite="lax")
    return {"message": "Logged out"}
