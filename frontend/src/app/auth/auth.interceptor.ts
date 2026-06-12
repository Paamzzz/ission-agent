import { HttpInterceptorFn } from '@angular/common/http';

const BACKEND_ORIGIN = 'http://localhost:8000';

/**
 * Adds `withCredentials: true` to every request targeting the Ission backend
 * so that the session cookie is included automatically.
 *
 * Does NOT attach any Authorization header — the backend reads the token
 * from the server-side session store via the session cookie.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
     if (req.url.startsWith(BACKEND_ORIGIN)) {
          const authReq = req.clone({ withCredentials: true });
          return next(authReq);
     }
     return next(req);
};
