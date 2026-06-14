import { Component, ChangeDetectorRef, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule, AsyncPipe } from '@angular/common';
import { Router } from '@angular/router';
import { MarkdownComponent } from 'ngx-markdown';
import { IssionService, AgentResponse, QualityScore, IssueClassification } from '../services/ission.service';
import { AuthService } from '../auth/auth.service';
import { AuthStatusComponent } from '../auth/auth-status.component';

@Component({
     selector: 'app-analyser',
     standalone: true,
     imports: [FormsModule, CommonModule, AsyncPipe, MarkdownComponent, AuthStatusComponent],
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
          readonly authService: AuthService,
          private readonly router: Router
     ) { }

     ngOnInit(): void {
          this.authService.checkSession().subscribe();
     }

     goToLanding(): void {
          this.router.navigate(['/landing']);
     }

     /** Returns a CSS modifier class for the quality score level. */
     get qualityLevelClass(): string {
          const level = this.apiResponse?.qualityScore?.level;
          if (level === 'high') return 'quality--high';
          if (level === 'medium') return 'quality--medium';
          return 'quality--low';
     }

     /** Returns a CSS modifier class for the classification priority. */
     get priorityClass(): string {
          const p = this.apiResponse?.classification?.priority?.toLowerCase();
          if (p === 'critical') return 'priority--critical';
          if (p === 'high') return 'priority--high';
          if (p === 'medium') return 'priority--medium';
          return 'priority--low';
     }

     /** Returns a CSS modifier class for the classification type. */
     get typeClass(): string {
          const t = this.apiResponse?.classification?.type?.toLowerCase();
          if (t === 'bug') return 'type--bug';
          if (t === 'feature') return 'type--feature';
          if (t === 'enhancement') return 'type--enhancement';
          if (t === 'documentation') return 'type--documentation';
          return 'type--refactor';
     }

     onAnalyze(): void {
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
                         setTimeout(() => {
                              this.isAnimating = false;
                              this.showFinalComment = true;
                              this.cdr.detectChanges();
                         }, 800);
                    }
               }
          };

          setTimeout(showNext, 600);
     }

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
