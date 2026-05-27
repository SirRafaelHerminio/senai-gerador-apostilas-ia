"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         modules/services/pedagogical_planner.py  (V1.7 — NOVO)             ║
║         Responsabilidade: Gerar o mapa pedagógico do bloco                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

ETAPA 1 DA PIPELINE V1.7:

Antes de gerar qualquer apostila, o sistema faz uma primeira chamada à IA
pedindo apenas o MAPA PEDAGÓGICO — a estrutura de capítulos e subcapítulos
do bloco, na ordem ideal de ensino.

Por que isso resolve o problema da geração monolítica:
    - A IA não precisa mais decidir estrutura E escrever conteúdo ao mesmo tempo
    - Cada capítulo recebe 100% da atenção e tokens da chamada seguinte
    - A progressão pedagógica é planejada ANTES de escrever
    - O professor pode ver e validar a estrutura antes da geração

O mapa retorna um JSON estruturado:
    {
        "titulo_apostila": "...",
        "capitulos": [
            {
                "numero": 1,
                "titulo": "...",
                "subtitulo": "...",
                "topicos": ["tópico 1", "tópico 2"],
                "profundidade": "fundamentos|aplicacao|avancado",
                "conexao_anterior": "...",
                "saep_relevante": true|false
            },
            ...
        ]
    }
"""

import json
import logging
import re
from typing import Optional
from modules.utils.response import ok, erro

logger = logging.getLogger(__name__)

# Prompt compacto para geração do mapa — usa poucos tokens intencionalmente
PROMPT_MAPA = """Você é um especialista em planejamento pedagógico do SENAI.

CONTEXTO:
Curso     : {curso}
UC        : {uc}
Bloco/Aula: {bloco_aula}

EXTRATO PEDAGÓGICO DA UC:
{extrato_uc}

{saep_info}
{obs_info}

TAREFA:
Gere o mapa pedagógico deste bloco dividido em capítulos para uma apostila técnica.

REGRAS DO MAPA:
- Divida o conteúdo em 4 a 7 capítulos (dependendo da complexidade do bloco)
- Cada capítulo deve ser autossuficiente mas conectado ao anterior
- A progressão deve ir do mais fundamental ao mais avançado
- Identifique quais capítulos têm maior relevância para o SAEP
- Cada capítulo deve ter tópicos específicos que serão aprofundados

RETORNE APENAS JSON VÁLIDO — sem markdown, sem texto antes ou depois:

{{
  "titulo_apostila": "título descritivo da apostila",
  "estimativa_capitulos": N,
  "capitulos": [
    {{
      "numero": 1,
      "titulo": "título do capítulo",
      "subtitulo": "descrição em uma frase do que será ensinado",
      "topicos": ["tópico específico 1", "tópico específico 2", "tópico específico 3"],
      "profundidade": "fundamentos",
      "conexao_anterior": null,
      "saep_relevante": true
    }},
    {{
      "numero": 2,
      "titulo": "título do capítulo",
      "subtitulo": "descrição em uma frase",
      "topicos": ["tópico 1", "tópico 2"],
      "profundidade": "aplicacao",
      "conexao_anterior": "Breve conexão com o capítulo anterior em uma frase",
      "saep_relevante": false
    }}
  ]
}}"""


class PedagogicalPlanner:
    """
    Gera o mapa pedagógico do bloco antes da geração dos capítulos.

    Uso:
        planner = PedagogicalPlanner(provider)
        mapa = planner.gerar_mapa(curso, uc, bloco_aula, extrato_uc, resumo_saep, obs)

        if mapa["sucesso"]:
            capitulos = mapa["dados"]["capitulos"]
    """

    def __init__(self, provider):
        """
        Args:
            provider: instância de BaseProvider (Gemini, Groq, etc.)
        """
        self.provider = provider

    def gerar_mapa(
        self,
        curso:       str,
        uc:          str,
        bloco_aula:  str,
        extrato_uc:  str,
        resumo_saep: str = "",
        observacoes: Optional[str] = None,
    ) -> dict:
        """
        Faz a primeira chamada à IA para gerar apenas o mapa pedagógico.

        Esta chamada usa poucos tokens — o objetivo é estrutura, não conteúdo.
        O mapa resultante guia todas as chamadas seguintes.

        Returns:
            ok(
                titulo_apostila = "...",
                capitulos = [...],
                total_capitulos = N,
                mapa_raw = {...}   # JSON original
            )
            erro("mensagem")
        """
        logger.info("PedagogicalPlanner: gerando mapa pedagógico...")

        # Monta o prompt do mapa (compacto — propositalmente)
        saep_info = f"HISTÓRICO SAEP:\n{resumo_saep[:1500]}" if resumo_saep else ""
        obs_info  = f"OBSERVAÇÕES DO PROFESSOR:\n{observacoes}" if observacoes else ""

        prompt = PROMPT_MAPA.format(
            curso       = curso,
            uc          = uc,
            bloco_aula  = bloco_aula,
            extrato_uc  = extrato_uc[:3000],  # Limitado — só para contexto
            saep_info   = saep_info,
            obs_info    = obs_info,
        )

        # Chama a IA com limite menor de tokens (só precisa do JSON)
        resultado_ia = self.provider.gerar(prompt)

        if not resultado_ia.get("sucesso"):
            logger.error(f"Falha ao gerar mapa pedagógico: {resultado_ia.get('erro')}")
            return erro(f"Falha ao gerar mapa pedagógico: {resultado_ia.get('erro', 'Erro desconhecido')}")

        conteudo = resultado_ia.get("conteudo", "")

        # Faz parse do JSON retornado
        mapa = self._parse_mapa(conteudo)
        if not mapa:
            logger.warning("Mapa inválido — usando estrutura padrão de fallback")
            mapa = self._mapa_fallback(bloco_aula)

        capitulos = mapa.get("capitulos", [])

        logger.info(
            f"Mapa gerado: '{mapa.get('titulo_apostila', '')}' | "
            f"{len(capitulos)} capítulos"
        )

        return ok(
            titulo_apostila = mapa.get("titulo_apostila", bloco_aula),
            capitulos       = capitulos,
            total_capitulos = len(capitulos),
            mapa_raw        = mapa,
        )

    def _parse_mapa(self, conteudo: str) -> Optional[dict]:
        """
        Faz parse do JSON retornado pela IA.
        Trata casos onde a IA adiciona markdown ou texto extra.
        """
        try:
            # Remove markdown se presente
            texto = conteudo.strip()
            texto = re.sub(r"^```json\s*", "", texto, flags=re.IGNORECASE)
            texto = re.sub(r"^```\s*",     "", texto)
            texto = re.sub(r"\s*```$",     "", texto)

            # Tenta encontrar o JSON mesmo se houver texto antes/depois
            match = re.search(r'\{[\s\S]*\}', texto)
            if match:
                texto = match.group(0)

            mapa = json.loads(texto)

            # Valida estrutura mínima
            if "capitulos" not in mapa or not isinstance(mapa["capitulos"], list):
                return None
            if len(mapa["capitulos"]) == 0:
                return None

            # Garante campos obrigatórios em cada capítulo
            for i, cap in enumerate(mapa["capitulos"]):
                cap["numero"]           = cap.get("numero", i + 1)
                cap["titulo"]           = cap.get("titulo", f"Capítulo {i+1}")
                cap["subtitulo"]        = cap.get("subtitulo", "")
                cap["topicos"]          = cap.get("topicos", [])
                cap["profundidade"]     = cap.get("profundidade", "aplicacao")
                cap["conexao_anterior"] = cap.get("conexao_anterior", None)
                cap["saep_relevante"]   = cap.get("saep_relevante", False)

            return mapa

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Falha ao fazer parse do mapa: {e}\nConteúdo: {conteudo[:500]}")
            return None

    def _mapa_fallback(self, bloco_aula: str) -> dict:
        """
        Estrutura padrão usada quando a IA não retorna um mapa válido.
        Garante que a pipeline não trave mesmo em caso de falha do planejamento.
        """
        return {
            "titulo_apostila": bloco_aula,
            "estimativa_capitulos": 4,
            "capitulos": [
                {
                    "numero": 1,
                    "titulo": "Fundamentos e Conceitos Essenciais",
                    "subtitulo": "Base teórica e definições do bloco",
                    "topicos": ["Conceitos fundamentais", "Terminologia técnica", "Contexto de aplicação"],
                    "profundidade": "fundamentos",
                    "conexao_anterior": None,
                    "saep_relevante": True,
                },
                {
                    "numero": 2,
                    "titulo": "Aplicação Técnica e Implementação",
                    "subtitulo": "Demonstração prática com exemplos reais",
                    "topicos": ["Sintaxe e uso", "Exemplos comentados", "Variações e casos especiais"],
                    "profundidade": "aplicacao",
                    "conexao_anterior": "Com os fundamentos estabelecidos, avançamos para a aplicação prática.",
                    "saep_relevante": True,
                },
                {
                    "numero": 3,
                    "titulo": "Boas Práticas e Contexto Profissional",
                    "subtitulo": "Como o mercado aplica estes conceitos",
                    "topicos": ["Boas práticas", "Erros comuns", "Padrões de mercado"],
                    "profundidade": "avancado",
                    "conexao_anterior": "Aplicando o que aprendemos em cenários profissionais reais.",
                    "saep_relevante": False,
                },
                {
                    "numero": 4,
                    "titulo": "Consolidação e Preparação para Avaliação",
                    "subtitulo": "Revisão, SAEP e pontos críticos",
                    "topicos": ["Revisão dos principais conceitos", "Pontos frequentes no SAEP", "Checklist de aprendizagem"],
                    "profundidade": "avancado",
                    "conexao_anterior": "Consolidando todo o conhecimento adquirido neste bloco.",
                    "saep_relevante": True,
                },
            ],
        }
