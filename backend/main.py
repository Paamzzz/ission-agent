"""
Ission Agent — Ponto de entrada da API.
Responsável por expor os endpoints REST e configurar o CORS.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orchestrator import IssionOrchestrator

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


# --- Rotas ---
@app.post("/api/analyze")
async def analyze_issue(payload: IssueRequest):
    """Recebe a URL de uma issue e delega ao orquestrador de IA."""
    orchestrator = IssionOrchestrator()
    result = await orchestrator.process_issue(payload.url)
    return result
