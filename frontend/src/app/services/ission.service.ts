import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

/** Issue quality score returned by the backend heuristic analysis. */
export interface QualityScore {
     score: number;           // 0–100
     level: 'low' | 'medium' | 'high';
     present: string[];
     missing: string[];
}

/** Foundry IQ classification result. */
export interface IssueClassification {
     type: string;            // Bug | Feature | Enhancement | Documentation | Refactor
     priority: string;        // Critical | High | Medium | Low
     confidence: string;      // high | medium | low
     rationale: string;
}

/** Full response structure returned by the agent analysis endpoint. */
export interface AgentResponse {
     status: string;
     thoughts: string[];
     finalComment: string;
     qualityScore: QualityScore | null;
     classification: IssueClassification | null;
}

/** Response structure for the publish-comment endpoint. */
export interface PublishResponse {
     status: string;
     message: string;
     comment_url: string;
}

/**
 * Service responsible for all HTTP communication with the Ission backend.
 */
@Injectable({ providedIn: 'root' })
export class IssionService {
     private readonly apiUrl = 'http://localhost:8000/api';

     constructor(private readonly http: HttpClient) { }

     analyzeIssue(issueUrl: string): Observable<AgentResponse> {
          return this.http.post<AgentResponse>(`${this.apiUrl}/analyze`, {
               url: issueUrl,
          }, { withCredentials: true });
     }

     publishComment(issueUrl: string, commentBody: string): Observable<PublishResponse> {
          return this.http.post<PublishResponse>(`${this.apiUrl}/publish-comment`, {
               issue_url: issueUrl,
               comment_body: commentBody,
          }, { withCredentials: true });
     }
}
