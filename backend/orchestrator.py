"""
Ission Agent — Orquestrador principal.
Responsável por buscar dados reais da issue no GitHub e gerar
um plano técnico de resolução baseado integralmente nos dados recebidos.
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

    def _fetch_github_issue(self, issue_url: str, token: str | None = None) -> dict:
        """
        Faz um GET na API pública do GitHub para buscar os dados da issue.
        Retorna o JSON da resposta como dicionário.
        Levanta exceções em caso de erro de rede ou issue não encontrada.

        Args:
            issue_url: URL da issue no GitHub.
            token: Token OAuth do usuário. Quando fornecido, inclui o header
                   `Authorization: Bearer <token>` na requisição. Quando None,
                   acessa a API publicamente (sem autenticação).
        """
        owner, repo, issue_number = self._parse_github_url(issue_url)

        api_url = (
            f"{self._github_api_base}/{owner}/{repo}/issues/{issue_number}"
        )

        headers: dict[str, str] = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Ission-Agent/0.1",
        }
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(
            api_url,
            headers=headers,
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

    def _build_plan(self, issue_data: dict) -> str:
        """
        Gera um plano técnico em Markdown a partir dos dados reais da issue.
        O plano é construído integralmente com base no conteúdo recebido do GitHub:
        título, descrição completa, labels, milestone, autor e número de comentários.
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

        milestone = issue_data.get("milestone")
        milestone_text = (
            self._sanitize_html(milestone["title"]) if milestone else "não definido"
        )

        comment_count = issue_data.get("comments", 0)
        issue_number = issue_data.get("number", "?")
        repo_url = issue_data.get("repository_url", "")
        # Derive repo name from repository_url (e.g. https://api.github.com/repos/owner/repo)
        repo_name = "/".join(repo_url.rstrip("/").split("/")[-2:]) if repo_url else "desconhecido"

        labels_text = ", ".join(issue_labels) if issue_labels else "nenhuma"

        # Determine the nature of the issue from labels to tailor steps
        label_names_lower = [l.lower() for l in issue_labels]
        is_bug = any(l in label_names_lower for l in ("bug", "defect", "fix", "regression"))
        is_feature = any(l in label_names_lower for l in ("enhancement", "feature", "feature request"))
        is_docs = any(l in label_names_lower for l in ("documentation", "docs"))

        if is_bug:
            nature = "correção de bug"
            step1 = f"Reproduzir o comportamento descrito por @{issue_user} localmente, confirmando as condições exatas do problema."
            step2 = "Isolar a causa raiz: inspecionar logs, rastrear o fluxo de execução e identificar o ponto de falha."
            step3 = "Implementar a correção com o menor escopo possível, evitando quebrar comportamentos existentes."
            step4 = "Escrever testes de regressão que cubram o cenário que originou o bug, garantindo que ele não reapareça."
            step5 = "Abrir PR descrevendo o bug, a causa raiz identificada e a abordagem da correção, referenciando esta issue."
        elif is_feature:
            nature = "nova funcionalidade"
            step1 = f"Revisar o escopo proposto por @{issue_user} e alinhar com os requisitos do projeto antes de iniciar."
            step2 = "Desenhar a solução técnica: definir interfaces, contratos de API e impactos em módulos existentes."
            step3 = "Implementar a funcionalidade de forma incremental, mantendo compatibilidade com o código existente."
            step4 = "Cobrir a nova funcionalidade com testes unitários e de integração."
            step5 = "Abrir PR com descrição detalhada da funcionalidade, exemplos de uso e prints ou demos se aplicável."
        elif is_docs:
            nature = "melhoria de documentação"
            step1 = f"Identificar exatamente qual trecho da documentação está faltando ou incorreto conforme relatado por @{issue_user}."
            step2 = "Verificar se a documentação está desatualizada em relação ao código atual antes de reescrever."
            step3 = "Redigir a documentação corrigida, com exemplos claros e linguagem consistente com o restante do projeto."
            step4 = "Revisar internamente para garantir precisão técnica."
            step5 = "Abrir PR focado apenas na mudança de documentação, referenciando esta issue."
        else:
            nature = "melhoria / investigação"
            step1 = f"Entender completamente o contexto reportado por @{issue_user} e reproduzir o cenário descrito."
            step2 = "Investigar o impacto da mudança nos módulos relacionados antes de propor solução."
            step3 = "Implementar a solução seguindo os padrões do projeto e com o menor impacto lateral possível."
            step4 = "Garantir cobertura de testes para os caminhos afetados pela mudança."
            step5 = "Abrir PR com contexto claro sobre a decisão técnica tomada, referenciando esta issue."

        # Build the plan with full issue body, no truncation
        body_section = (
            issue_body.strip()
            if issue_body.strip()
            else "*Sem descrição fornecida na issue.*"
        )

        plan = (
            f"### Plano Técnico — {issue_title}\n\n"
            f"| Campo | Valor |\n"
            f"|---|---|\n"
            f"| **Repositório** | `{repo_name}` |\n"
            f"| **Issue** | #{issue_number} |\n"
            f"| **Autor** | @{issue_user} |\n"
            f"| **Labels** | {labels_text} |\n"
            f"| **Milestone** | {milestone_text} |\n"
            f"| **Comentários existentes** | {comment_count} |\n"
            f"| **Tipo identificado** | {nature} |\n\n"
            f"---\n\n"
            f"#### Descrição da Issue\n\n"
            f"{body_section}\n\n"
            f"---\n\n"
            f"#### Plano de Ação\n\n"
            f"1. **Entendimento:** {step1}\n"
            f"2. **Investigação:** {step2}\n"
            f"3. **Implementação:** {step3}\n"
            f"4. **Testes:** {step4}\n"
            f"5. **Revisão:** {step5}\n"
        )

        return plan

    # ------------------------------------------------------------------
    # Método público
    # ------------------------------------------------------------------

    async def process_issue(self, issue_url: str, token: str | None = None) -> dict:
        """
        Processa uma URL de issue do GitHub:
        1. Busca dados reais via API do GitHub.
        2. Gera um plano técnico baseado integralmente nos dados recebidos.

        Args:
            issue_url: URL da issue no GitHub.
            token: Token OAuth do usuário. Quando fornecido, as requisições à
                   API do GitHub são autenticadas com esse token. Quando None,
                   usa acesso público (ou fallback via GITHUB_TOKEN no caller).
        """
        try:
            # Etapa 1: Buscar dados reais da issue no GitHub
            issue_data = self._fetch_github_issue(issue_url, token=token)
            raw_title = issue_data.get("title", "Sem título")
            issue_title = self._sanitize_html(raw_title)

            # Etapa 2: Gerar plano técnico com dados reais
            plan = self._build_plan(issue_data)

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
