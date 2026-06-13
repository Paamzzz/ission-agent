import { Component, OnInit, inject } from '@angular/core';
import { AsyncPipe, NgIf } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from './auth.service';

@Component({
     selector: 'app-auth-callback',
     standalone: true,
     imports: [AsyncPipe, NgIf],
     template: `
    <div class="auth-callback">
      <div *ngIf="isLoading$ | async" class="spinner-container">
        <div class="spinner"></div>
        <p>Completing authentication...</p>
      </div>
      <div *ngIf="authError$ | async as error" class="error-message">
        {{ error }}
      </div>
    </div>
  `,
     styles: [`
    .auth-callback {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      flex-direction: column;
    }

    .spinner-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 1rem;
    }

    .spinner {
      width: 48px;
      height: 48px;
      border: 4px solid rgba(0, 0, 0, 0.1);
      border-top-color: #333;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .error-message {
      color: #c0392b;
      background: #fdecea;
      border: 1px solid #e74c3c;
      border-radius: 4px;
      padding: 1rem 1.5rem;
      max-width: 480px;
      text-align: center;
    }
  `],
})
export class AuthCallbackComponent implements OnInit {
     private route = inject(ActivatedRoute);
     private router = inject(Router);
     private authService = inject(AuthService);

     isLoading$ = this.authService.isLoading$;
     authError$ = this.authService.authError$;

     ngOnInit(): void {
          this.route.queryParams.subscribe((params) => {
               const code = params['code'];
               const state = params['state'];

               if (!code || !state) {
                    this.authService.authError$.next('Authentication failed: missing code or state parameter.');
                    this.router.navigate(['/landing']);
                    return;
               }

               this.authService.handleCallback(code, state).subscribe({
                    next: () => {
                         // currentUser$ is already populated by handleCallback's tap().
                         // Navigate to analyzer — AuthStatusComponent will reflect the new state.
                         this.router.navigate(['/analyzer']);
                    },
                    error: () => {
                         // authError$ is already set by AuthService; stay on page to show the error
                    },
               });
          });
     }
}
