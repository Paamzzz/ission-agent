"""
Ission Agent — Orquestrador de IA.
Gerencia o pipeline de análise utilizando Semantic Kernel + Azure OpenAI (GPT-4o).
"""

import os

from dotenv import load_dotenv
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion


class IssionOrchestrator:
    """Orquestra o fluxo de análise de issues com agentes de IA."""

    def __init__(self) -> None:
        # Carrega variáveis de ambiente (.env) para credenciais do Azure OpenAI
        load_dotenv()

        # Inicializa o Kernel do Semantic Kernel
        self.kernel = Kernel()

        # Lê credenciais do Azure OpenAI a partir do .env
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")

        # Registra o serviço de Chat Completion do Azure OpenAI no kernel
        azure_chat_service = AzureChatCompletion(
            deployment_name=deployment_name,
            endpoint=endpoint,
            api_key=api_key,
        )
        self.kernel.add_service(azure_chat_service)

    async def process_issue(self, issue_url: str) -> dict:
        """
        Analisa a issue fornecida e retorna o resultado estruturado.

        Args:
            issue_url: URL pública da issue a ser processada.

        Returns:
            Dicionário compatível com a interface AgentResponse do front-end.
        """
        prompt = (
            "Você é o core do agente Ission. "
            "O usuário solicitou a análise da seguinte URL de Issue do GitHub: "
            f"{issue_url}. "
            "Como ainda estamos configurando as ferramentas de leitura do GitHub, "
            "simule o que seria o seu plano técnico de alto nível para resolver "
            "essa issue se baseando no título presumido dela. "
            "Responda de forma objetiva e técnica."
        )

        try:
            result = await self.kernel.invoke_prompt(prompt=prompt)
            final_comment = str(result)

            thoughts = [
                "Recebendo URL da issue...",
                "Enviando prompt ao Azure OpenAI (GPT-4o)...",
                "Processando resposta do modelo...",
                "Montando plano técnico de alto nível...",
            ]

            return {
                "status": "sucesso",
                "thoughts": thoughts,
                "finalComment": final_comment,
            }

        except Exception as e:
            return {
                "status": "erro",
                "thoughts": [
                    "Tentativa de conexão com Azure OpenAI...",
                    "Falha na comunicação com a API.",
                ],
                "finalComment": (
                    f"Não foi possível obter resposta da IA. "
                    f"Verifique suas credenciais no arquivo .env. "
                    f"Detalhe do erro: {str(e)}"
                ),
            }
