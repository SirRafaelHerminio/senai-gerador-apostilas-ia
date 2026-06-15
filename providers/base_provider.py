"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           providers/base_provider.py  (V1.3)                               ║
║           Contrato abstrato para todos os providers de IA                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

TODO provider deve:
  1. Herdar de BaseProvider
  2. Implementar: gerar(), verificar_conexao(), obter_info()
  3. Retornar dicionários padronizados

Providers planejados:
  ✅ groq_provider.py       — Groq (Llama, Mixtral, DeepSeek)
  ✅ gemini_provider.py     — Google Gemini (backup)
  🔜 openrouter_provider.py — OpenRouter (100+ modelos)
  🔜 openai_provider.py     — GPT-4
  🔜 local_provider.py      — Ollama (100% local, sem internet)
"""

from abc import ABC, abstractmethod


class BaseProvider(ABC):

    @abstractmethod
    def gerar(self, prompt: str) -> dict:
        """
        Envia o prompt e retorna conteúdo gerado.

        Returns sempre:
            {
                "sucesso":       bool,
                "conteudo":      str,
                "tokens_usados": int,
                "modelo":        str,
                "provider":      str,
                "erro":          str | None,
            }
        """
        pass

    @abstractmethod
    def verificar_conexao(self) -> dict:
        """
        Returns:
            { "conectado": bool, "mensagem": str }
        """
        pass

    @abstractmethod
    def obter_info(self) -> dict:
        """
        Returns:
            { "nome": str, "modelo": str, "max_tokens_saida": int }
        """
        pass
