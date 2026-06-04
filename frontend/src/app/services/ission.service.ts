import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

/** Estrutura de resposta retornada pelo agente de análise. */
export interface AgentResponse {
     status: string;
     thoughts: string[];
     finalComment: string;
}

/** Estrutura de resposta da publicação de comentário. */
export interface PublishResponse {
     status: string;
     message: string;
     comment_url: string;
}

/**
 * Serviço responsável pela comunicação com o backend do Ission.
 * Centraliza todas as chamadas HTTP relacionadas à análise de issues.
 */
@Injectable({ providedIn: 'root' })
export class IssionService {
     /** URL base da API do backend. */
     private readonly apiUrl = 'http://localhost:8000/api';

     constructor(private readonly http: HttpClient) { }

     /**
      * Envia a URL de uma issue para análise pelo agente.
      * @param issueUrl - URL pública da issue a ser analisada.
      * @returns Observable com a resposta estruturada do agente.
      */
     analyzeIssue(issueUrl: string): Observable<AgentResponse> {
          return this.http.post<AgentResponse>(`${this.apiUrl}/analyze`, {
               url: issueUrl,
          });
     }

     /**
      * Publica o plano técnico como comentário na issue do GitHub.
      * @param issueUrl - URL da issue onde o comentário será publicado.
      * @param commentBody - Conteúdo Markdown do comentário.
      * @returns Observable com a resposta de sucesso/erro.
      */
     publishComment(issueUrl: string, commentBody: string): Observable<PublishResponse> {
          return this.http.post<PublishResponse>(`${this.apiUrl}/publish-comment`, {
               issue_url: issueUrl,
               comment_body: commentBody,
          });
     }
}
