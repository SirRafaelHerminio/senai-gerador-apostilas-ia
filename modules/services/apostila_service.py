"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         modules/services/apostila_service.py  (V1.8)                       ║
║         Orquestrador principal — pipeline modular JSON → DOCX              ║
╚══════════════════════════════════════════════════════════════════════════════╝

PIPELINE V1.8:
    1. CourseReader     → lê PDF da UC
    2. SAEPReader       → varre SAEP recursivo
    3. DocumentReader   → lê Prompt Mestre + Plano de Aula
    4. ContentExtractor → extrato pedagógico da UC
    5. PedagogicalPlanner → Gemini gera mapa de capítulos (JSON)
    6. ContentGenerator  → Gemini gera conteúdo de cada capítulo (JSON)
    7. DocxBuilder       → python-docx monta DOCX profissional
"""

import os
import time
import logging
from typing import Optional

from modules.readers.document_reader      import DocumentReader
from modules.readers.course_reader        import CourseReader
from modules.readers.saep_reader          import SAEPReader
from modules.analyzers.content_extractor  import ContentExtractor
from modules.services.pedagogical_planner import PedagogicalPlanner
from modules.services.content_generator   import ContentGenerator
from modules.exporters.docx_builder       import DocxBuilder
from providers.provider_manager           import ProviderManager
from modules.utils.response               import ok, erro, extrair

logger = logging.getLogger(__name__)


class ApostilaService:

    def __init__(self, config: dict):
        self.config = config

        self.doc_reader    = DocumentReader()
        self.course_reader = CourseReader(
            pasta_cursos=config.get("CURSOS_FOLDER", "Cursos"))
        self.saep_reader   = SAEPReader(
            pasta_saep=config.get("SAEP_FOLDER", "SAEP"))
        self.extractor     = ContentExtractor()
        self.docx_builder  = DocxBuilder(
            pasta_output=config.get("OUTPUT_FOLDER", "output"))
        self.provider_mgr  = ProviderManager(
            provider_nome=config.get("AI_PROVIDER", "gemini"))
        self.prompt_mestre_path = config.get(
            "PROMPT_MESTRE_PATH", "Prompt Apostilas SENAI.docx")

    def gerar(
        self,
        curso:         str,
        uc:            str,
        bloco_aula:    str,
        caminho_plano: str = "",
        observacoes:   Optional[str] = None,
        professor:     Optional[str] = None,
    ) -> dict:
        t0     = time.time()
        avisos = []

        logger.info(f"\n{'═'*58}\n  PIPELINE V1.8 | {curso} | {uc} | {bloco_aula}\n{'═'*58}")

        try:
            # ── 1. Lê PDF da UC ───────────────────────────────────
            logger.info("▶ 1/7 — Lendo documento da UC...")
            res_uc = self.course_reader.ler_uc(curso, uc)
            if not res_uc.get("sucesso"):
                return erro(res_uc.get("erro", "Falha ao ler UC"))
            texto_uc  = extrair(res_uc, "texto",  "")
            curso_fmt = extrair(res_uc, "curso",  curso.replace("_", " "))
            uc_fmt    = extrair(res_uc, "uc",     uc.replace("_", " "))

            # ── 2. Lê SAEP ───────────────────────────────────────
            logger.info("▶ 2/7 — Varrendo SAEP...")
            res_saep = self.saep_reader.ler_curso(curso)
            arq_saep = extrair(res_saep, "total_arquivos", 0)
            if not extrair(res_saep, "tem_conteudo", False):
                avisos.append("Histórico SAEP não encontrado.")

            # ── 3. Lê Prompt Mestre + Plano ───────────────────────
            logger.info("▶ 3/7 — Lendo Prompt Mestre e Plano de Aula...")
            res_mestre   = self.doc_reader.ler(self.prompt_mestre_path)
            texto_mestre = extrair(res_mestre, "texto", "") if res_mestre.get("sucesso") else ""
            if not texto_mestre:
                avisos.append("Prompt Mestre não encontrado — usando instruções padrão.")

            texto_plano = ""
            if caminho_plano and os.path.exists(caminho_plano):
                res_plano   = self.doc_reader.ler(caminho_plano)
                texto_plano = extrair(res_plano, "texto", "") if res_plano.get("sucesso") else ""
            else:
                avisos.append("Plano de Aula não enviado.")

            # ── 4. Extração pedagógica ────────────────────────────
            logger.info("▶ 4/7 — Extraindo estrutura pedagógica...")
            res_ext    = self.extractor.extrair_uc(texto_uc, bloco_aula)
            extrato_uc = extrair(res_ext, "resumo_formatado", texto_uc[:4000]) \
                         if res_ext.get("sucesso") else texto_uc[:4000]

            res_saep_ext = self.extractor.extrair_saep(res_saep)
            resumo_saep  = extrair(res_saep_ext, "resumo_formatado", "")

            # ── 5. Mapa pedagógico (Gemini → JSON) ─────────────────
            logger.info("▶ 5/7 — Gerando mapa pedagógico...")
            provider = self.provider_mgr.obter_provider()
            planner  = PedagogicalPlanner(provider)

            res_mapa = planner.gerar_mapa(
                curso       = curso_fmt,
                uc          = uc_fmt,
                bloco_aula  = bloco_aula,
                extrato_uc  = extrato_uc,
                resumo_saep = resumo_saep,
                observacoes = observacoes,
            )
            if not res_mapa.get("sucesso"):
                return erro(res_mapa.get("erro", "Falha no mapa pedagógico"))

            titulo_apostila = extrair(res_mapa, "titulo_apostila", bloco_aula)
            capitulos_mapa  = extrair(res_mapa, "capitulos", [])
            total_caps      = len(capitulos_mapa)

            logger.info(f"   Mapa: '{titulo_apostila}' | {total_caps} capítulos")

            # ── 6. Geração por capítulo (Gemini → JSON) ────────────
            logger.info(f"▶ 6/7 — Gerando {total_caps} capítulos...")
            gen_content       = ContentGenerator(provider)
            capitulos_gerados = []
            titulos_anteriores= []
            total_tokens_in   = 0
            total_tokens_out  = 0
            total_palavras    = 0
            tempos_caps       = []

            for cap_info in capitulos_mapa:
                num   = cap_info.get("numero", 1)
                t_cap = time.time()
                logger.info(f"   Capítulo {num}/{total_caps}: {cap_info.get('titulo','')}")

                res_cap = gen_content.gerar_capitulo_json(
                    capitulo           = cap_info,
                    total_capitulos    = total_caps,
                    curso              = curso_fmt,
                    uc                 = uc_fmt,
                    bloco_aula         = bloco_aula,
                    titulo_apostila    = titulo_apostila,
                    extrato_uc         = extrato_uc,
                    resumo_saep        = resumo_saep,
                    observacoes        = observacoes,
                    titulos_anteriores = titulos_anteriores,
                )

                if not res_cap.get("sucesso"):
                    avisos.append(f"Capítulo {num} com falha: {res_cap.get('erro','')}")
                    # Adiciona capítulo vazio para não travar o DOCX
                    capitulos_gerados.append({
                        "numero":  num,
                        "titulo":  cap_info.get("titulo", f"Capítulo {num}"),
                        "secoes":  [],
                        "saep_relevante": cap_info.get("saep_relevante", False),
                    })
                else:
                    dados_cap = extrair(res_cap, "dados", {})
                    # Injeta saep_relevante do mapa (mais confiável)
                    dados_cap["saep_relevante"] = cap_info.get("saep_relevante", False)
                    capitulos_gerados.append(dados_cap)
                    titulos_anteriores.append(cap_info.get("titulo", ""))
                    total_tokens_in  += extrair(res_cap, "tokens_entrada", 0)
                    total_tokens_out += extrair(res_cap, "tokens_saida",   0)
                    total_palavras   += extrair(res_cap, "palavras",       0)

                tempos_caps.append(round(time.time() - t_cap, 1))

            # ── 7. Monta DOCX ─────────────────────────────────────
            logger.info("▶ 7/7 — Construindo DOCX profissional...")
            tempo_total = round(time.time() - t0, 1)

            metricas_docx = {
                "total_capitulos": total_caps,
                "total_palavras":  total_palavras,
                "total_tokens_out":total_tokens_out,
                "tempo_total":     tempo_total,
            }

            res_docx = self.docx_builder.construir(
                titulo_apostila = titulo_apostila,
                curso           = curso_fmt,
                uc              = uc_fmt,
                bloco_aula      = bloco_aula,
                capitulos       = capitulos_gerados,
                metricas        = metricas_docx,
                professor       = professor,
            )

            if not res_docx.get("sucesso"):
                return erro(res_docx.get("erro", "Falha ao construir DOCX"))

            nome = extrair(res_docx, "nome_arquivo", "")
            logger.info(
                f"\n{'═'*58}\n"
                f"  DOCX V1.8 GERADO em {tempo_total}s\n"
                f"  Arquivo : {nome}\n"
                f"  Tamanho : {extrair(res_docx,'tamanho_legivel','')}\n"
                f"  Caps    : {total_caps} | Palavras: {total_palavras}\n"
                f"  Tokens  : in={total_tokens_in} out={total_tokens_out}\n"
                f"{'═'*58}"
            )

            return ok(
                apostila = {
                    "nome_arquivo": nome,
                    "caminho":      nome,
                    "tamanho":      extrair(res_docx, "tamanho_legivel"),
                    "data_geracao": extrair(res_docx, "data_geracao"),
                    "tipo":         "docx",
                },
                metricas = {
                    "tempo_segundos":   tempo_total,
                    "total_capitulos":  total_caps,
                    "total_palavras":   total_palavras,
                    "tokens_entrada":   total_tokens_in,
                    "tokens_saida":     total_tokens_out,
                    "tempos_capitulos": tempos_caps,
                    "provider":         "gemini",
                    "modelo":           self.provider_mgr.info().get("modelo",""),
                    "arquivos_saep":    arq_saep,
                },
                avisos = avisos,
            )

        except Exception as e:
            logger.error(f"Erro inesperado: {e}", exc_info=True)
            return erro(f"Erro interno: {str(e)}")

    def verificar_status(self) -> dict:
        resultado = self.provider_mgr.verificar_conexao()
        resultado["provider_info"] = self.provider_mgr.info()
        resultado["versao"]        = "V1.8"
        return resultado
