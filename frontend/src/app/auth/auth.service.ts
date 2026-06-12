import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, from, throwError, EMPTY } from 'rxjs';
import { map, catchError, finalize, tap } from 'rxjs/operators';
import { AuthenticatedUser, AuthLoginResponse } from './auth.models';

const API_BASE = 'http://localhost:8000';

@Injectable({ providedIn: 'root' })
export class AuthService {
     private http = inject(HttpClient);
     private router = inject(Router);

     // Private PKCE fields — never written to any Web Storage or cookie
     #codeVerifier: string | null = null;
     #state: string | null = null;

     // Public observables
     currentUser$ = new BehaviorSubject<AuthenticatedUser | null>(null);
     isLoading$ = new BehaviorSubject<boolean>(false);
     authError$ = new BehaviorSubject<string | null>(null);

     isAuthenticated$: Observable<boolean> = this.currentUser$.pipe(
          map((user) => user !== null)
     );

     // ---------------------------------------------------------------------------
     // PKCE utility methods
     // ---------------------------------------------------------------------------

     /** Generates a code verifier: 96 random bytes encoded as base64url (no padding). */
     async generateCodeVerifier(): Promise<string> {
          const array = new Uint8Array(96);
          crypto.getRandomValues(array);
          return this.toBase64Url(array);
     }

     /** Computes SHA-256 of the verifier and base64url-encodes the result. */
     async computeCodeChallenge(verifier: string): Promise<string> {
          const encoder = new TextEncoder();
          const data = encoder.encode(verifier);
          const digest = await crypto.subtle.digest('SHA-256', data);
          return this.toBase64Url(new Uint8Array(digest));
     }

     /** Generates a state value: 16 random bytes encoded as base64url (no padding). */
     async generateState(): Promise<string> {
          const array = new Uint8Array(16);
          crypto.getRandomValues(array);
          return this.toBase64Url(array);
     }

     /** Encodes a Uint8Array to base64url without padding. */
     private toBase64Url(bytes: Uint8Array): string {
          let binary = '';
          for (let i = 0; i < bytes.length; i++) {
               binary += String.fromCharCode(bytes[i]);
          }
          return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
     }

     // ---------------------------------------------------------------------------
     // login()
     // ---------------------------------------------------------------------------

     /**
      * Initiates the OAuth flow:
      *   1. Generates PKCE params via Web Crypto API.
      *   2. Persists verifier + state to sessionStorage so they survive the
      *      full-page redirect to GitHub and back. Both are cleared on first use.
      *   3. Fetches the authorization URL from the backend.
      *   4. Appends state + code_challenge to the URL and redirects the browser.
      */
     async login(): Promise<void> {
          try {
               this.#codeVerifier = await this.generateCodeVerifier();
               const challenge = await this.computeCodeChallenge(this.#codeVerifier);
               this.#state = await this.generateState();

               // Persist across the full-page redirect. Cleared immediately after
               // single use in handleCallback().
               sessionStorage.setItem('oauth_code_verifier', this.#codeVerifier);
               sessionStorage.setItem('oauth_state', this.#state);

               this.isLoading$.next(true);

               const response = await this.http
                    .get<AuthLoginResponse>(`${API_BASE}/auth/github/login`, {
                         withCredentials: true,
                    })
                    .toPromise();

               if (!response) {
                    throw new Error('No response from login endpoint');
               }

               const fullUrl =
                    `${response.authorization_url}` +
                    `&state=${encodeURIComponent(this.#state)}` +
                    `&code_challenge=${encodeURIComponent(challenge)}` +
                    `&code_challenge_method=S256`;

               window.location.href = fullUrl;
          } catch (err: unknown) {
               const message =
                    err instanceof Error ? err.message : 'Failed to initiate login';
               this.authError$.next(message);
               this.isLoading$.next(false);
          }
     }

     // ---------------------------------------------------------------------------
     // handleCallback()
     // ---------------------------------------------------------------------------

     /**
      * Handles the OAuth callback:
      *   1. Restores verifier + state from sessionStorage (they were stored before
      *      the full-page redirect to GitHub). Clears them immediately after reading.
      *   2. Validates the returned state against the stored state.
      *   3. POSTs the code + code_verifier to the backend.
      *   4. Updates currentUser$ on success; clears all PKCE fields either way.
      */
     handleCallback(code: string, state: string): Observable<void> {
          // Restore PKCE params that were persisted before the redirect.
          // Read-once: immediately remove from sessionStorage regardless of outcome.
          const storedVerifier = sessionStorage.getItem('oauth_code_verifier');
          const storedState = sessionStorage.getItem('oauth_state');
          sessionStorage.removeItem('oauth_code_verifier');
          sessionStorage.removeItem('oauth_state');

          // Restore into private fields so the rest of the method works unchanged.
          this.#codeVerifier = storedVerifier;
          this.#state = storedState;

          if (state !== this.#state) {
               this.authError$.next('State mismatch — possible CSRF attack. Please try again.');
               this.#codeVerifier = null;
               this.#state = null;
               return throwError(() => new Error('OAuth state mismatch'));
          }

          this.isLoading$.next(true);

          const body = {
               code,
               code_verifier: this.#codeVerifier,
          };

          return this.http
               .post<AuthenticatedUser>(`${API_BASE}/auth/github/callback`, body, {
                    withCredentials: true,
               })
               .pipe(
                    tap((user) => {
                         this.currentUser$.next(user);
                         this.#codeVerifier = null;
                         this.#state = null;
                    }),
                    map(() => void 0),
                    catchError((err) => {
                         const message =
                              err?.error?.detail ?? err?.message ?? 'Callback failed';
                         this.authError$.next(message);
                         this.#codeVerifier = null;
                         this.#state = null;
                         this.isLoading$.next(false);
                         return throwError(() => err);
                    }),
                    finalize(() => this.isLoading$.next(false))
               );
     }

     // ---------------------------------------------------------------------------
     // logout()
     // ---------------------------------------------------------------------------

     /**
      * Logs the user out:
      *   - POSTs to /auth/logout.
      *   - Always clears currentUser$ and sets isLoading$ to false via finalize,
      *     regardless of whether the request succeeds or fails.
      */
     logout(): Observable<void> {
          this.isLoading$.next(true);

          return this.http
               .post<void>(`${API_BASE}/auth/logout`, {}, { withCredentials: true })
               .pipe(
                    map(() => void 0),
                    catchError(() => EMPTY),
                    finalize(() => {
                         this.currentUser$.next(null);
                         this.isLoading$.next(false);
                    })
               );
     }

     // ---------------------------------------------------------------------------
     // checkSession()
     // ---------------------------------------------------------------------------

     /**
      * Checks whether an existing session is still valid by calling GET /auth/me.
      *   - On success: populates currentUser$.
      *   - On 401 / any error: sets currentUser$ to null silently.
      *   - Sets isLoading$ to false in both cases.
      */
     checkSession(): Observable<void> {
          this.isLoading$.next(true);

          return this.http
               .get<AuthenticatedUser>(`${API_BASE}/auth/me`, { withCredentials: true })
               .pipe(
                    tap((user) => this.currentUser$.next(user)),
                    map(() => void 0),
                    catchError(() => {
                         this.currentUser$.next(null);
                         return EMPTY;
                    }),
                    finalize(() => this.isLoading$.next(false))
               );
     }
}
