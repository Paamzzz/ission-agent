import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

/** Estrutura de resposta retornada pelo agente de análise. */
export interface AgentResponse {
  status: string;
  thoughts: string[];
  finalComment: string;
}

/**
 * Serviço responsável pela comunicação com o backend do Ission.
 * Centraliza todas as chamadas HTTP relacionadas à análise de issues.
 */
@Injectable({ providedIn: 'root' })
export class IssionService {
  /** URL base da API do backend. */
  private readonly apiUrl = 'http://localhost:8000/api';

  constructor(private readonly http: HttpClient) {}

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
}
