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
      width: 24px;
      height: 24px;
      border-radius: 50%;
      object-fit: cover;
    }

    .username {
      font-size: 14px;
    }

    .auth-spinner {
      display: inline-block;
      width: 16px;
      height: 16px;
      border: 2px solid currentColor;
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin 0.75s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .auth-error {
      font-size: 13px;
      color: #c0392b;
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
