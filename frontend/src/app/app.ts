import { Component, ChangeDetectorRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { MarkdownComponent } from 'ngx-markdown';
import { IssionService, AgentResponse } from './services/ission.service';

@Component({
     selector: 'app-root',
     imports: [FormsModule, CommonModule, MarkdownComponent],
     templateUrl: './app.html',
     styleUrl: './app.scss'
})
export class App {
     issueUrl: string = '';
     isLoading: boolean = false;
     apiResponse: AgentResponse | null = null;

     // --- Animação em cascata ---
     displayedThoughts: string[] = [];
     showFinalComment: boolean = false;
     isAnimating: boolean = false;

     // --- Publicação de comentário ---
     isPublishing: boolean = false;
     publishSuccess: boolean = false;
     publishError: string = '';
     commentUrl: string = '';

     constructor(
          private readonly issionService: IssionService,
          private readonly cdr: ChangeDetectorRef
     ) { }

     onAnalyze(): void {
          // Reset do estado
          this.isLoading = true;
          this.apiResponse = null;
          this.displayedThoughts = [];
          this.showFinalComment = false;
          this.isAnimating = false;
          this.publishSuccess = false;
          this.publishError = '';
          this.commentUrl = '';

          this.issionService.analyzeIssue(this.issueUrl).subscribe({
               next: (response) => {
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
      * Exibe os thoughts um a um com intervalo de 1.5s,
      * revelando o finalComment somente após o último.
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
                         // Último thought exibido — revelar o plano após breve pausa
                         setTimeout(() => {
                              this.isAnimating = false;
                              this.showFinalComment = true;
                              this.cdr.detectChanges();
                         }, 800);
                    }
               }
          };

          // Inicia a cascata
          setTimeout(showNext, 600);
     }

     /**
      * Publica o plano técnico como comentário real na issue do GitHub.
      */
     onPublishComment(): void {
          if (!this.apiResponse) return;

          this.isPublishing = true;
          this.publishError = '';

          this.issionService.publishComment(this.issueUrl, this.apiResponse.finalComment).subscribe({
               next: (response) => {
                    this.isPublishing = false;
                    this.publishSuccess = true;
                    this.commentUrl = response.comment_url;
                    this.cdr.detectChanges();
               },
               error: (err) => {
                    this.isPublishing = false;
                    this.publishError = err?.error?.detail || 'Erro ao publicar comentário. Tente novamente.';
                    this.cdr.detectChanges();
               }
          });
     }
}
