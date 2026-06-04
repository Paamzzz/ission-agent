"""
Ission Agent — Orquestrador principal.
Responsável por buscar dados reais da issue no GitHub e gerar
um plano técnico de resolução (mock dinâmico enquanto a IA está com cota limitada).
"""

import json
import os
import re
import urllib.request
import urllib.error

from dotenv import load_dotenv


class IssionOrchestrator:

    def __init__(self) -> None:
        load_dotenv()
        self.api_key = os.getenv("GEMINI_API_KEY")
        self._github_api_base = "https://api.github.com/repos"

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    def _parse_github_url(self, issue_url: str) -> tuple[str, str, str]:
        """
        Extrai owner, repo e issue_number de uma URL do GitHub.
        Aceita formatos como:
          - https://github.com/owner/repo/issues/123
          - http://github.com/owner/repo/issues/123
          - github.com/owner/repo/issues/123
        Retorna uma tupla (owner, repo, issue_number).
        Levanta ValueError se o formato for inválido.
        """
        pattern = r"(?:https?://)?github\.com/([^/]+)/([^/]+)/issues/(\d+)"
        match = re.search(pattern, issue_url.strip())

        if not match:
            raise ValueError(
                f"URL inválida. Formato esperado: "
                f"https://github.com/owner/repo/issues/123"
            )

        owner = match.group(1)
        repo = match.group(2)
        issue_number = match.group(3)

        return owner, repo, issue_number

    def _fetch_github_issue(self, issue_url: str) -> dict:
        """
        Faz um GET na API pública do GitHub para buscar os dados da issue.
        Retorna o JSON da resposta como dicionário.
        Levanta exceções em caso de erro de rede ou issue não encontrada.
        """
        owner, repo, issue_number = self._parse_github_url(issue_url)

        api_url = (
            f"{self._github_api_base}/{owner}/{repo}/issues/{issue_number}"
        )

        request = urllib.request.Request(
            api_url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Ission-Agent/0.1",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data

        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError(
                    "Issue não encontrada. Verifique se a URL está correta "
                    "e se o repositório é público."
                )
            elif e.code == 403:
                raise ValueError(
                    "Acesso negado pela API do GitHub (rate limit ou "
                    "repositório privado). Tente novamente em alguns minutos."
                )
            else:
                raise ValueError(
                    f"Erro ao acessar a API do GitHub (HTTP {e.code}). "
                    f"Verifique a URL e tente novamente."
                )

        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Falha de conexão com o GitHub. "
                f"Verifique sua internet. Detalhe: {str(e.reason)}"
            )

    def _sanitize_html(self, text: str) -> str:
        """
        Escapa caracteres HTML perigosos (< e >) para evitar que o
        navegador interprete conteúdo de issues como tags HTML reais.
        """
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _build_mock_plan(self, issue_data: dict) -> str:
        """
        Gera um plano técnico em Markdown usando dados reais da issue.
        Funciona como mock dinâmico enquanto a IA (Gemini) está com cota.
        """
        raw_title = issue_data.get("title", "Título não disponível")
        issue_title = self._sanitize_html(raw_title)
        raw_body = issue_data.get("body", "") or ""
        issue_body = self._sanitize_html(raw_body)
        issue_labels = [
            self._sanitize_html(label.get("name", ""))
            for label in issue_data.get("labels", [])
        ]
        issue_user = self._sanitize_html(
            issue_data.get("user", {}).get("login", "desconhecido")
        )

        labels_text = ", ".join(issue_labels) if issue_labels else "nenhuma"

        # Resumo do body (primeiros 200 caracteres para contexto)
        body_preview = (
            issue_body[:200] + "..." if len(issue_body) > 200 else issue_body
        )

        plan = (
            f"### Plano Técnico de Resolução para: {issue_title}\n\n"
            f"**Autor da issue:** @{issue_user}\n"
            f"**Labels:** {labels_text}\n\n"
            f"---\n\n"
            f"#### Contexto\n"
            f"{body_preview}\n\n"
            f"---\n\n"
            f"#### Passos Propostos\n\n"
            f"1. **Análise:** A issue reportada requer investigação do "
            f"comportamento descrito em \"{issue_title}\".\n"
            f"2. **Reprodução:** Configurar ambiente local para reproduzir "
            f"o cenário reportado.\n"
            f"3. **Implementação:** Desenvolver a correção/feature seguindo "
            f"os padrões do projeto.\n"
            f"4. **Testes:** Criar testes unitários e de integração para "
            f"validar a solução.\n"
            f"5. **Code Review:** Submeter PR com descrição detalhada "
            f"referenciando esta issue.\n\n"
            f"---\n\n"
            f"*Plano gerado via Mock Dinâmico do Ission Agent "
            f"(dados reais do GitHub, IA temporariamente indisponível).*"
        )

        return plan

    # ------------------------------------------------------------------
    # Método público
    # ------------------------------------------------------------------

    async def process_issue(self, issue_url: str) -> dict:
        """
        Processa uma URL de issue do GitHub:
        1. Busca dados reais via API pública do GitHub.
        2. Gera um plano técnico formatado em Markdown (mock dinâmico).
        """
        try:
            # Etapa 1: Buscar dados reais da issue no GitHub
            issue_data = self._fetch_github_issue(issue_url)
            raw_title = issue_data.get("title", "Sem título")
            issue_title = self._sanitize_html(raw_title)

            # Etapa 2: Gerar plano técnico com dados reais
            plan = self._build_mock_plan(issue_data)

            return {
                "status": "sucesso",
                "thoughts": [
                    "Validando URL da issue...",
                    f"Issue encontrada: \"{issue_title}\"",
                    "Extraindo metadados (labels, autor, corpo)...",
                    "Gerando plano técnico de resolução...",
                    "Plano gerado com sucesso!",
                ],
                "finalComment": plan,
            }

        except ValueError as e:
            # URL inválida ou issue não encontrada
            return {
                "status": "erro",
                "thoughts": [
                    "Validando URL da issue...",
                    "Falha na validação ou busca da issue.",
                ],
                "finalComment": (
                    f"**Erro ao processar a issue:**\n\n"
                    f"{str(e)}\n\n"
                    f"Possíveis causas:\n"
                    f"- A URL fornecida não segue o formato "
                    f"`https://github.com/owner/repo/issues/123`\n"
                    f"- O repositório é privado\n"
                    f"- O número da issue não existe neste repositório"
                ),
            }

        except ConnectionError as e:
            # Falha de rede
            return {
                "status": "erro",
                "thoughts": [
                    "Tentando conexão com a API do GitHub...",
                    "Falha de rede detectada.",
                ],
                "finalComment": (
                    f"**Erro de conexão:**\n\n{str(e)}\n\n"
                    f"Verifique sua conexão com a internet e tente novamente."
                ),
            }

        except Exception as e:
            # Erro inesperado
            return {
                "status": "erro",
                "thoughts": [
                    "Processando issue...",
                    "Erro inesperado durante a execução.",
                ],
                "finalComment": (
                    f"**Erro inesperado:**\n\n"
                    f"Ocorreu um problema não previsto. "
                    f"Detalhe: {str(e)}"
                ),
            }
