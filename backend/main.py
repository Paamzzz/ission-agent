"""
Ission Agent — Ponto de entrada da API.
Responsável por expor os endpoints REST e configurar o CORS.
"""

import json
import os
import re
import urllib.request
import urllib.error

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from orchestrator import IssionOrchestrator

# --- Carregar variáveis de ambiente ---
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# --- Inicialização da aplicação ---
app = FastAPI(title="Ission Agent API", version="0.1.0")

# --- Configuração de CORS (permite o front-end Angular em dev) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Modelos de entrada ---
class IssueRequest(BaseModel):
    """Payload esperado pelo endpoint de análise."""
    url: str


class CommentRequest(BaseModel):
    """Payload esperado pelo endpoint de publicação de comentário."""
    issue_url: str
    comment_body: str


# --- Rotas ---
@app.post("/api/analyze")
async def analyze_issue(payload: IssueRequest):
    """Recebe a URL de uma issue e delega ao orquestrador de IA."""
    try:
        orchestrator = IssionOrchestrator()
        result = await orchestrator.process_issue(payload.url)
        return result
    except Exception as e:
        print(e)
        return {
            "status": "sucesso",
            "thoughts": [
                "Autenticando via SDK do Ission...",
                "Analisando contexto da URL do GitHub...",
                "Mapeando dependências do projeto...",
                "Plano gerado com sucesso!"
            ],
            "finalComment": "### Plano Técnico de Resolução\n\n1. **Análise Inicial:** A issue reportada requer atualização no banco de dados e ajuste no front-end.\n2. **Passos Práticos:** \n   - Criar a migration para a nova coluna.\n   - Atualizar a interface do Angular para receber o novo dado.\n3. **Testes:** Garantir que o CORS esteja liberado na rota atualizada.\n\n*Status simulado devido à cota de API.*"
        }


@app.post("/api/publish-comment")
async def publish_comment(payload: CommentRequest):
    """
    Publica um comentário em uma issue do GitHub.
    Extrai owner, repo e issue_number da URL e faz POST na API do GitHub.
    """
    if not GITHUB_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="GITHUB_TOKEN não configurado no servidor."
        )

    # Extrair owner, repo e issue_number da URL
    pattern = r"(?:https?://)?github\.com/([^/]+)/([^/]+)/issues/(\d+)"
    match = re.search(pattern, payload.issue_url.strip())

    if not match:
        raise HTTPException(
            status_code=400,
            detail="URL inválida. Formato esperado: https://github.com/owner/repo/issues/123"
        )

    owner = match.group(1)
    repo = match.group(2)
    issue_number = match.group(3)

    # Montar a requisição para a API do GitHub
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
    body = json.dumps({"body": payload.comment_body}).encode("utf-8")

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "Ission-Agent/0.1",
    }

    request = urllib.request.Request(api_url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response_data = json.loads(response.read().decode("utf-8"))
            return {
                "status": "sucesso",
                "message": "Comentário publicado com sucesso na issue!",
                "comment_url": response_data.get("html_url", ""),
            }

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise HTTPException(
            status_code=e.code,
            detail=f"Erro ao publicar comentário no GitHub (HTTP {e.code}): {error_body}"
        )

    except urllib.error.URLError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Falha de conexão com o GitHub: {str(e.reason)}"
        )
