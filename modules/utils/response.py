"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           modules/utils/response.py                                        ║
║           Responsabilidade: Retornos padronizados para todo o sistema      ║
╚══════════════════════════════════════════════════════════════════════════════╝

POR QUE ISSO EXISTE?
─────────────────────
Um dos maiores problemas da V1.2 era o KeyError — o código tentava
acessar uma chave num dicionário que não existia.

Ex: resultado["conteudo"]  → crash se "conteudo" não foi definido.

A solução é garantir que TODO módulo retorne SEMPRE o mesmo formato.
Assim o código que lê o resultado sabe exatamente o que esperar.

REGRA GERAL DA V1.3:
    Sucesso → ok(dados={...})
    Erro    → erro("mensagem")

Todo consumidor usa .get() para segurança adicional.
"""


def ok(dados: dict = None, **kwargs) -> dict:
    """
    Retorna um dicionário de sucesso padronizado.

    Uso:
        return ok({"html": conteudo, "tokens": 1234})
        return ok(topicos=["loop", "array"], competencias=["Aplicar"])
    """
    resultado = {
        "sucesso": True,
        "erro":    None,
        "dados":   dados or {},
    }
    # Permite passar campos extras diretamente como kwargs
    if kwargs:
        resultado["dados"].update(kwargs)
    return resultado


def erro(mensagem: str, dados: dict = None) -> dict:
    """
    Retorna um dicionário de erro padronizado.

    Uso:
        return erro("Arquivo PDF não encontrado")
        return erro("Timeout na API", {"tentativas": 3})
    """
    return {
        "sucesso": False,
        "erro":    mensagem,
        "dados":   dados or {},
    }


def extrair(resultado: dict, chave: str, padrao=None):
    """
    Extrai um valor de resultado["dados"] com segurança.
    Nunca lança KeyError.

    Uso:
        html     = extrair(resultado, "html", "")
        topicos  = extrair(resultado, "topicos", [])
    """
    return resultado.get("dados", {}).get(chave, padrao)
