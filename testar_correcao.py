#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
  testar_correcao.py - Teste local do gerador de apostilas SENAI
  Roda o PIPELINE REAL com um provider FALSO - sem API, sem internet.
==============================================================================

COMO USAR:
    1. Coloque este arquivo na RAIZ do projeto (mesma pasta do app.py).
    2. Rode:   python testar_correcao.py
    3. Leia o relatorio e abra os DOCX gerados em  output_teste/

Sao dois niveis de teste:

  NIVEL A - Resiliencia do parser (a peca que quebrava):
    Alimenta o ContentGenerator com respostas problematicas (JSON truncado,
    texto antes/depois, cerca markdown, resposta cortada) e confere que NENHUM
    capitulo sai vazio.

  NIVEL B - Fluxo completo /gerar:
    Roda o ApostilaService.gerar() inteiro (mapa -> capitulos -> validacao ->
    DOCX) com leitores stubados e um provider falso "inteligente", provando
    que o caminho de producao gera uma apostila com capitulos preenchidos -
    inclusive recuperando um capitulo cuja resposta veio truncada.
"""

import os
import sys
import json
import logging

logging.basicConfig(level=logging.WARNING, format="   . %(message)s")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from modules.services.content_generator import ContentGenerator
    from modules.services.apostila_service  import ApostilaService, _validar_capitulo
    from modules.exporters.docx_builder      import DocxBuilder
    from modules.utils.response              import ok, extrair
except Exception as e:
    print(f"\n[ERRO] Nao consegui importar os modulos do projeto.\n   Erro: {e}")
    print("   Coloque este arquivo na RAIZ do projeto (junto do app.py).\n")
    sys.exit(1)

PASTA_OUT = "output_teste"


# ===================================================================
#  FIXTURE - capitulo realista (tema de jogos, pra ficar familiar)
# ===================================================================
def _secao(titulo):
    conteudo = (
        "Estruturas de controle determinam o fluxo de execucao de um programa. "
        "Em C#, o condicional if avalia uma expressao booleana e executa o bloco "
        "apenas quando o resultado e verdadeiro. No desenvolvimento de jogos com "
        "Unity 6 isso aparece o tempo todo: checar se a vida do jogador chegou a "
        "zero, se uma tecla foi pressionada ou se um inimigo esta no alcance. "
    ) * 5
    return {
        "titulo": titulo, "conteudo": conteudo,
        "codigo": {"linguagem": "csharp",
                   "titulo": "Verificacao de vida no Update()",
                   "codigo": ("void Update()\n{\n    // Checa a cada frame\n"
                              "    if (vidaAtual <= 0)\n    {\n"
                              "        GerenciarMorte();\n    }\n}")},
        "tabela": None,
        "boxes": [
            {"tipo": "atencao", "titulo": "Atencao",
             "conteudo": "Erro comum: usar = (atribuicao) no lugar de == (comparacao)."},
            {"tipo": "pratica", "titulo": "Contexto Profissional",
             "conteudo": "Estudios usam switch para maquinas de estado de personagens."},
        ],
        "subsecoes": [],
    }


def _capitulo_json(numero, titulo, subtitulo, n_secoes=3):
    return {
        "numero": numero, "titulo": titulo, "subtitulo": subtitulo,
        "introducao": "Introducao contextualizando o capitulo dentro do Unity 6.",
        "secoes": [_secao(f"Secao {i+1} de {titulo}") for i in range(n_secoes)],
        "resumo_secao": "Sintese do que foi visto.",
        "saep_relevante": (numero == 1),
        "conexao_proximo": "Seguimos para o proximo tema.",
    }


# ===================================================================
#  PROVIDERS FALSOS
# ===================================================================
def _resp(conteudo):
    return {"sucesso": True, "conteudo": conteudo, "tokens_entrada": 1500,
            "tokens_saida": 3000, "tokens_usados": 4500, "palavras": 600,
            "modelo": "fake", "provider": "fake", "erro": None}


class ProviderFixo:
    """Devolve sempre a mesma resposta crua (para o Nivel A)."""
    def __init__(self, conteudo):
        self.conteudo = conteudo

    def gerar(self, prompt):
        return _resp(self.conteudo)


class ProviderInteligente:
    """
    Para o Nivel B: responde conforme o prompt.
    - Prompt do mapa  -> devolve um mapa com 2 capitulos.
    - Prompt do cap 1 -> JSON completo.
    - Prompt do cap 2 -> JSON TRUNCADO (simula corte por limite de tokens).
    """
    def gerar(self, prompt):
        if '"capitulos"' in prompt:                     # planner (mapa pedagogico)
            mapa = {
                "titulo_apostila": "Controle e Repeticao em C# para Jogos",
                "estimativa_capitulos": 2,
                "capitulos": [
                    {"numero": 1, "titulo": "Estruturas de Controle em C#",
                     "subtitulo": "Condicionais no Unity 6",
                     "topicos": ["if/else", "switch"], "profundidade": "aplicacao",
                     "saep_relevante": True},
                    {"numero": 2, "titulo": "Lacos de Repeticao no Unity 6",
                     "subtitulo": "for, while e foreach",
                     "topicos": ["for", "while", "foreach"], "profundidade": "aplicacao",
                     "saep_relevante": False},
                ],
            }
            return _resp(json.dumps(mapa, ensure_ascii=False))

        # geracao de capitulo
        if "2/2" in prompt or "Lacos de Repeticao" in prompt:
            cap = _capitulo_json(2, "Lacos de Repeticao no Unity 6", "for, while e foreach")
            inteiro = json.dumps(cap, ensure_ascii=False, indent=2)
            return _resp(inteiro[:int(len(inteiro) * 0.65)])   # TRUNCADO de proposito
        cap = _capitulo_json(1, "Estruturas de Controle em C#", "Condicionais no Unity 6")
        return _resp(json.dumps(cap, ensure_ascii=False, indent=2))


# ===================================================================
#  NIVEL A - resiliencia do parser
# ===================================================================
def nivel_a():
    print("\n" + "=" * 74)
    print("  NIVEL A - Resiliencia do parser (cenarios que causavam vazio)")
    print("=" * 74)

    completo = _capitulo_json(1, "Estruturas de Controle em C#", "Condicionais")
    j = json.dumps(completo, ensure_ascii=False, indent=2)
    cortada_inicio = j[len(j) // 3:]

    cenarios = [
        ("1. JSON completo",               j,                                 3),
        ("2. JSON truncado a 70%",         j[:int(len(j) * 0.70)],            1),
        ("3. JSON truncado a 50%",         j[:int(len(j) * 0.50)],            1),
        ("4. JSON com texto antes/depois", f"Claro! Segue:\n\n{j}\n\nPronto!", 3),
        ("5. JSON dentro de cerca md",     f"```json\n{j}\n```",              3),
        ("6. Resposta cortada no inicio",  cortada_inicio,                    1),
    ]

    aprovados = 0
    for nome, resposta, min_sec in cenarios:
        cg = ContentGenerator(provider=ProviderFixo(resposta))
        res = cg.gerar_capitulo_json(
            capitulo={"numero": 1, "titulo": "Estruturas de Controle em C#",
                      "subtitulo": "Condicionais", "saep_relevante": True},
            total_capitulos=1, curso="Jogos Digitais", uc="Logica",
            bloco_aula="Bloco 1", titulo_apostila="Teste", extrato_uc="apoio")
        dados = res.get("dados", {})          # <- como a producao (corrigida) le
        valido, motivo = _validar_capitulo({**dados, "saep_relevante": True}, 1)
        n = len(dados.get("secoes", []))
        ch = sum(len(s.get("conteudo", "")) for s in dados.get("secoes", []))
        passou = valido and n >= min_sec and ch > 0
        aprovados += passou
        print(f"\n[{'PASSOU' if passou else 'FALHOU'}]  {nome}")
        print(f"          secoes={n} | conteudo={ch} chars | "
              f"{'OK' if valido else 'REJEITADO: ' + motivo}")
    print(f"\n  -> Nivel A: {aprovados}/{len(cenarios)} cenarios")
    return aprovados, len(cenarios)


# ===================================================================
#  NIVEL B - fluxo completo /gerar (com stubs)
# ===================================================================
def nivel_b():
    print("\n" + "=" * 74)
    print("  NIVEL B - Fluxo completo ApostilaService.gerar() (rota /gerar)")
    print("=" * 74)

    svc = ApostilaService(config={"OUTPUT_FOLDER": PASTA_OUT})

    # Stubs dos leitores (sem PDFs, sem disco)
    svc.course_reader.ler_uc   = lambda curso, uc: ok(texto="Conteudo da UC de apoio.",
                                                      curso=curso, uc=uc)
    svc.saep_reader.ler_curso  = lambda curso: ok(total_arquivos=0, tem_conteudo=False)
    svc.doc_reader.ler         = lambda caminho: ok(texto="")
    svc.extractor.extrair_uc   = lambda texto, bloco: ok(resumo_formatado="Resumo da UC.")
    svc.extractor.extrair_saep = lambda res: ok(resumo_formatado="")
    # Provider falso inteligente (mapa + 2 capitulos, sendo o 2o truncado)
    svc.provider_mgr.obter_provider = lambda: ProviderInteligente()

    res = svc.gerar(curso="Programacao de Jogos Digitais", uc="Logica de Programacao",
                    bloco_aula="Bloco de Teste", professor="Henrique")

    if not res.get("sucesso"):
        print(f"\n  [FALHOU] /gerar retornou erro: {res.get('erro')}")
        return 0, 1

    dados = res.get("dados", {})
    metr  = dados.get("metricas", {})
    apo   = dados.get("apostila", {})
    n_caps = metr.get("total_capitulos", 0)
    falhos = metr.get("capitulos_falhos", 0)
    arq    = apo.get("nome_arquivo", "")
    caminho = os.path.join(PASTA_OUT, arq)

    print(f"\n  [OK] Apostila gerada com sucesso")
    print(f"          capitulos no documento : {n_caps}  (esperado: 2)")
    print(f"          capitulos com falha     : {falhos}")
    print(f"          palavras totais         : {metr.get('total_palavras', 0)}")
    print(f"          arquivo                 : {os.path.abspath(caminho)}")
    for aviso in dados.get("avisos", []):
        print(f"          aviso: {aviso}")

    corpo_ok = _docx_tem_corpo(caminho)
    print(f"          corpo dos capitulos no DOCX: {'OK (tem texto)' if corpo_ok else 'VAZIO'}")

    passou = (n_caps >= 2 and corpo_ok)
    print(f"\n  -> Nivel B: {'PASSOU' if passou else 'FALHOU'}")
    return (1 if passou else 0), 1


def _docx_tem_corpo(caminho):
    try:
        from docx import Document
        d = Document(caminho)
        textos = [p.text for p in d.paragraphs if p.text.strip()]
        return any("Estruturas de controle determinam" in t or "Secao" in t for t in textos)
    except Exception as e:
        print(f"          (nao consegui reabrir o DOCX: {e})")
        return False


# ===================================================================
def main():
    print("\n" + "#" * 74)
    print("  TESTE LOCAL DA CORRECAO - gerador de apostilas SENAI")
    print("  (pipeline real | provider falso | sem API | sem internet)")
    print("#" * 74)

    a_ok, a_tot = nivel_a()
    b_ok, b_tot = nivel_b()

    total_ok, total = a_ok + b_ok, a_tot + b_tot
    print("\n" + "#" * 74)
    print(f"  RESULTADO FINAL: {total_ok}/{total} testes passaram")
    if total_ok == total:
        print("  OK - capitulos preenchidos em todos os cenarios.")
        print(f"  Abra os arquivos em ./{PASTA_OUT}/ para conferir visualmente.")
    else:
        print("  ATENCAO - alguns testes falharam; veja os detalhes acima.")
    print("#" * 74 + "\n")
    sys.exit(0 if total_ok == total else 1)


if __name__ == "__main__":
    main()
