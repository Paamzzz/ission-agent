import { Component, ChangeDetectorRef, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MarkdownComponent } from 'ngx-markdown';
import { IssionService, AgentResponse } from '../services/ission.service';
import { AuthService } from '../auth/auth.service';
import { AuthStatusComponent } from '../auth/auth-status.component';

@Component({
     selector: 'app-analyser',
     standalone: true,
     imports: [FormsModule, CommonModule, MarkdownComponent, AuthStatusComponent],
     templateUrl: './analyser.html',
     styleUrl: './analyser.scss'
})
export class Analyser implements OnInit {
     issueUrl: string = '';
     isLoading: boolean = false;
     apiResponse: AgentResponse | null = null;

     // --- Cascade animation ---
     displayedThoughts: string[] = [];
     showFinalComment: boolean = false;
     isAnimating: boolean = false;

     // --- Comment publishing ---
     isPublishing: boolean = false;
     publishSuccess: boolean = false;
     publishError: string = '';
     commentUrl: string = '';

     constructor(
          private readonly issionService: IssionService,
          private readonly cdr: ChangeDetectorRef,
          private readonly authService: AuthService,
          private readonly router: Router
     ) { }

     ngOnInit(): void {
          this.authService.checkSession().subscribe();
     }

     goToLanding(): void {
          this.router.navigate(['/landing']);
     }

     onAnalyze(): void {
          // Reset state
          this.isLoading = true;
          this.apiResponse = null;
          this.displayedThoughts = [];
          this.showFinalComment = false;
          this.isAnimating = false;
          this.publishSuccess = false;
          this.publishError = '';
          this.commentUrl = '';

          this.issionService.analyzeIssue(this.issueUrl).subscribe({
               next: (response: AgentResponse) => {
                    this.apiResponse = response;
                    this.isLoading = false;
                    this.startThoughtAnimation(response.thoughts);
                    this.cdr.detectChanges();
               },
               error: () => {
                    this.isLoading = false;
                    this.cdr.detectChanges();
               }
          });
     }

     /**
      * Displays thoughts one by one at 1.5s intervals,
      * revealing finalComment only after the last one.
      */
     private startThoughtAnimation(thoughts: string[]): void {
          this.isAnimating = true;
          let index = 0;

          const showNext = () => {
               if (index < thoughts.length) {
                    this.displayedThoughts.push(thoughts[index]);
                    index++;
                    this.cdr.detectChanges();

                    if (index < thoughts.length) {
                         setTimeout(showNext, 1500);
                    } else {
                         // Last thought displayed — reveal plan after brief pause
                         setTimeout(() => {
                              this.isAnimating = false;
                              this.showFinalComment = true;
                              this.cdr.detectChanges();
                         }, 800);
                    }
               }
          };

          // Start cascade
          setTimeout(showNext, 600);
     }

     /**
      * Publishes the technical plan as a real comment on the GitHub issue.
      */
     onPublishComment(): void {
          if (!this.apiResponse) return;

          this.isPublishing = true;
          this.publishError = '';

          this.issionService.publishComment(this.issueUrl, this.apiResponse.finalComment).subscribe({
               next: (response: { comment_url: string }) => {
                    this.isPublishing = false;
                    this.publishSuccess = true;
                    this.commentUrl = response.comment_url;
                    this.cdr.detectChanges();
               },
               error: (err: { error?: { detail?: string } }) => {
                    this.isPublishing = false;
                    this.publishError = err?.error?.detail || 'Failed to publish comment. Please try again.';
                    this.cdr.detectChanges();
               }
          });
     }
}
