"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         providers/gemini_provider.py  (V1.6)                               ║
║         Gemini 2.5 Flash — máximo de saída, counters separados             ║
╚══════════════════════════════════════════════════════════════════════════════╝

MUDANÇAS V1.5 → V1.6:
    - max_output_tokens aumentado para 16.000 (permite apostilas muito maiores)
    - Sem stop_sequences que poderiam cortar a resposta prematuramente
    - Retorna tokens_entrada e tokens_saida separadamente
    - Retorna contagem real de palavras geradas
    - temperature 0.4 — levemente mais expressivo sem perder precisão
    - top_p e top_k ajustados para geração de texto longo
"""

import os
import re
import time
import logging
from providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)

MODELO_PADRAO = "gemini-2.5-flash"


class GeminiProvider(BaseProvider):
    """
    Provider Gemini 2.5 Flash — V1.6.
    Configurado para gerar apostilas longas e densas sem corte prematuro.
    """

    def __init__(self, api_key: str = None, modelo: str = None):
        try:
            import google.generativeai as genai
            self._genai = genai
        except ImportError:
            raise ImportError(
                "Biblioteca 'google-generativeai' não instalada.\n"
                "Execute: pip install google-generativeai"
            )

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY não encontrada no .env\n"
                "Obtenha em: https://aistudio.google.com/app/apikey"
            )

        self.modelo = modelo or os.getenv("GEMINI_MODEL", MODELO_PADRAO)

        self._genai.configure(api_key=self.api_key)

        # V1.6: 16.000 tokens de saída — apostilas muito mais densas
        # Sem stop_sequences — deixa a IA completar naturalmente
        self._gen_config = self._genai.GenerationConfig(
            temperature       = float(os.getenv("GEMINI_TEMPERATURE", "0.4")),
            max_output_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "16000")),
            top_p             = 0.95,
            top_k             = 64,
            # Sem stop_sequences — era um dos gargalos de corte prematuro
        )

        self._model = self._genai.GenerativeModel(
            model_name        = self.modelo,
            generation_config = self._gen_config,
        )

        logger.info(
            f"GeminiProvider V1.6 | Modelo: {self.modelo} | "
            f"Max tokens saída: {self._gen_config.max_output_tokens}"
        )

    def gerar(self, prompt: str) -> dict:
        """
        Gera apostila com Gemini 2.5 Flash.
        Retorna tokens de entrada e saída separadamente + contagem de palavras.
        """
        ultimo_erro = ""

        for tentativa in range(1, 4):
            try:
                logger.info(
                    f"Gemini: tentativa {tentativa}/3 | "
                    f"Prompt: {len(prompt)} chars (~{len(prompt)//4} tokens)"
                )

                resposta = self._model.generate_content(prompt)
                conteudo = self._extrair_texto(resposta)

                if not conteudo:
                    raise ValueError("Gemini retornou resposta vazia ou bloqueada pelos filtros")

                conteudo = self._limpar_markdown(conteudo)

                # Tokens separados (entrada / saída / total)
                tokens_entrada, tokens_saida, tokens_total = self._obter_tokens(resposta)

                # Contagem real de palavras no conteúdo gerado
                texto_puro  = re.sub(r"<[^>]+>", "", conteudo)
                palavras    = len(texto_puro.split())

                logger.info(
                    f"Gemini: sucesso | "
                    f"Entrada: {tokens_entrada} tk | "
                    f"Saída: {tokens_saida} tk | "
                    f"Total: {tokens_total} tk | "
                    f"Palavras: {palavras} | "
                    f"HTML: {len(conteudo)} chars"
                )

                return {
                    "sucesso":        True,
                    "conteudo":       conteudo,
                    "tokens_usados":  tokens_total,
                    "tokens_entrada": tokens_entrada,
                    "tokens_saida":   tokens_saida,
                    "palavras":       palavras,
                    "modelo":         self.modelo,
                    "provider":       "gemini",
                    "erro":           None,
                }

            except Exception as e:
                ultimo_erro = str(e)
                logger.warning(f"Gemini tentativa {tentativa} falhou: {ultimo_erro}")
                if tentativa < 3:
                    espera = 10 * tentativa
                    logger.info(f"Aguardando {espera}s...")
                    time.sleep(espera)

        return {
            "sucesso":        False,
            "conteudo":       "",
            "tokens_usados":  0,
            "tokens_entrada": 0,
            "tokens_saida":   0,
            "palavras":       0,
            "modelo":         self.modelo,
            "provider":       "gemini",
            "erro":           self._tratar_erro(ultimo_erro),
        }

    def verificar_conexao(self) -> dict:
        try:
            cfg_teste = self._genai.GenerationConfig(max_output_tokens=10)
            r = self._model.generate_content(
                "Responda apenas: OK",
                generation_config=cfg_teste,
            )
            texto = self._extrair_texto(r)
            if texto:
                return {"conectado": True, "mensagem": f"Gemini OK — {self.modelo}"}
            return {"conectado": False, "mensagem": "Resposta vazia"}
        except Exception as e:
            return {"conectado": False, "mensagem": self._tratar_erro(str(e))}

    def obter_info(self) -> dict:
        return {
            "nome":             "Google Gemini",
            "modelo":           self.modelo,
            "max_tokens_saida": int(os.getenv("GEMINI_MAX_TOKENS", "16000")),
            "provider":         "gemini",
            "temperatura":      float(os.getenv("GEMINI_TEMPERATURE", "0.4")),
        }

    # ─── Privados ─────────────────────────────────────────────

    def _extrair_texto(self, resposta) -> str:
        try:
            if hasattr(resposta, "text") and resposta.text:
                return resposta.text
            if hasattr(resposta, "candidates") and resposta.candidates:
                c = resposta.candidates[0]
                if hasattr(c, "content") and c.content:
                    return "".join(
                        p.text for p in c.content.parts if hasattr(p, "text")
                    )
        except Exception as e:
            logger.warning(f"Erro ao extrair texto: {e}")
        return ""

    def _limpar_markdown(self, texto: str) -> str:
        t = texto.strip()
        t = re.sub(r"^```html\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"^```\s*",     "", t)
        t = re.sub(r"\s*```$",     "", t)
        match = re.search(r"(?i)(<div|<!doctype)", t)
        if match and match.start() > 0:
            t = t[match.start():]
        return t.strip()

    def _obter_tokens(self, resposta) -> tuple[int, int, int]:
        """Retorna (tokens_entrada, tokens_saida, tokens_total)."""
        try:
            meta = getattr(resposta, "usage_metadata", None)
            if meta:
                entrada = getattr(meta, "prompt_token_count",      0) or 0
                saida   = getattr(meta, "candidates_token_count",  0) or 0
                total   = getattr(meta, "total_token_count",        0) or 0
                if total == 0:
                    total = entrada + saida
                return entrada, saida, total
        except Exception:
            pass
        return 0, 0, 0

    def _tratar_erro(self, erro: str) -> str:
        tabela = {
            "api_key_invalid":    "API Key inválida — verifique GEMINI_API_KEY no .env",
            "api key not valid":  "API Key inválida — verifique GEMINI_API_KEY no .env",
            "quota_exceeded":     "Cota esgotada — verifique seu plano no AI Studio",
            "rate_limit":         "Limite de requisições — aguarde e tente novamente",
            "model_not_found":    f"Modelo '{self.modelo}' não encontrado",
            "deadline_exceeded":  "Timeout — tente reduzir o contexto",
            "resource_exhausted": "Recursos esgotados — aguarde alguns minutos",
        }
        el = erro.lower()
        for k, v in tabela.items():
            if k in el:
                return v
        return f"Erro Gemini: {erro[:200]}"
