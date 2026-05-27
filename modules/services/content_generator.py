"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         modules/services/content_generator.py  (V1.8 — NOVO)               ║
║         Gemini gera JSON pedagógico puro — sem HTML, sem CSS               ║
╚══════════════════════════════════════════════════════════════════════════════╝

ARQUITETURA V1.8:
    Gemini → JSON pedagógico → DocxBuilder → DOCX final

Por que JSON em vez de HTML:
    - HTML/CSS consome ~40% dos tokens sem agregar conteúdo
    - JSON é compacto: a IA usa quase 100% dos tokens para ENSINAR
    - A formatação visual fica 100% no python-docx (determinístico)
    - Resultado: apostilas 2-3x mais densas com o mesmo limite de tokens

Estrutura do JSON por capítulo:
    {
      "numero": 1,
      "titulo": "Fundamentos de...",
      "subtitulo": "...",
      "introducao": "texto de introdução do capítulo",
      "secoes": [
        {
          "titulo": "título da seção",
          "conteudo": "explicação técnica extensa",
          "codigo": { "linguagem": "python", "titulo": "...", "codigo": "..." },
          "tabela": { "cabecalho": [...], "linhas": [[...], ...] },
          "boxes": [
            { "tipo": "atencao|dica|saep|pratica", "titulo": "...", "conteudo": "..." }
          ],
          "subsecoes": [
            { "titulo": "...", "conteudo": "...", "codigo": null, "boxes": [] }
          ]
        }
      ],
      "resumo_secao": "resumo do que foi ensinado",
      "saep_relevante": true,
      "conexao_proximo": "conexão com o próximo capítulo"
    }
"""

import json
import re
import logging
from typing import Optional
from modules.utils.response import ok, erro

logger = logging.getLogger(__name__)


PROMPT_CONTEUDO = """Você é um professor técnico sênior do SENAI gerando conteúdo pedagógico.

CONTEXTO:
Curso     : {curso}
UC        : {uc}
Apostila  : {titulo_apostila}
Bloco     : {bloco_aula}

CAPÍTULO: {numero}/{total} — {titulo}
Subtítulo : {subtitulo}
Tópicos   : {topicos}
Nível     : {profundidade}
{conexao_txt}

CONTEXTO PEDAGÓGICO:
{extrato_uc}

{saep_info}
{obs_info}

CAPÍTULOS ANTERIORES (não repita):
{anteriores_txt}

══════════════════════════════════════════════════════════════
MISSÃO: Gerar o CONTEÚDO COMPLETO e APROFUNDADO deste capítulo.

REGRAS DE PROFUNDIDADE:
- Cada seção deve ter mínimo 400 palavras de conteúdo real
- Explique o "porquê" de cada conceito, não apenas o "o quê"
- Para código: comente CADA linha que não é trivial
- Use dados e nomes realistas (nunca foo, bar, x, y)
- Progrida do simples para o complexo dentro de cada seção
- Analogias concretas sempre que ajudarem a fixar o conceito
- Erros comuns reais que iniciantes cometem (com explicação de por quê ocorrem)
- Aplicações em empresas reais (Nubank, iFood, Magazine Luiza, Mercado Livre, etc.)

RETORNE APENAS JSON VÁLIDO — sem markdown, sem texto antes ou depois:

{{
  "numero": {numero},
  "titulo": "{titulo}",
  "subtitulo": "{subtitulo}",
  "introducao": "Parágrafo de 100-150 palavras introduzindo o capítulo, conectando com o anterior e motivando o estudo do conteúdo. Sem texto motivacional vazio — contextualize tecnicamente.",
  "secoes": [
    {{
      "titulo": "Título da Seção 1",
      "conteudo": "Explicação técnica extensa e aprofundada. Mínimo 400 palavras. Explique fundamentos, contexto histórico quando relevante, variações, casos de uso. Use parágrafos bem desenvolvidos. Nunca seja superficial.",
      "codigo": {{
        "linguagem": "python",
        "titulo": "Descrição do que o código demonstra",
        "codigo": "# Comentário explicativo de cada linha relevante\\ncódigo aqui\\n# mais comentários"
      }},
      "tabela": {{
        "cabecalho": ["Coluna 1", "Coluna 2", "Coluna 3"],
        "linhas": [
          ["valor 1", "valor 2", "valor 3"],
          ["valor 4", "valor 5", "valor 6"]
        ]
      }},
      "boxes": [
        {{
          "tipo": "atencao",
          "titulo": "Atenção",
          "conteudo": "Erro comum real que iniciantes cometem, com explicação de por que acontece e como evitar."
        }},
        {{
          "tipo": "dica",
          "titulo": "Dica Profissional",
          "conteudo": "Conhecimento de profissional sênior sobre este tópico."
        }},
        {{
          "tipo": "saep",
          "titulo": "Relevância SAEP",
          "conteudo": "O que deste tópico costuma ser cobrado, como aparece, o que não errar."
        }},
        {{
          "tipo": "pratica",
          "titulo": "Contexto Profissional",
          "conteudo": "Como isso é usado em empresa real. Cite empresa, problema de negócio e solução."
        }}
      ],
      "subsecoes": [
        {{
          "titulo": "Subtópico importante",
          "conteudo": "Aprofundamento de um aspecto específico. Mínimo 200 palavras.",
          "codigo": null,
          "boxes": []
        }}
      ]
    }}
  ],
  "resumo_secao": "Síntese em 80-120 palavras do que foi ensinado neste capítulo. Objetivo e direto.",
  "saep_relevante": {saep_bool},
  "conexao_proximo": "Uma frase conectando este capítulo com o próximo (ou null se for o último)."
}}

IMPORTANTE:
- Use TODO o espaço disponível — gere o máximo de conteúdo útil possível
- código pode ser null se não aplicável ao tópico
- tabela pode ser null se não houver comparação
- boxes: inclua apenas os tipos relevantes para cada seção (não force todos)
- subsecoes: inclua apenas se o tópico tiver subdivisões naturais
- Nunca use placeholders como [inserir aqui] ou [exemplo]
- JSON deve ser valido — escape aspas internas com barra invertida"""


class ContentGenerator:
    """
    Usa o Gemini para gerar conteúdo pedagógico em JSON puro.
    Sem HTML, sem CSS — apenas conteúdo.
    """

    def __init__(self, provider):
        self.provider = provider

    def gerar_capitulo_json(
        self,
        capitulo:           dict,
        total_capitulos:    int,
        curso:              str,
        uc:                 str,
        bloco_aula:         str,
        titulo_apostila:    str,
        extrato_uc:         str,
        resumo_saep:        str = "",
        observacoes:        Optional[str] = None,
        titulos_anteriores: list = None,
    ) -> dict:
        numero   = capitulo.get("numero", 1)
        titulo   = capitulo.get("titulo", f"Capítulo {numero}")
        subtit   = capitulo.get("subtitulo", "")
        topicos  = capitulo.get("topicos", [])
        profund  = capitulo.get("profundidade", "aplicacao")
        saep_rel = capitulo.get("saep_relevante", False)
        conexao  = capitulo.get("conexao_anterior")

        topicos_fmt  = "\n".join(f"  • {t}" for t in topicos) if topicos else "  • Conteúdo do capítulo"
        conexao_txt  = f"CONEXÃO COM CAPÍTULO ANTERIOR: {conexao}" if conexao else ""
        saep_info    = f"HISTÓRICO SAEP:\n{resumo_saep[:1500]}" if resumo_saep else ""
        obs_info     = f"INSTRUÇÃO DO PROFESSOR: {observacoes}" if observacoes else ""
        ant_txt      = ("Capítulos já cobertos (não repita): " +
                        " | ".join(titulos_anteriores)) if titulos_anteriores else "Primeiro capítulo."

        prompt = PROMPT_CONTEUDO.format(
            curso            = curso,
            uc               = uc,
            titulo_apostila  = titulo_apostila,
            bloco_aula       = bloco_aula,
            numero           = numero,
            total            = total_capitulos,
            titulo           = titulo,
            subtitulo        = subtit,
            topicos          = topicos_fmt,
            profundidade     = profund,
            saep_bool        = str(saep_rel).lower(),
            conexao_txt      = conexao_txt,
            extrato_uc       = extrato_uc[:3500],
            saep_info        = saep_info,
            obs_info         = obs_info,
            anteriores_txt   = ant_txt,
        )

        logger.info(f"ContentGenerator: gerando Capítulo {numero}/{total_capitulos} — {titulo}")

        res_ia = self.provider.gerar(prompt)
        if not res_ia.get("sucesso"):
            return erro(f"Falha Capítulo {numero}: {res_ia.get('erro', 'Erro desconhecido')}")

        conteudo_raw    = res_ia.get("conteudo", "")
        tokens_entrada  = res_ia.get("tokens_entrada", 0)
        tokens_saida    = res_ia.get("tokens_saida",   0)
        tokens_total    = res_ia.get("tokens_usados",  0)
        palavras        = res_ia.get("palavras",        0)

        dados = self._parse_json(conteudo_raw, numero, titulo, subtit)

        if palavras == 0:
            palavras = self._contar_palavras(dados)

        logger.info(
            f"Capítulo {numero} gerado | "
            f"in={tokens_entrada} out={tokens_saida} | palavras={palavras}"
        )

        return ok(
            dados          = dados,
            tokens_entrada = tokens_entrada,
            tokens_saida   = tokens_saida,
            tokens_total   = tokens_total,
            palavras       = palavras,
            numero         = numero,
            titulo         = titulo,
        )

    def _parse_json(self, conteudo: str, numero: int, titulo: str, subtitulo: str) -> dict:
        try:
            texto = conteudo.strip()
            texto = re.sub(r"^```json\s*", "", texto, flags=re.IGNORECASE)
            texto = re.sub(r"^```\s*",     "", texto)
            texto = re.sub(r"\s*```$",     "", texto)
            match = re.search(r'\{[\s\S]*\}', texto)
            if match:
                texto = match.group(0)
            dados = json.loads(texto)
            dados.setdefault("numero",          numero)
            dados.setdefault("titulo",          titulo)
            dados.setdefault("subtitulo",       subtitulo)
            dados.setdefault("introducao",      "")
            dados.setdefault("secoes",          [])
            dados.setdefault("resumo_secao",    "")
            dados.setdefault("saep_relevante",  False)
            dados.setdefault("conexao_proximo", None)
            return dados
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Parse JSON falhou cap {numero}: {e}")
            return {
                "numero": numero, "titulo": titulo, "subtitulo": subtitulo,
                "introducao": "", "secoes": [{"titulo": "Conteúdo",
                "conteudo": conteudo[:8000], "codigo": None,
                "tabela": None, "boxes": [], "subsecoes": []}],
                "resumo_secao": "", "saep_relevante": False, "conexao_proximo": None,
            }

    def _contar_palavras(self, dados: dict) -> int:
        texto = " ".join([
            dados.get("introducao", ""),
            " ".join(s.get("conteudo", "") for s in dados.get("secoes", [])),
            dados.get("resumo_secao", ""),
        ])
        return len(texto.split())
