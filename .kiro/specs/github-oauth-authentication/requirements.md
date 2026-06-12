# Requirements Document

## Introduction

Esta feature adiciona autenticação de usuários ao Ission Agent via GitHub OAuth 2.0 Authorization Code Flow com PKCE. Atualmente, a aplicação usa um único token de serviço global armazenado em variável de ambiente no backend. O objetivo é permitir que cada usuário conecte sua própria conta GitHub, obtendo acesso a repositórios privados e publicando comentários com sua própria identidade. A autenticação é opcional: quando nenhum usuário estiver autenticado, a aplicação continua funcionando com o token global existente como fallback.

O fluxo envolve três partes: o frontend Angular (inicia o fluxo, recebe apenas os dados públicos do usuário autenticado), o backend FastAPI (troca o authorization code pelo access token, armazena o token em sessão server-side segura e intermedia chamadas à GitHub API) e o GitHub OAuth App (provedor de identidade).

## Glossary

- **Auth_Service**: Serviço Angular responsável por gerenciar o estado de autenticação e iniciar o fluxo OAuth. O frontend nunca armazena o access token — o Auth_Service recebe apenas o objeto Authenticated_User e mantém o estado de autenticação baseado na sessão server-side.
- **OAuth_Controller**: Módulo FastAPI responsável pelos endpoints de autenticação (`/auth/github/login`, `/auth/github/callback`, `/auth/logout`).
- **Session_Store**: Mecanismo de armazenamento server-side do access token no backend. O token é mantido exclusivamente no servidor em sessão segura (HTTP-only, SameSite=Strict cookie) e nunca é transmitido ao frontend.
- **GitHub_API_Client**: Módulo backend responsável por fazer chamadas à GitHub API usando o token do usuário autenticado ou o token global como fallback.
- **PKCE**: Proof Key for Code Exchange — extensão do OAuth 2.0 que usa `code_verifier` e `code_challenge` para proteger o fluxo contra interceptação do authorization code.
- **Code_Verifier**: String aleatória criptograficamente segura gerada pelo frontend, mantida em memória durante o fluxo OAuth.
- **Code_Challenge**: Hash SHA-256 do `code_verifier`, codificado em Base64 URL-safe, enviado ao GitHub no início do fluxo.
- **Authorization_Code**: Código temporário retornado pelo GitHub após o usuário autorizar o acesso, válido por poucos minutos.
- **Access_Token**: Token de acesso OAuth do GitHub válido para fazer chamadas à API em nome do usuário. Armazenado exclusivamente na Session_Store no backend; nunca transmitido ao frontend.
- **GitHub_OAuth_App**: Aplicação registrada no GitHub que define `client_id`, `client_secret` e o `redirect_uri`.
- **Authenticated_User**: Objeto que representa o usuário autenticado, contendo `login`, `avatar_url` e `name` obtidos via `/user` da GitHub API.
- **Fallback_Token**: Token global (`GITHUB_TOKEN`) configurado em variável de ambiente no backend, usado quando não há usuário autenticado.

---

## Requirements

### Requirement 1: Iniciar Fluxo de Autenticação OAuth com PKCE

**User Story:** As a developer, I want to click a "Connect GitHub" button to start the OAuth login flow, so that I can connect my GitHub account without manually handling tokens.

#### Acceptance Criteria

1. WHEN the user clicks the "Connect GitHub" button, THE Auth_Service SHALL generate a cryptographically secure `code_verifier` of at least 43 characters using the Web Crypto API.
2. WHEN the `code_verifier` is generated, THE Auth_Service SHALL compute the `code_challenge` as the Base64 URL-safe SHA-256 hash of the `code_verifier`.
3. WHEN the `code_challenge` is computed, THE Auth_Service SHALL generate a random `state` parameter of at least 16 bytes using the Web Crypto API.
4. WHEN the `state` and `code_verifier` are generated, THE Auth_Service SHALL store both values in memory only (never in localStorage, sessionStorage, or cookies).
5. WHEN the PKCE parameters are ready, THE Auth_Service SHALL redirect the browser to the GitHub authorization URL containing `client_id`, `redirect_uri`, `scope=repo user`, `state`, `code_challenge`, and `code_challenge_method=S256`.
6. IF the Web Crypto API is unavailable, THEN THE Auth_Service SHALL display an error message stating that the browser does not support the required security features.

---

### Requirement 2: Processar o Callback OAuth no Frontend

**User Story:** As a developer, I want the application to handle the GitHub OAuth callback automatically, so that I am logged in after authorizing access without manual steps.

#### Acceptance Criteria

1. WHEN the browser is redirected to the callback route (`/auth/callback`), THE Auth_Service SHALL extract the `code` and `state` parameters from the URL query string.
2. WHEN the `state` parameter is extracted, THE Auth_Service SHALL compare it with the stored in-memory `state` value.
3. IF the extracted `state` does not match the stored `state`, THEN THE Auth_Service SHALL discard the `code`, clear all PKCE parameters from memory, and display an authentication error to the user.
4. WHEN the `state` is validated, THE Auth_Service SHALL send the `code` and `code_verifier` to the backend endpoint `POST /auth/github/callback`.
5. WHEN the backend returns the `Authenticated_User` object, THE Auth_Service SHALL update the authentication state with the received user data (login, avatar_url, name) and store it as an observable.
6. WHEN the authentication state is updated, THE Auth_Service SHALL clear the `code_verifier`, `state`, and authorization code from memory.
7. WHEN authentication is complete, THE Auth_Service SHALL navigate the user to the main application page.
8. IF the backend returns an error during token exchange, THEN THE Auth_Service SHALL display a descriptive authentication error message and allow the user to retry.

---

### Requirement 3: Trocar Authorization Code por Access Token no Backend

**User Story:** As a developer, I want the backend to securely exchange the authorization code for an access token, so that the client_secret is never exposed to the browser.

#### Acceptance Criteria

1. WHEN the backend receives a `POST /auth/github/callback` request with `code` and `code_verifier`, THE OAuth_Controller SHALL send a request to `https://github.com/login/oauth/access_token` with `client_id`, `client_secret`, `code`, `redirect_uri`, and `code_verifier`.
2. WHEN GitHub returns the access token, THE OAuth_Controller SHALL immediately fetch the user profile from `https://api.github.com/user` using the access token.
3. WHEN the user profile is fetched, THE OAuth_Controller SHALL return only the `Authenticated_User` object (`login`, `avatar_url`, `name`) and a session cookie to the frontend — the access token SHALL NOT be included in the response body.
4. THE OAuth_Controller SHALL store the access token server-side in a secure, HTTP-only, SameSite=Strict session with a configurable TTL.
5. IF GitHub returns an error during token exchange, THEN THE OAuth_Controller SHALL return HTTP 400 with a descriptive error message and SHALL NOT log the partial token or authorization code.
6. THE OAuth_Controller SHALL validate that `client_secret` is loaded from environment variables and SHALL NOT accept it from request parameters.

---

### Requirement 4: Gerenciar Sessão e Estado de Autenticação no Frontend

**User Story:** As a developer, I want to see a visual indicator of my GitHub connection status with my avatar and username, so that I always know whether I am authenticated.

#### Acceptance Criteria

1. WHEN the user is authenticated, THE Auth_Service SHALL expose the `Authenticated_User` object (login, avatar_url, name) as an observable to all components.
2. WHEN the application loads, THE Auth_Service SHALL check for an existing valid session by calling `GET /auth/me` on the backend.
3. WHEN `GET /auth/me` returns a valid user, THE Auth_Service SHALL restore the authenticated state without requiring re-login.
4. WHEN `GET /auth/me` returns 401 or an error, THE Auth_Service SHALL set the authentication state to unauthenticated silently.
5. WHILE the user is authenticated, THE UI SHALL display the user's avatar, GitHub username, and a "Disconnect" button in a non-intrusive header area.
6. WHILE the user is not authenticated, THE UI SHALL display a "Connect GitHub" button.
7. WHEN the application transitions between authenticated and unauthenticated states, THE UI SHALL update without requiring a full page reload.

---

### Requirement 5: Desconectar Conta GitHub

**User Story:** As a developer, I want to disconnect my GitHub account, so that I can stop the application from acting on my behalf.

#### Acceptance Criteria

1. WHEN the user clicks the "Disconnect" button, THE Auth_Service SHALL call `POST /auth/logout` on the backend.
2. WHEN the backend confirms logout, THE Auth_Service SHALL set the authentication state to unauthenticated and clear any locally held user data.
3. WHEN logout is complete, THE Auth_Service SHALL navigate the user to the main page if they are not already there.
4. WHEN the backend session is cleared, THE OAuth_Controller SHALL invalidate the server-side session and clear the session cookie.
5. IF the logout request fails, THEN THE Auth_Service SHALL still clear the local authentication state and any locally held user data, ensuring the user is treated as unauthenticated.

---

### Requirement 6: Usar Token do Usuário Autenticado nas Chamadas à GitHub API

**User Story:** As a developer, I want my API calls to use my own GitHub token, so that I can access my private repositories and publish comments as myself.

#### Acceptance Criteria

1. WHEN a request to analyze an issue is made by an authenticated user, THE GitHub_API_Client SHALL use the user's access token from the server-side session to call the GitHub API.
2. WHEN a request to publish a comment is made by an authenticated user, THE GitHub_API_Client SHALL use the user's access token to authenticate the comment publication, so the comment appears as authored by the user.
3. WHILE no user is authenticated, THE GitHub_API_Client SHALL fall back to the `Fallback_Token` from the environment variable for all GitHub API calls.
4. IF the backend returns HTTP 401 due to an expired or invalid access token, THEN THE Auth_Service SHALL clear the authentication state and prompt the user to reconnect.
5. THE GitHub_API_Client SHALL NEVER log the access token value in any log output.
6. THE GitHub_API_Client SHALL NEVER include the access token in any API response body.

---

### Requirement 7: Proteger o Callback Route e Parâmetros PKCE

**User Story:** As a security engineer, I want the OAuth callback to be protected against CSRF and code interception attacks, so that stolen authorization codes cannot be exchanged for tokens.

#### Acceptance Criteria

1. THE Auth_Service SHALL generate a unique `state` parameter for each OAuth flow initiation and invalidate it after a single use.
2. WHEN a `state` mismatch is detected, THE Auth_Service SHALL log a security warning (without logging token values) and abort the flow.
3. THE OAuth_Controller SHALL validate that the `redirect_uri` in the token exchange request matches exactly the `redirect_uri` registered in the GitHub OAuth App configuration.
4. THE OAuth_Controller SHALL use HTTPS for all communications with GitHub APIs in production.
5. IF the authorization code has already been used or is expired, THEN THE OAuth_Controller SHALL return HTTP 400 and SHALL NOT attempt to reuse the code.
6. THE Auth_Service SHALL configure all HTTP requests to the Ission backend with `withCredentials: true` so that the session cookie is sent automatically, and SHALL NOT attach any token to request headers.

---

### Requirement 8: Tratar Erros de Autenticação com Feedback Visual

**User Story:** As a developer, I want clear visual feedback when authentication fails, so that I understand what went wrong and how to recover.

#### Acceptance Criteria

1. WHEN any authentication step fails, THE Auth_Service SHALL emit an error state observable with a human-readable message in the user's language.
2. WHEN an authentication error occurs, THE UI SHALL display the error message in a non-blocking notification that auto-dismisses after 5 seconds.
3. WHEN a network error occurs during the OAuth callback, THE Auth_Service SHALL display a message indicating a connection failure and offer a "Try Again" action.
4. WHEN the user is redirected to the callback route without `code` or `state` parameters, THE Auth_Service SHALL treat it as an invalid callback and navigate to the main page with an error notification.
5. WHILE authentication is in progress (between redirect and callback resolution), THE UI SHALL display a loading indicator and disable the "Connect GitHub" button.
6. IF the GitHub OAuth App configuration is missing (`client_id` not set), THEN THE OAuth_Controller SHALL return HTTP 503 with the message "GitHub OAuth not configured" at the `/auth/github/login` endpoint.
