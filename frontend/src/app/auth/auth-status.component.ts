import { Component, inject, OnInit } from '@angular/core';
import { AsyncPipe, NgIf } from '@angular/common';
import { AuthService } from './auth.service';

@Component({
     selector: 'app-auth-status',
     standalone: true,
     imports: [AsyncPipe, NgIf],
     template: `
    <div class="auth-status">
      <!-- Loading state -->
      <span *ngIf="isLoading$ | async" class="auth-spinner"></span>

      <!-- Authenticated -->
      <ng-container *ngIf="currentUser$ | async as user; else unauthenticated">
        <img [src]="user.avatar_url" [alt]="user.login" class="user-avatar" />
        <span class="username">@{{ user.login }}</span>
        <button (click)="onLogout()" class="btn-disconnect">Disconnect</button>
      </ng-container>

      <!-- Unauthenticated -->
      <ng-template #unauthenticated>
        <button
          (click)="onLogin()"
          [disabled]="isLoading$ | async"
          class="btn-connect"
        >
          Connect GitHub
        </button>
      </ng-template>

      <!-- Error -->
      <div *ngIf="authError$ | async as error" class="auth-error">{{ error }}</div>
    </div>
  `,
     styles: [`
    .auth-status {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .user-avatar {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      object-fit: cover;
      border: 1.5px solid rgba(147, 51, 234, 0.4);
    }

    .username {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      color: #9B85BE;
    }

    .btn-connect {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 8px 16px;
      background: linear-gradient(135deg, #7B2FBE, #9333EA);
      border: none;
      border-radius: 8px;
      color: #fff;
      font-family: 'Syne', sans-serif;
      font-size: 0.8rem;
      font-weight: 700;
      letter-spacing: 0.02em;
      cursor: pointer;
      white-space: nowrap;
      box-shadow: 0 3px 14px rgba(123, 47, 190, 0.4);
      transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s, opacity 0.2s;
    }

    .btn-connect:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 6px 22px rgba(123, 47, 190, 0.55);
    }

    .btn-connect:active:not(:disabled) {
      transform: translateY(0);
    }

    .btn-connect:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      box-shadow: none;
    }

    .btn-disconnect {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 7px 14px;
      background: transparent;
      border: 1px solid rgba(239, 68, 68, 0.35);
      border-radius: 8px;
      color: rgba(239, 68, 68, 0.8);
      font-family: 'Syne', sans-serif;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .btn-disconnect:hover {
      background: rgba(239, 68, 68, 0.1);
      border-color: rgba(239, 68, 68, 0.6);
      color: #EF4444;
      transform: translateY(-1px);
    }

    .btn-disconnect:active {
      transform: translateY(0);
    }

    .auth-spinner {
      display: inline-block;
      width: 16px;
      height: 16px;
      border: 2px solid rgba(147, 51, 234, 0.3);
      border-top-color: #9333EA;
      border-radius: 50%;
      animation: spin 0.75s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .auth-error {
      font-size: 0.75rem;
      color: #EF4444;
      font-family: 'JetBrains Mono', monospace;
    }
  `],
})
export class AuthStatusComponent implements OnInit {
     protected authService = inject(AuthService);

     currentUser$ = this.authService.currentUser$;
     isLoading$ = this.authService.isLoading$;
     authError$ = this.authService.authError$;

     ngOnInit(): void {
          // Subscribe to authError$ and auto-dismiss after 5 seconds
          this.authError$.subscribe((error) => {
               if (error !== null) {
                    setTimeout(() => this.authService.authError$.next(null), 5000);
               }
          });
     }

     onLogin(): void {
          this.authService.login();
     }

     onLogout(): void {
          this.authService.logout().subscribe();
     }
}
