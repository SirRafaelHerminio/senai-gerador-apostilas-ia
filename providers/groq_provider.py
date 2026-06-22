"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           providers/groq_provider.py  (V1.3)                               ║
║           Integração com Groq API — provider principal                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

COMO OBTER SUA CHAVE GROQ (GRATUITA):
  1. Acesse https://console.groq.com
  2. Crie uma conta (gratuito)
  3. Menu: API Keys → Create API Key
  4. Copie e cole no .env: GROQ_API_KEY=gsk_...

MODELOS DISPONÍVEIS (gratuitos/acessíveis):
  llama-3.3-70b-versatile      → RECOMENDADO (melhor qualidade)
  llama-3.1-8b-instant         → mais rápido, menor qualidade
  deepseek-r1-distill-llama-70b→ ótimo para conteúdo técnico estruturado
  mixtral-8x7b-32768           → contexto 32k — bom para documentos longos
  gemma2-9b-it                 → leve e eficiente

LIMITES GRATUITOS (aproximados, podem mudar):
  30 req/min | 500.000 tokens/dia
  Suficiente para dezenas de apostilas por dia.
"""

import os
import time
import logging
from groq import Groq
from providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)

MODELO_PADRAO = "llama-3.3-70b-versatile"


class GroqProvider(BaseProvider):

    def __init__(self, api_key: str = None, modelo: str = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY não encontrada no .env\n"
                "Obtenha em: https://console.groq.com"
            )
        self.modelo = modelo or os.getenv("GROQ_MODEL", MODELO_PADRAO)
        self.client = Groq(api_key=self.api_key)
        logger.info(f"GroqProvider iniciado | Modelo: {self.modelo}")

    def gerar(self, prompt: str, json_mode: bool = False) -> dict:
        """Envia prompt ao Groq com retry automático (3 tentativas)."""
        for tentativa in range(1, 4):
            try:
                logger.info(
                    f"Groq: tentativa {tentativa}/3 | "
                    f"~{len(prompt)//4} tokens no prompt"
                )
                resp = self.client.chat.completions.create(
                    model    = self.modelo,
                    messages = [
                        {
                            "role": "system",
                            "content": (
                                "Você é um especialista em materiais didáticos do SENAI. "
                                "Siga todas as instruções rigorosamente. "
                                "Retorne APENAS o HTML solicitado — uma única <div> "
                                "com CSS inline. Sem markdown, sem explicações externas."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature = float(os.getenv("GROQ_TEMPERATURE", "0.3")),
                    max_tokens  = int(os.getenv("GROQ_MAX_TOKENS", "8192")),
                )

                conteudo = resp.choices[0].message.content or ""
                tokens   = resp.usage.total_tokens if resp.usage else 0

                logger.info(f"Groq: sucesso | {tokens} tokens | {len(conteudo)} chars")

                return {
                    "sucesso":       True,
                    "conteudo":      conteudo,
                    "tokens_usados": tokens,
                    "modelo":        self.modelo,
                    "provider":      "groq",
                    "erro":          None,
                }

            except Exception as e:
                logger.warning(f"Groq tentativa {tentativa} falhou: {e}")
                if tentativa < 3:
                    time.sleep(5 * tentativa)

        return {
            "sucesso":       False,
            "conteudo":      "",
            "tokens_usados": 0,
            "modelo":        self.modelo,
            "provider":      "groq",
            "erro":          self._tratar_erro(str(e)),
        }

    def verificar_conexao(self) -> dict:
        try:
            r = self.client.chat.completions.create(
                model    = self.modelo,
                messages = [{"role": "user", "content": "OK"}],
                max_tokens = 5,
            )
            return {"conectado": bool(r.choices), "mensagem": f"Groq OK — {self.modelo}"}
        except Exception as e:
            return {"conectado": False, "mensagem": f"Groq erro: {self._tratar_erro(str(e))}"}

    def obter_info(self) -> dict:
        return {
            "nome":             "Groq",
            "modelo":           self.modelo,
            "max_tokens_saida": int(os.getenv("GROQ_MAX_TOKENS", "8192")),
            "provider":         "groq",
        }

    def _tratar_erro(self, e: str) -> str:
        tabela = {
            "invalid_api_key":  "API Key inválida — verifique GROQ_API_KEY no .env",
            "rate_limit":       "Limite de requisições atingido — aguarde 1 minuto",
            "model_not_found":  f"Modelo '{self.modelo}' não encontrado — verifique GROQ_MODEL",
            "context_length":   "Prompt muito longo — reduza o conteúdo ou use o Mixtral",
        }
        for chave, msg in tabela.items():
            if chave in e.lower():
                return msg
        return f"Erro Groq: {e}"
