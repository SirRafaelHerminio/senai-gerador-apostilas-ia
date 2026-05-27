"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         providers/provider_manager.py  (V1.5)                              ║
║         Gerenciador de providers — Gemini como padrão                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

V1.5: provider padrão alterado para "gemini"
"""

import os
import logging
import importlib
from providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)

_REGISTRY = {
    "gemini": "providers.gemini_provider.GeminiProvider",
    "groq":   "providers.groq_provider.GroqProvider",
}


class ProviderManager:

    def __init__(self, provider_nome: str = None):
        self.provider_nome = (
            provider_nome
            or os.getenv("AI_PROVIDER", "gemini")   # V1.5: padrão gemini
        ).lower().strip()
        self._instance: BaseProvider | None = None

    def obter_provider(self) -> BaseProvider:
        if self._instance is None:
            self._instance = self._instanciar()
        return self._instance

    def verificar_conexao(self) -> dict:
        try:
            resultado = self.obter_provider().verificar_conexao()
            resultado["provider"] = self.provider_nome
            return resultado
        except (ValueError, ImportError) as e:
            return {"conectado": False, "mensagem": str(e), "provider": self.provider_nome}
        except Exception as e:
            return {
                "conectado": False,
                "mensagem":  f"Erro ao inicializar '{self.provider_nome}': {e}",
                "provider":  self.provider_nome,
            }

    def info(self) -> dict:
        try:
            return self.obter_provider().obter_info()
        except Exception:
            return {"nome": self.provider_nome, "status": "não inicializado"}

    def providers_disponiveis(self) -> list:
        return list(_REGISTRY.keys())

    def _instanciar(self) -> BaseProvider:
        if self.provider_nome not in _REGISTRY:
            raise ValueError(
                f"Provider '{self.provider_nome}' não reconhecido.\n"
                f"Disponíveis: {', '.join(_REGISTRY.keys())}\n"
                f"Configure AI_PROVIDER no .env"
            )
        caminho   = _REGISTRY[self.provider_nome]
        mod_path, cls_name = caminho.rsplit(".", 1)
        try:
            modulo   = importlib.import_module(mod_path)
            Classe   = getattr(modulo, cls_name)
            instancia = Classe()
            logger.info(f"Provider '{self.provider_nome}' iniciado: {cls_name}")
            return instancia
        except ImportError as e:
            raise ImportError(
                f"Biblioteca para '{self.provider_nome}' não instalada.\n"
                f"Execute: pip install -r requirements.txt\nDetalhe: {e}"
            )
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Falha ao inicializar '{self.provider_nome}': {e}")
