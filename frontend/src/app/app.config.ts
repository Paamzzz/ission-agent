import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideMarkdown } from 'ngx-markdown';

import { routes } from './app.routes';
import { authInterceptor } from './auth/auth.interceptor';

export const appConfig: ApplicationConfig = {
     providers: [
          provideBrowserGlobalErrorListeners(),
          provideRouter(routes),
          provideHttpClient(withInterceptors([authInterceptor])),
          provideMarkdown()
     ]
};
