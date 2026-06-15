"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         modules/services/apostila_service.py  (V1.9)                       ║
║         Orquestrador com validação obrigatória de capítulos                ║
╚══════════════════════════════════════════════════════════════════════════════╝

MELHORIAS V1.8 → V1.9:
    - Validação obrigatória de cada capítulo antes de passar pro DOCX
    - Rejeita capítulos com título genérico, sem seções ou conteúdo mínimo
    - Log detalhado de cada capítulo aceito/rejeitado
    - Continua geração mesmo se um capítulo falhar
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

# Títulos genéricos que indicam capítulo vazio/placeholder
TITULOS_INVALIDOS = {
    "", "capítulo", "capitulo", "cap", "chapter",
    "capítulo 1", "capítulo 2", "capítulo 3",
    "capitulo 1", "capitulo 2", "capitulo 3",
    "sem título", "sem titulo", "título", "titulo",
}


def _validar_capitulo(dados: dict, indice: int) -> tuple[bool, str]:
    """
    Valida se um capítulo tem conteúdo real antes de enviar pro DOCX.
    Retorna (valido, motivo).
    """
    if not dados:
        return False, "Dados ausentes"

    titulo = dados.get("titulo", "").strip().lower()
    if titulo in TITULOS_INVALIDOS:
        return False, f"Título genérico/placeholder: '{titulo}'"

    secoes = dados.get("secoes", [])
    if not secoes:
        return False, "Sem seções"

    # Verifica conteúdo mínimo total
    total_chars = sum(
        len(s.get("conteudo", "")) for s in secoes
    )
    if total_chars < 50:
        return False, f"Conteúdo muito curto ({total_chars} chars)"

    # Verifica se pelo menos uma seção tem título real
    secoes_com_titulo = [s for s in secoes if s.get("titulo", "").strip()]
    if not secoes_com_titulo:
        return False, "Nenhuma seção com título"

    return True, "OK"


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

        logger.info(f"\n{'═'*58}\n  PIPELINE V1.9 | {curso} | {uc} | {bloco_aula}\n{'═'*58}")

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
                avisos.append("Prompt Mestre não encontrado.")

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

            # ── 5. Mapa pedagógico ────────────────────────────────
            logger.info("▶ 5/7 — Gerando mapa de capítulos...")
            provider = self.provider_mgr.obter_provider()
            planner  = PedagogicalPlanner(provider)
            res_mapa = planner.gerar_mapa(
                curso=curso_fmt, uc=uc_fmt, bloco_aula=bloco_aula,
                extrato_uc=extrato_uc, resumo_saep=resumo_saep,
                observacoes=observacoes,
            )
            if not res_mapa.get("sucesso"):
                return erro(res_mapa.get("erro", "Falha no mapa pedagógico"))

            titulo_apostila = extrair(res_mapa, "titulo_apostila", bloco_aula)
            capitulos_mapa  = extrair(res_mapa, "capitulos", [])
            total_caps      = len(capitulos_mapa)
            logger.info(f"   Mapa: '{titulo_apostila}' | {total_caps} capítulos")

            # ── 6. Geração capítulo por capítulo ──────────────────
            logger.info(f"▶ 6/7 — Gerando {total_caps} capítulos...")
            gen_content        = ContentGenerator(provider)
            capitulos_validos  = []
            capitulos_falhos   = []
            titulos_anteriores = []
            total_tokens_in    = 0
            total_tokens_out   = 0
            total_palavras     = 0

            for cap_info in capitulos_mapa:
                num   = cap_info.get("numero", 1)
                titulo_cap = cap_info.get("titulo", f"Capítulo {num}")
                logger.info(f"   [{num}/{total_caps}] {titulo_cap}")

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
                    msg = f"Cap {num} falhou na geração: {res_cap.get('erro','')}"
                    logger.error(msg)
                    avisos.append(msg)
                    capitulos_falhos.append(num)
                    continue

                # O capítulo vem DIRETO em res_cap["dados"] (com secoes, titulo, etc.).
                # Usar extrair(res_cap, "dados") procuraria uma chave "dados" DENTRO
                # do capítulo — que não existe — e devolvia {}, fazendo todo capítulo
                # ser rejeitado como "Título genérico: ''". Esse era o motivo de os
                # capítulos chegarem vazios ao DOCX.
                dados_cap = res_cap.get("dados", {})

                # ── VALIDAÇÃO OBRIGATÓRIA ─────────────────────────
                dados_cap["saep_relevante"] = cap_info.get("saep_relevante", False)
                valido, motivo = _validar_capitulo(dados_cap, num)

                if not valido:
                    msg = f"Cap {num} rejeitado — {motivo}"
                    logger.warning(msg)
                    avisos.append(f"⚠️ {msg}")
                    capitulos_falhos.append(num)
                    continue

                # Capítulo aceito
                capitulos_validos.append(dados_cap)
                titulos_anteriores.append(titulo_cap)
                total_tokens_in  += extrair(res_cap, "tokens_entrada", 0)
                total_tokens_out += extrair(res_cap, "tokens_saida",   0)
                total_palavras   += extrair(res_cap, "palavras",       0)

                logger.info(
                    f"   ✅ Cap {num} aceito | "
                    f"palavras={extrair(res_cap,'palavras',0)} | "
                    f"seções={len(dados_cap.get('secoes',[]))}"
                )

            # Verifica se temos capítulos suficientes
            if not capitulos_validos:
                return erro(
                    "Nenhum capítulo com conteúdo válido foi gerado. "
                    "Verifique os arquivos em debug_gemini/ para diagnóstico."
                )

            if capitulos_falhos:
                avisos.append(
                    f"Capítulos com falha: {capitulos_falhos}. "
                    f"Apostila gerada com {len(capitulos_validos)}/{total_caps} capítulos."
                )

            # ── 7. Monta DOCX ─────────────────────────────────────
            logger.info(
                f"▶ 7/7 — Construindo DOCX com "
                f"{len(capitulos_validos)} capítulos válidos..."
            )
            tempo_total   = round(time.time() - t0, 1)
            metricas_docx = {
                "total_capitulos": len(capitulos_validos),
                "total_palavras":  total_palavras,
                "total_tokens_out":total_tokens_out,
                "tempo_total":     tempo_total,
            }

            res_docx = self.docx_builder.construir(
                titulo_apostila = titulo_apostila,
                curso           = curso_fmt,
                uc              = uc_fmt,
                bloco_aula      = bloco_aula,
                capitulos       = capitulos_validos,
                metricas        = metricas_docx,
                professor       = professor,
            )

            if not res_docx.get("sucesso"):
                return erro(res_docx.get("erro", "Falha ao construir DOCX"))

            nome = extrair(res_docx, "nome_arquivo", "")
            logger.info(
                f"\n{'═'*58}\n"
                f"  DOCX V1.9 GERADO em {tempo_total}s\n"
                f"  Arquivo  : {nome}\n"
                f"  Caps OK  : {len(capitulos_validos)}/{total_caps}\n"
                f"  Palavras : {total_palavras}\n"
                f"  Tokens   : in={total_tokens_in} out={total_tokens_out}\n"
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
                    "tempo_segundos":    tempo_total,
                    "total_capitulos":   len(capitulos_validos),
                    "capitulos_falhos":  len(capitulos_falhos),
                    "total_palavras":    total_palavras,
                    "tokens_entrada":    total_tokens_in,
                    "tokens_saida":      total_tokens_out,
                    "provider":          "gemini",
                    "modelo":            self.provider_mgr.info().get("modelo",""),
                    "arquivos_saep":     arq_saep,
                },
                avisos = avisos,
            )

        except Exception as e:
            logger.error(f"Erro inesperado: {e}", exc_info=True)
            return erro(f"Erro interno: {str(e)}")

    def verificar_status(self) -> dict:
        resultado = self.provider_mgr.verificar_conexao()
        resultado["provider_info"] = self.provider_mgr.info()
        resultado["versao"]        = "V1.9"
        return resultado
