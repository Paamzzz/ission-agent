export interface AuthenticatedUser {
     login: string;
     avatar_url: string;
     name: string | null;
}

export interface AuthLoginResponse {
     authorization_url: string;
}

/** PKCE parameters held in memory only — never exported or serialized */
interface PkceParams {
     codeVerifier: string;
     codeChallenge: string;
     state: string;
}
