# Implementation Plan: GitHub OAuth Authentication

## Overview

Implement GitHub OAuth 2.0 Authorization Code Flow with PKCE across the FastAPI backend and Angular frontend. The backend handles token exchange, server-side session storage, and GitHub API proxying; the frontend manages PKCE generation, callback handling, and authentication state display. The access token never leaves the backend.

## Tasks

- [x] 1. Install dependencies and set up environment configuration
  - Add `itsdangerous`, `httpx`, and `pytest-asyncio` to `backend/requirements.txt`
  - Add `fast-check` and `@types/node` (if missing) to `frontend/package.json` devDependencies
  - Add the new environment variables to `backend/.env.example`: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI`, `SESSION_SECRET_KEY`, `SESSION_TTL_HOURS`
  - _Requirements: 3.6, 8.6_

- [x] 2. Create backend data models and session store
  - [x] 2.1 Create `backend/auth_models.py` with Pydantic models: `AuthenticatedUser`, `SessionData`, `CallbackRequest`, `AuthLoginResponse`, `ErrorResponse`
    - `AuthenticatedUser` exposes only `login`, `avatar_url`, `name` — never the token
    - `SessionData` holds `access_token`, `user: AuthenticatedUser`, `expires_at: datetime`
    - _Requirements: 3.3, 3.4_
  - [x] 2.2 Add in-memory session store dict and `get_current_token` FastAPI dependency in `backend/auth_router.py` (file can be an empty router at this step)
    - `sessions: dict[str, SessionData] = {}`
    - `get_current_token(request: Request) -> str | None` reads session cookie, returns user token or `None`
    - _Requirements: 3.4, 6.1, 6.2, 6.3_

- [x] 3. Implement backend OAuth endpoints (`auth_router.py`)
  - [x] 3.1 Implement `GET /auth/github/login`
    - Load `GITHUB_CLIENT_ID` from env; return 503 with `{"detail": "GitHub OAuth not configured"}` if missing
    - Build and return the GitHub authorization URL with `client_id`, `redirect_uri`, `scope=repo user`, `code_challenge_method=S256`, and a placeholder for `state` and `code_challenge` (actual PKCE params come from the frontend)
    - _Requirements: 1.5, 8.6_
  - [x] 3.2 Implement `POST /auth/github/callback`
    - Accept `CallbackRequest` (`code`, `code_verifier`)
    - Validate `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` are set; validate `redirect_uri` matches `GITHUB_REDIRECT_URI` exactly — return 400 on mismatch
    - Exchange code for token via `https://github.com/login/oauth/access_token`; return 400 on GitHub error without logging code or partial token
    - Fetch `/user` from GitHub API with the received token
    - Create a `session_id = secrets.token_urlsafe(32)`, store `SessionData` in `sessions` dict with configurable TTL
    - Set `Set-Cookie: session_id=<id>; HttpOnly; SameSite=Strict; Path=/` response header
    - Return only `AuthenticatedUser` in the response body
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 7.3, 7.4, 7.5_
  - [x] 3.3 Implement `GET /auth/me`
    - Read session cookie; look up session in store; check expiry
    - Return `AuthenticatedUser` (200) if valid; return 401 if missing or expired
    - _Requirements: 4.2, 4.3, 4.4_
  - [x] 3.4 Implement `POST /auth/logout`
    - Remove session entry from `sessions` dict
    - Clear session cookie in response (`Set-Cookie: session_id=; Max-Age=0; ...`)
    - _Requirements: 5.4_

- [x] 4. Integrate `auth_router` and update existing endpoints in `main.py` and `orchestrator.py`
  - [x] 4.1 Update `main.py` to include `auth_router` and wire `get_current_token` dependency into `/api/analyze` and `/api/publish-comment`
    - `app.include_router(auth_router)`
    - Both existing endpoints receive `token: str | None = Depends(get_current_token)` and forward it
    - _Requirements: 6.1, 6.2, 6.3_
  - [x] 4.2 Update `orchestrator.py` — modify `_fetch_github_issue` to accept optional `token: str | None = None`
    - When token is provided, add `Authorization: Bearer <token>` header to GitHub API request
    - When token is `None`, omit the Authorization header (public access / fallback)
    - _Requirements: 6.1, 6.3, 6.5_
  - [x] 4.3 Update `publish_comment` in `main.py` to use the session token when present, falling back to `GITHUB_TOKEN`
    - _Requirements: 6.2, 6.3_

- [x] 5. Checkpoint — backend is complete
  - Run `pytest` to verify all backend tests pass; confirm endpoints respond correctly with a quick smoke test using `curl` or an HTTP client.

- [x] 6. Create Angular TypeScript interfaces and `AuthService`
  - [x] 6.1 Create `frontend/src/app/auth/auth.models.ts` with `AuthenticatedUser`, `AuthLoginResponse`, and private `PkceParams` interface
    - _Requirements: 4.1_
  - [x] 6.2 Create `frontend/src/app/auth/auth.service.ts` implementing the full `AuthService`
    - `currentUser$: BehaviorSubject<AuthenticatedUser | null>`
    - `isAuthenticated$: Observable<boolean>`
    - `isLoading$: BehaviorSubject<boolean>`
    - `authError$: BehaviorSubject<string | null>`
    - `login()` — generate PKCE via Web Crypto API (`code_verifier` ≥ 43 chars, `state` ≥ 16 bytes), store in private class fields only, call `GET /auth/github/login`, redirect to returned URL
    - `handleCallback(code, state)` — validate state, `POST /auth/github/callback`, update `currentUser$`, clear PKCE fields
    - `logout()` — call `POST /auth/logout`, set `currentUser$` to `null` regardless of response
    - `checkSession()` — call `GET /auth/me`, restore state or set unauthenticated silently
    - PKCE params stored as private class fields — never written to `localStorage`, `sessionStorage`, or cookies
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 4.1, 5.1, 5.2, 5.3, 5.5, 7.1, 7.6, 8.1, 8.3, 8.4_
  - [ ]* 6.3 Write property test for `AuthService` PKCE generation (P1, P2, P3)
    - **Property 1: code_verifier validity** — assert length ≥ 43 and matches `/^[A-Za-z0-9\-._~]+$/`
    - **Property 2: code_challenge derivation integrity** — independently compute `base64url(SHA256(verifier))` and compare
    - **Property 3: OAuth state uniqueness** — generate 100 states, insert into a `Set`, assert size equals 100
    - Use `fast-check` with ≥ 100 iterations
    - **Validates: Requirements 1.1, 1.2, 7.1**
  - [ ]* 6.4 Write property test for `handleCallback` state mismatch (P4)
    - **Property 4: State mismatch aborts flow and clears PKCE parameters**
    - Use `fast-check` to generate pairs of non-equal strings, call `handleCallback` with mismatched state, assert error emitted and PKCE fields cleared
    - **Validates: Requirements 2.3, 7.1**
  - [ ]* 6.5 Write unit tests for `AuthService` example-based scenarios
    - `login()` does NOT write to `localStorage`, `sessionStorage`, or `document.cookie`
    - `handleCallback()` with matching state updates `currentUser$`
    - `checkSession()` calls `GET /auth/me` on init; handles 401 silently (sets unauthenticated)
    - `logout()` always sets `currentUser$` to `null` even when request fails
    - _Requirements: 1.4, 2.5, 2.7, 4.3, 4.4, 5.5_

- [x] 7. Create `AuthInterceptor` and wire into Angular app configuration
  - [x] 7.1 Create `frontend/src/app/auth/auth.interceptor.ts` as an `HttpInterceptorFn`
    - Adds `withCredentials: true` to every request targeting `http://localhost:8000`
    - Does NOT add any `Authorization` header
    - _Requirements: 7.6_
  - [x] 7.2 Update `frontend/src/app/app.config.ts` to register the interceptor: `provideHttpClient(withInterceptors([authInterceptor]))`
    - _Requirements: 7.6_
  - [ ]* 7.3 Write unit tests for `AuthInterceptor`
    - Verifies `withCredentials: true` is added to requests to `http://localhost:8000`
    - Verifies requests to other origins are not modified
    - _Requirements: 7.6_

- [x] 8. Create `AuthCallbackComponent` and register the `/auth/callback` route
  - [x] 8.1 Create `frontend/src/app/auth/auth-callback.component.ts` (standalone)
    - Reads `code` and `state` from `ActivatedRoute.queryParams`
    - If either is missing, navigate to `/` with an error notification
    - Delegates to `AuthService.handleCallback()`; shows a full-page loading spinner while in progress
    - Navigates to `/` on success; shows error message on failure
    - _Requirements: 2.1, 2.7, 2.8, 8.4, 8.5_
  - [x] 8.2 Update `frontend/src/app/app.routes.ts` to add `{ path: 'auth/callback', component: AuthCallbackComponent }`
    - _Requirements: 2.1_
  - [ ]* 8.3 Write unit tests for `AuthCallbackComponent`
    - Verifies navigation to `/` on success
    - Verifies error display and navigation to `/` when code/state are missing
    - Verifies loading spinner is shown while `handleCallback` is in progress
    - _Requirements: 2.7, 2.8, 8.4, 8.5_

- [x] 9. Create `AuthStatusComponent` and embed in app header
  - [x] 9.1 Create `frontend/src/app/auth/auth-status.component.ts` (standalone)
    - Subscribes to `AuthService.currentUser$`, `isLoading$`, and `authError$`
    - **Unauthenticated state**: render "Connect GitHub" button — disabled while loading
    - **Authenticated state**: render user avatar (24 px circle), `@username`, and "Disconnect" button
    - **Loading state**: show spinner, disable "Connect GitHub" button
    - **Error state**: display inline error message that auto-dismisses after 5 seconds
    - All state transitions happen without a full page reload
    - _Requirements: 4.5, 4.6, 4.7, 8.2, 8.5_
  - [x] 9.2 Embed `AuthStatusComponent` in the main app header (`app.component.ts` / `app.component.html`)
    - _Requirements: 4.5, 4.6_
  - [ ]* 9.3 Write unit tests for `AuthStatusComponent`
    - Verifies "Connect GitHub" button rendered when unauthenticated
    - Verifies avatar, `@username`, and "Disconnect" button rendered when authenticated
    - Verifies spinner shown and button disabled when loading
    - Verifies error message auto-dismisses after 5 seconds
    - _Requirements: 4.5, 4.6, 4.7, 8.2, 8.5_

- [ ] 10. Write backend property-based and unit tests
  - [ ]* 10.1 Write property tests for token isolation (P5) using `hypothesis`
    - **Property 5: Token isolation across all surfaces**
    - Use `hypothesis` to generate arbitrary token strings; mock GitHub to return them; assert the token does NOT appear in any response body or log output for `/auth/github/callback`, `/api/analyze`, `/api/publish-comment`, `/auth/me`
    - **Validates: Requirements 3.3, 6.5, 6.6**
  - [ ]* 10.2 Write property tests for token selection correctness (P6) using `hypothesis`
    - **Property 6: Token selection correctness**
    - Use `hypothesis` to generate sessions with and without valid entries; verify the correct token (user vs. fallback) is passed to the GitHub API mock in each case
    - **Validates: Requirements 6.1, 6.2, 6.3**
  - [ ]* 10.3 Write property tests for `redirect_uri` rejection (P8) using `hypothesis`
    - **Property 8: redirect_uri validation rejects non-matching values**
    - Use `hypothesis` to generate strings differing from configured `GITHUB_REDIRECT_URI`; assert HTTP 400 is returned without contacting GitHub
    - **Validates: Requirements 7.3**
  - [ ]* 10.4 Write example-based unit tests for backend endpoints using `pytest`
    - `GET /auth/github/login` returns correct URL; returns 503 when `GITHUB_CLIENT_ID` is absent
    - `POST /auth/github/callback` full mock flow; verifies `Set-Cookie` has `HttpOnly` and `SameSite=Strict`
    - `GET /auth/me` valid session returns user; expired/missing session returns 401
    - `POST /auth/logout` removes session from store and clears cookie
    - `get_current_token` dependency returns user token when session is valid; returns `GITHUB_TOKEN` when not
    - _Requirements: 3.1–3.6, 4.2–4.4, 5.4_
  - [ ]* 10.5 Write property test for logout always clearing state (P7) using `hypothesis`
    - **Property 7: Logout always clears local authentication state**
    - Use `hypothesis` to generate arbitrary HTTP error response codes from `POST /auth/logout`; mock `HttpClient` to return them; assert `currentUser$` becomes `null` in all cases
    - **Validates: Requirements 5.2, 5.5**

- [x] 11. Final checkpoint — Ensure all tests pass
  - Run `pytest` (backend) and `npx vitest --run` (frontend); ensure all tests pass and the full OAuth flow is exercised end-to-end via automated tests. Ask the user if any questions arise.

## Notes

- Sub-tasks marked with `*` are optional and can be skipped for a faster MVP iteration.
- Each task references specific requirements for traceability.
- The access token is strictly server-side — any path that would expose it (response body, URL, log) is a correctness violation.
- The in-memory `sessions` dict is intentional for this sprint; Redis migration is a production follow-up item noted in the design.
- Property tests use `fast-check` (frontend / TypeScript) and `hypothesis` (backend / Python), each running ≥ 100 iterations.
- Checkpoints at tasks 5 and 11 validate incremental progress before moving to the next layer.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1"] },
    { "id": 1, "tasks": ["2.2"] },
    { "id": 2, "tasks": ["3.1", "3.2", "3.3", "3.4", "6.1"] },
    { "id": 3, "tasks": ["4.1", "4.2", "4.3", "6.2"] },
    { "id": 4, "tasks": ["6.3", "6.4", "6.5", "7.1", "10.1", "10.2", "10.3", "10.4"] },
    { "id": 5, "tasks": ["7.2", "8.1", "10.5"] },
    { "id": 6, "tasks": ["7.3", "8.2"] },
    { "id": 7, "tasks": ["8.3", "9.1"] },
    { "id": 8, "tasks": ["9.2"] },
    { "id": 9, "tasks": ["9.3"] }
  ]
}
```
