"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         modules/services/content_generator.py  (V1.9.1)                    ║
║         Parse robusto — extrai conteúdo mesmo quando JSON falha            ║
╚══════════════════════════════════════════════════════════════════════════════╝

CORREÇÃO V1.9.1:
    Problema identificado via debug_gemini/:
    - Gemini retorna conteúdo RICO (16k chars) mas com texto antes do JSON
    - O regex antigo não encontrava o bloco JSON correto
    - Validação de 200 chars rejeitava o fallback com conteúdo bom

    Solução:
    1. Busca o ÚLTIMO { ... } completo — evita pegar fragmentos
    2. Se JSON falha, extrai seções diretamente do texto bruto
    3. Validação reduzida para 50 chars — não rejeita conteúdo real
    4. Salva debug sempre para diagnóstico
"""

import json
import re
import os
import logging
from datetime import datetime
from typing import Optional
from modules.utils.response import ok, erro

logger = logging.getLogger(__name__)

DEBUG_DIR = "debug_gemini"


def _salvar_debug(numero: int, titulo: str, conteudo_bruto: str):
    """Salva resposta bruta do Gemini para diagnóstico."""
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(DEBUG_DIR, f"cap{numero:02d}_{ts}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"=== Capítulo {numero}: {titulo} ===\n")
            f.write(f"=== Tamanho: {len(conteudo_bruto)} chars ===\n\n")
            f.write(conteudo_bruto)
        logger.info(f"Debug salvo: {path}")
    except Exception as e:
        logger.warning(f"Não foi possível salvar debug: {e}")


PROMPT_CAPITULO = """Você é um professor técnico sênior do SENAI.
Gere o Capítulo {numero} de {total} de forma COMPLETA.

CONTEXTO:
Curso: {curso} | UC: {uc} | Apostila: {titulo_apostila}
Bloco: {bloco_aula}

CAPÍTULO:
Número   : {numero}/{total}
Título   : {titulo}
Subtítulo: {subtitulo}
Tópicos  : {topicos}
Nível    : {profundidade}
{conexao_txt}

CONTEXTO PEDAGÓGICO:
{extrato_uc}
{saep_info}
{obs_info}

JÁ COBERTOS (não repita):
{anteriores_txt}

══════════════════════════════════════════════════════
INSTRUÇÕES:

Para cada tópico, gere:
1. Explicação técnica detalhada (mínimo 3 parágrafos)
2. Exemplo de código comentado linha a linha (se aplicável)
3. Box ATENÇÃO com erros comuns reais
4. Box BOAS PRÁTICAS com padrões de mercado
5. Aplicação em empresa real

Use dados realistas. Comente cada linha importante do código.

RETORNE APENAS O JSON ABAIXO — sem texto antes, sem texto depois, sem markdown:

{{
  "numero": {numero},
  "titulo": "{titulo}",
  "subtitulo": "{subtitulo}",
  "introducao": "Texto introdutório de 80-100 palavras contextualizando o capítulo.",
  "secoes": [
    {{
      "titulo": "Título da Primeira Seção",
      "conteudo": "Explicação técnica extensa com no mínimo 400 palavras. Desenvolva o conceito completamente, explique o porquê, mostre variações e casos de uso.",
      "codigo": {{
        "linguagem": "python",
        "titulo": "Descrição do exemplo",
        "codigo": "# Comentário de cada linha\\ncodigo = valor  # o que faz\\nprint(codigo)"
      }},
      "tabela": null,
      "boxes": [
        {{
          "tipo": "atencao",
          "titulo": "Atenção",
          "conteudo": "Erro real que iniciantes cometem e como corrigir."
        }},
        {{
          "tipo": "pratica",
          "titulo": "Contexto Profissional",
          "conteudo": "Como uma empresa real (ex: Nubank) usa este conceito."
        }}
      ],
      "subsecoes": []
    }},
    {{
      "titulo": "Título da Segunda Seção",
      "conteudo": "Segunda seção com mínimo 400 palavras aprofundando o tema.",
      "codigo": null,
      "tabela": {{
        "cabecalho": ["Coluna A", "Coluna B", "Coluna C"],
        "linhas": [["Valor 1A", "Valor 1B", "Valor 1C"], ["Valor 2A", "Valor 2B", "Valor 2C"]]
      }},
      "boxes": [
        {{
          "tipo": "dica",
          "titulo": "Dica Profissional",
          "conteudo": "Conhecimento de sênior que faz diferença na prática."
        }}
      ],
      "subsecoes": []
    }}
  ],
  "resumo_secao": "Síntese de 60-80 palavras do que foi ensinado.",
  "saep_relevante": {saep_bool},
  "conexao_proximo": "Uma frase conectando com o próximo capítulo."
}}"""


class ContentGenerator:
    """
    Gera conteúdo JSON pedagógico por capítulo.
    V1.9.1: parse robusto com extração de texto bruto como fallback.
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
        titulo   = capitulo.get("titulo",    f"Capítulo {numero}")
        subtit   = capitulo.get("subtitulo", "")
        topicos  = capitulo.get("topicos",   [])
        profund  = capitulo.get("profundidade", "aplicacao")
        saep_rel = capitulo.get("saep_relevante", False)
        conexao  = capitulo.get("conexao_anterior")

        topicos_fmt = "\n".join(f"  - {t}" for t in topicos) if topicos else "  - Conteúdo principal"
        conexao_txt = f"CONEXÃO ANTERIOR: {conexao}" if conexao else ""
        saep_info   = f"CONTEXTO SAEP:\n{resumo_saep[:1200]}" if resumo_saep else ""
        obs_info    = f"INSTRUÇÃO DO PROFESSOR: {observacoes}" if observacoes else ""
        ant_txt     = ("Já cobertos: " + " | ".join(titulos_anteriores)) if titulos_anteriores else "Primeiro capítulo."

        prompt = PROMPT_CAPITULO.format(
            curso           = curso,
            uc              = uc,
            titulo_apostila = titulo_apostila,
            bloco_aula      = bloco_aula,
            numero          = numero,
            total           = total_capitulos,
            titulo          = titulo,
            subtitulo       = subtit,
            topicos         = topicos_fmt,
            profundidade    = profund,
            saep_bool       = str(saep_rel).lower(),
            conexao_txt     = conexao_txt,
            extrato_uc      = extrato_uc[:3000],
            saep_info       = saep_info,
            obs_info        = obs_info,
            anteriores_txt  = ant_txt,
        )

        logger.info(f"ContentGenerator: Capítulo {numero}/{total_capitulos} — {titulo}")

        for tentativa in range(1, 3):
            res_ia = self.provider.gerar(prompt)
            if not res_ia.get("sucesso"):
                if tentativa == 2:
                    return erro(f"Falha Capítulo {numero}: {res_ia.get('erro','Erro')}")
                continue

            conteudo_bruto = res_ia.get("conteudo", "")

            # Salva sempre para debug
            _salvar_debug(numero, titulo, conteudo_bruto)

            # Tenta parse JSON — vários métodos
            dados, parse_ok = self._parse_robusto(conteudo_bruto, numero, titulo, subtit)

            # Valida minimamente
            valido, motivo = self._validar_minimo(dados)
            if valido:
                logger.info(f"Cap {numero} OK via {'JSON' if parse_ok else 'texto'}")
                break
            else:
                logger.warning(f"Cap {numero} tentativa {tentativa}: {motivo}")
                if tentativa == 2:
                    logger.warning(f"Cap {numero}: usando conteúdo parcial disponível")

        palavras       = self._contar_palavras(dados)
        tokens_entrada = res_ia.get("tokens_entrada", 0)
        tokens_saida   = res_ia.get("tokens_saida",   0)
        tokens_total   = res_ia.get("tokens_usados",  0)

        logger.info(
            f"Cap {numero} finalizado | palavras={palavras} | "
            f"seções={len(dados.get('secoes',[]))} | parse_ok={parse_ok}"
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

    # ─── Parse robusto ────────────────────────────────────────────────────────

    def _parse_robusto(self, conteudo: str, numero: int, titulo: str, subtitulo: str) -> tuple[dict, bool]:
        """
        Tenta extrair JSON com estratégias progressivas.
        Retorna (dados, parse_foi_json).

        Regra de ouro: só aceita como capítulo um objeto que REALMENTE tenha
        seções com conteúdo. Fragmentos internos (um box, uma seção solta) são
        rejeitados — eram a causa dos "capítulos vazios" em respostas truncadas.
        """
        texto = conteudo.strip()

        # Remove cercas markdown (caso o JSON mode não esteja ativo no provider)
        texto = re.sub(r"^```json\s*", "", texto, flags=re.IGNORECASE)
        texto = re.sub(r"^```\s*",     "", texto)
        texto = re.sub(r"\s*```$",     "", texto)

        # Estratégia 1: JSON direto
        try:
            dados = json.loads(texto)
            if self._eh_capitulo(dados):
                return self._normalizar(dados, numero, titulo, subtitulo), True
        except Exception:
            pass

        # Estratégia 2: raw_decode a partir do PRIMEIRO '{' — ignora texto
        # antes e depois do JSON, mas só aceita o objeto externo (o capítulo).
        try:
            inicio = texto.find("{")
            if inicio >= 0:
                dados, _ = json.JSONDecoder().raw_decode(texto[inicio:])
                if self._eh_capitulo(dados):
                    return self._normalizar(dados, numero, titulo, subtitulo), True
        except Exception:
            pass

        # Estratégia 3: JSON TRUNCADO — recupera o máximo de seções completas.
        # É o que salva o caso de a resposta do Gemini ser cortada por limite
        # de tokens (antes isso virava "capítulo vazio").
        dados = self._salvar_json_truncado(texto)
        if self._eh_capitulo(dados):
            logger.warning(
                f"Cap {numero}: JSON truncado — recuperadas "
                f"{len(dados.get('secoes', []))} seção(ões) completa(s)"
            )
            return self._normalizar(dados, numero, titulo, subtitulo), True

        # Estratégia 4: extrai seções do texto bruto (último recurso)
        return self._extrair_do_texto(texto, numero, titulo, subtitulo), False

    @staticmethod
    def _eh_capitulo(dados) -> bool:
        """
        Só considera capítulo válido um dict com lista de seções não-vazia
        e com algum conteúdo real. Bloqueia fragmentos internos do JSON.
        """
        if not isinstance(dados, dict):
            return False
        secoes = dados.get("secoes")
        if not isinstance(secoes, list) or not secoes:
            return False
        return any(
            (s.get("conteudo") or "").strip() or (s.get("titulo") or "").strip()
            for s in secoes if isinstance(s, dict)
        )

    def _salvar_json_truncado(self, texto: str):
        """
        Recupera o MAIOR objeto JSON válido de um JSON possivelmente truncado,
        preservando o máximo de elementos/seções completos.

        Faz um scanner que respeita strings e escapes, guarda o último ponto
        "seguro" (logo após fechar um valor com } ou ]) e, ao final, fecha as
        estruturas que ficaram abertas. Descarta o trecho incompleto do fim.
        """
        if not texto:
            return None
        inicio = texto.find("{")
        if inicio < 0:
            return None
        s = texto[inicio:]
        stack, in_str, esc = [], False, False
        cut, cut_stack = None, None
        for i, ch in enumerate(s):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if stack:
                    stack.pop()
                cut, cut_stack = i + 1, list(stack)   # ponto seguro: valor completo

        # Talvez já fosse decodificável inteiro (texto extra só no fim)
        try:
            obj, _ = json.JSONDecoder().raw_decode(s)
            return obj
        except Exception:
            pass

        if cut is None:
            return None

        fragmento = s[:cut]
        for ab in reversed(cut_stack):
            fragmento += "}" if ab == "{" else "]"
        try:
            return json.loads(fragmento)
        except Exception:
            return None

    def _extrair_do_texto(self, texto: str, numero: int, titulo: str, subtitulo: str) -> dict:
        """
        Fallback inteligente: extrai seções do texto bruto quando o JSON falha.
        Procura padrões de título e conteúdo no texto.
        """
        logger.info(f"Cap {numero}: usando extração de texto bruto ({len(texto)} chars)")

        # Limpa o texto mantendo conteúdo legível
        texto_limpo = re.sub(r'"(\w+)":\s*', '', texto)   # remove chaves JSON
        texto_limpo = re.sub(r'[{}\[\]]', ' ', texto_limpo)
        texto_limpo = re.sub(r'\\n', '\n', texto_limpo)
        texto_limpo = re.sub(r'\s{3,}', '\n\n', texto_limpo)
        texto_limpo = texto_limpo.strip()

        # Divide em blocos de ~2000 chars para simular seções
        blocos = []
        if len(texto_limpo) > 500:
            tamanho_bloco = max(1000, len(texto_limpo) // 3)
            partes = [texto_limpo[i:i+tamanho_bloco]
                      for i in range(0, len(texto_limpo), tamanho_bloco)]
            for i, parte in enumerate(partes[:3]):
                if len(parte.strip()) > 100:
                    blocos.append({
                        "titulo":    f"Parte {i+1} — {titulo}",
                        "conteudo":  parte.strip(),
                        "codigo":    None,
                        "tabela":    None,
                        "boxes":     [],
                        "subsecoes": [],
                    })

        if not blocos:
            blocos = [{
                "titulo":    titulo,
                "conteudo":  texto_limpo[:5000] if texto_limpo else "Conteúdo sendo preparado.",
                "codigo":    None,
                "tabela":    None,
                "boxes":     [],
                "subsecoes": [],
            }]

        return {
            "numero":          numero,
            "titulo":          titulo,
            "subtitulo":       subtitulo,
            "introducao":      "",
            "secoes":          blocos,
            "resumo_secao":    "",
            "saep_relevante":  False,
            "conexao_proximo": None,
        }

    def _normalizar(self, dados: dict, numero: int, titulo: str, subtitulo: str) -> dict:
        dados.setdefault("numero",          numero)
        dados.setdefault("titulo",          titulo)
        dados.setdefault("subtitulo",       subtitulo)
        dados.setdefault("introducao",      "")
        dados.setdefault("secoes",          [])
        dados.setdefault("resumo_secao",    "")
        dados.setdefault("saep_relevante",  False)
        dados.setdefault("conexao_proximo", None)
        for s in dados.get("secoes", []):
            s.setdefault("titulo",    "")
            s.setdefault("conteudo",  "")
            s.setdefault("codigo",    None)
            s.setdefault("tabela",    None)
            s.setdefault("boxes",     [])
            s.setdefault("subsecoes", [])
        return dados

    # ─── Validação mínima ─────────────────────────────────────────────────────

    def _validar_minimo(self, dados: dict) -> tuple[bool, str]:
        """Validação mínima — só rejeita se realmente não tiver nada."""
        if not dados.get("titulo", "").strip():
            return False, "Título ausente"
        secoes = dados.get("secoes", [])
        if not secoes:
            return False, "Sem seções"
        total = sum(len(s.get("conteudo", "")) for s in secoes)
        if total < 50:    # Mínimo muito baixo — só rejeita se vazio de verdade
            return False, f"Conteúdo muito curto ({total} chars)"
        return True, "OK"

    def _contar_palavras(self, dados: dict) -> int:
        partes = [dados.get("introducao", ""), dados.get("resumo_secao", "")]
        for s in dados.get("secoes", []):
            partes.append(s.get("conteudo", ""))
            for sub in s.get("subsecoes", []):
                partes.append(sub.get("conteudo", ""))
        return len(" ".join(partes).split())
