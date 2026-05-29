import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { IssionService, AgentResponse } from './services/ission.service';

@Component({
     selector: 'app-root',
     imports: [FormsModule, CommonModule],
     templateUrl: './app.html',
     styleUrl: './app.scss'
})
export class App {
     issueUrl: string = '';
     isLoading: boolean = false;
     apiResponse: AgentResponse | null = null;

     constructor(private readonly issionService: IssionService) { }

     onAnalyze(): void {
          this.isLoading = true;
          this.issionService.analyzeIssue(this.issueUrl).subscribe({
               next: (response) => {
                    this.apiResponse = response;
                    this.isLoading = false;
               },
               error: () => {
                    this.isLoading = false;
               }
          });
     }
}
