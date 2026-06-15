"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           modules/analyzers/content_extractor.py  (V1.3 — NOVO)            ║
║           Responsabilidade: Extração inteligente de conteúdo pedagógico     ║
╚══════════════════════════════════════════════════════════════════════════════╝

ESTE É O MÓDULO MAIS IMPORTANTE DA V1.3 PARA ECONOMIA DE TOKENS.

PROBLEMA DA V1.2:
    O sistema enviava o PDF inteiro para a IA (às vezes 50.000+ tokens).
    Isso esgotava a cota rapidamente e tornava as respostas lentas.

SOLUÇÃO V1.3 — EXTRAÇÃO ANTES DE ENVIAR:
    1. Lê o texto bruto do PDF (feito pelo DocumentReader)
    2. Extrai APENAS o que interessa pedagogicamente:
       - Competências e capacidades
       - Tópicos de conteúdo
       - Tecnologias e ferramentas
       - Critérios avaliativos
       - Situação de Aprendizagem
       - Objetivos de aprendizagem
    3. Retorna um dicionário estruturado (~2-5KB em vez de 50KB)
    4. O ContextBuilder usa ESSE dicionário — não o texto bruto

REDUÇÃO ESTIMADA DE TOKENS: 80-95% por requisição.

COMO FUNCIONA TECNICAMENTE:
    Usa expressões regulares (regex) e busca por palavras-chave
    para localizar seções relevantes no texto.
    
    No futuro (V2.0), isso será feito com embeddings + busca vetorial,
    que é mais preciso para textos com estrutura variável.
"""

import re
import logging
from modules.utils.response import ok, erro

logger = logging.getLogger(__name__)

# ─── Padrões para identificar seções no documento ────────────────────────────
# Cada lista contém variações de como o SENAI nomeia aquele conceito

PADROES_COMPETENCIAS = [
    r"competência[s]?\s*[:\-–]?\s*(.+?)(?=\n\n|\ncapacidade|\nhabilidade|$)",
    r"competência[s]?\s+desenvolvida[s]?\s*[:\-–]?\s*(.+?)(?=\n\n|$)",
]

PADROES_CAPACIDADES = [
    r"capacidade[s]?\s*[:\-–]?\s*(.+?)(?=\n\n|\ncompetência|$)",
    r"capacidade[s]?\s+técnica[s]?\s*[:\-–]?\s*(.+?)(?=\n\n|$)",
    r"capacidade[s]?\s+socioemocional[ais]?\s*[:\-–]?\s*(.+?)(?=\n\n|$)",
]

PADROES_SITUACAO_APRENDIZAGEM = [
    r"situação\s+de\s+aprendizagem\s*[:\-–]?\s*(.+?)(?=\n\n|\ncompetência|$)",
    r"SA\s*[:\-–]\s*(.+?)(?=\n\n|$)",
]

PADROES_OBJETIVOS = [
    r"objetivo[s]?\s*[:\-–]?\s*(.+?)(?=\n\n|\ncompetência|$)",
    r"objetivo[s]?\s+de\s+aprendizagem\s*[:\-–]?\s*(.+?)(?=\n\n|$)",
]

PADROES_CRITERIOS = [
    r"critério[s]?\s*[:\-–]?\s*(.+?)(?=\n\n|$)",
    r"critério[s]?\s+de\s+avaliação\s*[:\-–]?\s*(.+?)(?=\n\n|$)",
    r"indicador[es]?\s*[:\-–]?\s*(.+?)(?=\n\n|$)",
]

# Tecnologias e ferramentas comuns em cursos técnicos SENAI
# (expandido conforme os cursos forem sendo adicionados)
TECNOLOGIAS_CONHECIDAS = [
    # Desenvolvimento
    "python", "javascript", "typescript", "java", "c#", "php", "ruby", "go",
    "html", "css", "react", "vue", "angular", "node", "django", "flask",
    "fastapi", "spring", "laravel",
    # Banco de dados
    "mysql", "postgresql", "mongodb", "sqlite", "oracle", "redis", "sql",
    # Infraestrutura
    "docker", "kubernetes", "git", "github", "gitlab", "linux", "aws", "azure",
    # Eletrônica / Mecatrônica
    "arduino", "plc", "clp", "scada", "autocad", "solidworks", "catia",
    "inversores", "sensores", "atuadores",
    # Jogos
    "unity", "unreal", "godot", "blender", "c++", "lua",
    # Redes
    "tcp/ip", "cisco", "mikrotik", "vlan", "firewall",
]

# Verbos de Bloom — identificam nível cognitivo exigido
VERBOS_BLOOM = {
    "lembrar":    ["identificar", "reconhecer", "listar", "nomear", "definir"],
    "entender":   ["explicar", "descrever", "interpretar", "resumir", "classificar"],
    "aplicar":    ["aplicar", "executar", "utilizar", "resolver", "implementar", "usar"],
    "analisar":   ["analisar", "comparar", "diferenciar", "examinar", "investigar"],
    "avaliar":    ["avaliar", "julgar", "validar", "testar", "justificar", "criticar"],
    "criar":      ["criar", "desenvolver", "projetar", "construir", "planejar", "arquitetar"],
}


class ContentExtractor:
    """
    Extrai informações pedagógicas estruturadas de um texto bruto de UC.

    Em vez de jogar 50KB de PDF na IA, extraímos ~2KB de informação relevante.

    Uso:
        extractor = ContentExtractor()
        resultado = extractor.extrair_uc(texto_bruto_do_pdf)

        if resultado["sucesso"]:
            dados = resultado["dados"]
            # dados["competencias"], dados["topicos"], dados["tecnologias"]...
    """

    def extrair_uc(self, texto: str, bloco_aula: str = "") -> dict:
        """
        Extrai estrutura pedagógica completa de um documento de UC.

        Args:
            texto:      Texto bruto extraído do PDF da UC
            bloco_aula: Bloco/aula selecionado (para filtrar tópicos relevantes)

        Returns:
            ok(
                competencias, capacidades, situacao_aprendizagem,
                objetivos, criterios, tecnologias,
                nivel_bloom, topicos, resumo_formatado
            )
        """
        if not texto or not texto.strip():
            return erro("Texto da UC vazio — não foi possível extrair conteúdo")

        texto_lower = texto.lower()

        # ── Extrai cada categoria ─────────────────────────────────────────────
        competencias  = self._extrair_por_padroes(texto, PADROES_COMPETENCIAS)
        capacidades   = self._extrair_por_padroes(texto, PADROES_CAPACIDADES)
        sa            = self._extrair_por_padroes(texto, PADROES_SITUACAO_APRENDIZAGEM)
        objetivos     = self._extrair_por_padroes(texto, PADROES_OBJETIVOS)
        criterios     = self._extrair_por_padroes(texto, PADROES_CRITERIOS)
        tecnologias   = self._extrair_tecnologias(texto_lower)
        nivel_bloom   = self._identificar_bloom(texto_lower)
        topicos       = self._extrair_topicos(texto, bloco_aula)

        # ── Monta resumo formatado para o ContextBuilder ─────────────────────
        resumo = self._montar_resumo(
            competencias, capacidades, sa, objetivos,
            criterios, tecnologias, nivel_bloom, topicos, bloco_aula
        )

        logger.info(
            f"Extração UC | "
            f"Competências: {len(competencias)} | "
            f"Capacidades: {len(capacidades)} | "
            f"Tecnologias: {len(tecnologias)} | "
            f"Tópicos: {len(topicos)} | "
            f"Bloom: {nivel_bloom}"
        )

        return ok(
            competencias         = competencias,
            capacidades          = capacidades,
            situacao_aprendizagem = sa,
            objetivos            = objetivos,
            criterios            = criterios,
            tecnologias          = tecnologias,
            nivel_bloom          = nivel_bloom,
            topicos              = topicos,
            resumo_formatado     = resumo,
        )

    def extrair_saep(self, dados_saep: dict) -> dict:
        """
        Extrai padrões recorrentes do conteúdo SAEP consolidado.

        Args:
            dados_saep: Resultado retornado pelo SAEPReader.ler_curso()

        Returns:
            ok(
                recorrencias, competencias_cobradas,
                tecnologias_cobradas, formatos_avaliacao,
                peso_diagnostica, peso_pratica,
                resumo_formatado
            )
        """
        if not dados_saep or not dados_saep.get("sucesso"):
            return ok(
                recorrencias         = [],
                competencias_cobradas = [],
                tecnologias_cobradas  = [],
                formatos_avaliacao    = [],
                resumo_formatado      = "[SAEP não disponível]",
            )

        d = dados_saep.get("dados", {})
        tem_conteudo = d.get("tem_conteudo", False)

        if not tem_conteudo:
            return ok(
                recorrencias         = [],
                competencias_cobradas = [],
                tecnologias_cobradas  = [],
                formatos_avaliacao    = [],
                resumo_formatado      = "[Histórico SAEP não encontrado para este curso]",
            )

        # Textos separados por tipo
        texto_diag   = d.get("diagnostica", {}).get("texto", "")
        texto_prat   = d.get("pratica",     {}).get("texto", "")
        texto_total  = d.get("consolidado", "")
        texto_lower  = texto_total.lower()

        tecnologias_cobradas  = self._extrair_tecnologias(texto_lower)
        competencias_cobradas = self._extrair_competencias_saep(texto_lower)
        formatos              = self._extrair_formatos_avaliacao(texto_lower)
        recorrencias          = self._extrair_recorrencias(texto_lower)

        resumo = self._montar_resumo_saep(
            recorrencias, competencias_cobradas,
            tecnologias_cobradas, formatos,
            ciclos=d.get("ciclos_encontrados", []),
            total_arq=d.get("total_arquivos", 0),
        )

        return ok(
            recorrencias          = recorrencias,
            competencias_cobradas = competencias_cobradas,
            tecnologias_cobradas  = tecnologias_cobradas,
            formatos_avaliacao    = formatos,
            ciclos                = d.get("ciclos_encontrados", []),
            resumo_formatado      = resumo,
        )

    # ─── Extratores privados ──────────────────────────────────────────────────

    def _extrair_por_padroes(self, texto: str, padroes: list) -> list:
        """
        Tenta cada padrão regex e coleta os resultados únicos.
        Limpa o texto e remove itens muito curtos.
        """
        encontrados = []
        for padrao in padroes:
            try:
                matches = re.findall(padrao, texto, re.IGNORECASE | re.DOTALL)
                for m in matches:
                    # Limpa e divide por linhas/bullets
                    partes = re.split(r"[\n•\-–]", m)
                    for parte in partes:
                        parte_limpa = parte.strip()
                        if len(parte_limpa) > 10:
                            encontrados.append(parte_limpa)
            except re.error:
                continue

        # Remove duplicatas mantendo ordem
        return list(dict.fromkeys(encontrados))[:15]

    def _extrair_tecnologias(self, texto_lower: str) -> list:
        """Identifica tecnologias mencionadas no documento."""
        return [t for t in TECNOLOGIAS_CONHECIDAS if t in texto_lower]

    def _identificar_bloom(self, texto_lower: str) -> str:
        """
        Identifica o nível mais alto da Taxonomia de Bloom encontrado.
        A ordem da lista já é do mais alto para o mais baixo.
        """
        for nivel, verbos in reversed(list(VERBOS_BLOOM.items())):
            if any(v in texto_lower for v in verbos):
                return nivel
        return "aplicar"   # Padrão razoável para cursos técnicos

    def _extrair_topicos(self, texto: str, bloco_aula: str) -> list:
        """
        Extrai tópicos de conteúdo do documento.
        Prioriza tópicos relacionados ao bloco/aula selecionado.
        """
        topicos = []

        # Busca linhas que parecem ser tópicos (curtas, sem pontuação final)
        linhas = texto.split("\n")
        for linha in linhas:
            linha = linha.strip()
            # Heurística: linha entre 10-80 chars sem ponto final = provável tópico
            if (10 < len(linha) < 80
                    and not linha.endswith(".")
                    and not linha.endswith(":")
                    and not linha[0].isdigit()
                    and linha[0].isupper()):
                topicos.append(linha)

        # Filtra por relevância ao bloco_aula se fornecido
        if bloco_aula and topicos:
            palavras_chave = set(bloco_aula.lower().split())
            relevantes     = [t for t in topicos
                              if any(p in t.lower() for p in palavras_chave if len(p) > 3)]
            if relevantes:
                return relevantes[:12]

        return list(dict.fromkeys(topicos))[:12]

    def _extrair_competencias_saep(self, texto_lower: str) -> list:
        """Extrai competências citadas nos documentos SAEP."""
        padroes = [
            r"competência\s+\d+[:\-–]?\s*(.{10,80})",
            r"competência[s]?\s*avaliada[s]?\s*[:\-–]\s*(.{10,80})",
        ]
        resultados = []
        for p in padroes:
            try:
                matches = re.findall(p, texto_lower, re.IGNORECASE)
                resultados.extend(m.strip() for m in matches if len(m.strip()) > 10)
            except re.error:
                pass
        return list(dict.fromkeys(resultados))[:8]

    def _extrair_formatos_avaliacao(self, texto_lower: str) -> list:
        """Identifica formatos de avaliação mencionados no SAEP."""
        formatos = [
            "prova escrita", "avaliação prática", "checklist", "projeto",
            "portfólio", "seminário", "simulação", "entrega", "banca",
            "questão dissertativa", "múltipla escolha", "situação-problema",
        ]
        return [f for f in formatos if f in texto_lower]

    def _extrair_recorrencias(self, texto_lower: str) -> list:
        """
        Identifica tópicos recorrentes no SAEP baseado em frequência de palavras
        técnicas significativas (stop words removidas manualmente).
        """
        # Remove palavras comuns
        stop_words = {
            "que", "para", "com", "uma", "como", "por", "mais", "deve", "ser",
            "dos", "das", "não", "são", "suas", "seu", "sua", "nos", "nas",
            "este", "esta", "estes", "estas", "foi", "tem", "ter",
        }
        palavras = re.findall(r"\b[a-záéíóúâêîôûãõç]{5,}\b", texto_lower)
        frequencias = {}
        for p in palavras:
            if p not in stop_words:
                frequencias[p] = frequencias.get(p, 0) + 1

        # Retorna as 10 palavras mais frequentes (prováveis tópicos recorrentes)
        ordenadas = sorted(frequencias.items(), key=lambda x: x[1], reverse=True)
        return [p for p, _ in ordenadas[:10]]

    # ─── Formatadores de resumo ───────────────────────────────────────────────

    def _montar_resumo(
        self, competencias, capacidades, sa, objetivos,
        criterios, tecnologias, nivel_bloom, topicos, bloco_aula
    ) -> str:
        """
        Monta um resumo estruturado e compacto para o ContextBuilder.
        Este texto substitui o PDF bruto no prompt — muito menor e mais focado.
        """
        partes = ["═══ CONTEXTO PEDAGÓGICO DA UC (EXTRAÍDO) ═══\n"]

        if bloco_aula:
            partes.append(f"FOCO: {bloco_aula}\n")

        if competencias:
            partes.append("COMPETÊNCIAS:")
            partes.extend(f"  • {c}" for c in competencias[:5])
            partes.append("")

        if capacidades:
            partes.append("CAPACIDADES:")
            partes.extend(f"  • {c}" for c in capacidades[:8])
            partes.append("")

        if sa:
            partes.append("SITUAÇÃO DE APRENDIZAGEM:")
            partes.extend(f"  {s}" for s in sa[:2])
            partes.append("")

        if objetivos:
            partes.append("OBJETIVOS:")
            partes.extend(f"  • {o}" for o in objetivos[:5])
            partes.append("")

        if topicos:
            partes.append("TÓPICOS DE CONTEÚDO:")
            partes.extend(f"  • {t}" for t in topicos[:10])
            partes.append("")

        if tecnologias:
            partes.append(f"TECNOLOGIAS: {', '.join(tecnologias)}\n")

        if nivel_bloom:
            partes.append(f"NÍVEL COGNITIVO (BLOOM): {nivel_bloom.upper()}\n")

        if criterios:
            partes.append("CRITÉRIOS AVALIATIVOS:")
            partes.extend(f"  • {c}" for c in criterios[:4])

        return "\n".join(partes)

    def _montar_resumo_saep(
        self, recorrencias, competencias, tecnologias,
        formatos, ciclos, total_arq
    ) -> str:
        """Monta resumo compacto do SAEP para o prompt."""
        partes = ["═══ ANÁLISE SAEP (HISTÓRICO) ═══\n"]

        if ciclos:
            partes.append(f"Ciclos analisados: {', '.join(ciclos)}")
        if total_arq:
            partes.append(f"Documentos lidos: {total_arq}\n")

        if competencias:
            partes.append("COMPETÊNCIAS COBRADAS NO SAEP:")
            partes.extend(f"  • {c}" for c in competencias[:6])
            partes.append("")

        if tecnologias:
            partes.append(f"TECNOLOGIAS AVALIADAS: {', '.join(tecnologias[:8])}\n")

        if recorrencias:
            partes.append(f"TÓPICOS RECORRENTES: {', '.join(recorrencias[:8])}\n")

        if formatos:
            partes.append(f"FORMATOS DE AVALIAÇÃO: {', '.join(formatos)}\n")

        partes.append(
            "INSTRUÇÃO: Reforce os tópicos recorrentes. "
            "Adicione alertas SAEP nos conteúdos de alta relevância avaliativa."
        )

        return "\n".join(partes)
