"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           modules/readers/saep_reader.py  (V1.8)                           ║
║           Responsabilidade: Leitura recursiva do histórico SAEP            ║
╚══════════════════════════════════════════════════════════════════════════════╝

MELHORIA V1.8 — Mapeamento inteligente de pasta SAEP:
    O sistema localiza automaticamente a pasta SAEP correta para o curso
    selecionado, normalizando nomes (acentos, espaços, maiúsculas).

    Exemplos de mapeamento automático:
        "Desenvolvimento de Sistemas"  → SAEP/Desenvolvimento_de_Sistemas/
        "Design Web"                   → SAEP/Design_Web/
        "Programação de Jogos Digitais"→ SAEP/Programacao_de_Jogos_Digitais/

    Se a pasta não existir: ignora SAEP silenciosamente, sem erro.

ESTRUTURA SUPORTADA:
    SAEP/
    └── Nome_do_Curso/
        ├── Diagnostica/
        │   └── 2024/
        │       ├── prova.pdf
        │       └── checklist.docx
        └── Pratica/
            └── 2024/
                └── projeto.pdf
"""

import os
import re
import unicodedata
import logging
from modules.readers.document_reader import DocumentReader
from modules.utils.response import ok, erro

logger = logging.getLogger(__name__)

EXTENSOES_VALIDAS = {".pdf", ".docx", ".txt"}
IDENTIFICADORES_DIAGNOSTICA = {"diagnostica", "diagnóstica", "diagnostico", "teorica", "teorico"}
IDENTIFICADORES_PRATICA      = {"pratica", "prática", "pratico", "projeto", "atividade"}


def normalizar_nome(nome: str) -> str:
    """
    Normaliza um nome para comparação com nomes de pastas.

    Processo:
        1. Remove acentos (NFD + filtra non-ASCII)
        2. Converte para minúsculas
        3. Substitui espaços e hífens por underscore
        4. Remove caracteres especiais

    Exemplos:
        "Desenvolvimento de Sistemas" → "desenvolvimento_de_sistemas"
        "Programação de Jogos"        → "programacao_de_jogos"
        "Design Web"                  → "design_web"
    """
    # Remove acentos via normalização Unicode NFD
    sem_acento = unicodedata.normalize("NFD", nome)
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")

    # Minúsculas
    resultado = sem_acento.lower()

    # Espaços e hífens → underscore
    resultado = re.sub(r"[\s\-]+", "_", resultado)

    # Remove caracteres não alfanuméricos (exceto underscore)
    resultado = re.sub(r"[^\w]", "", resultado)

    return resultado


def localizar_pasta_saep(pasta_saep_raiz: str, nome_curso: str) -> str | None:
    """
    Localiza automaticamente a pasta SAEP correta para um curso.

    Estratégia de busca (em ordem de prioridade):
        1. Correspondência exata (nome_curso == nome_pasta)
        2. Correspondência normalizada (ignora acentos, case, espaços)
        3. Correspondência parcial (nome_curso contém ou está contido na pasta)

    Args:
        pasta_saep_raiz: Caminho raiz da pasta SAEP (ex: "SAEP")
        nome_curso:      Nome do curso como vem do formulário

    Returns:
        Caminho completo da pasta SAEP do curso, ou None se não encontrada
    """
    if not os.path.exists(pasta_saep_raiz):
        return None

    # Normaliza o nome do curso para comparação
    curso_norm = normalizar_nome(nome_curso)

    try:
        pastas_disponiveis = [
            d for d in os.listdir(pasta_saep_raiz)
            if os.path.isdir(os.path.join(pasta_saep_raiz, d))
            and not d.startswith(".")
        ]
    except PermissionError:
        return None

    # ── Prioridade 1: Correspondência exata ───────────────────────────────────
    if nome_curso in pastas_disponiveis:
        caminho = os.path.join(pasta_saep_raiz, nome_curso)
        logger.info(f"SAEP localizado (exato): {caminho}")
        return caminho

    # ── Prioridade 2: Correspondência normalizada ─────────────────────────────
    for pasta in pastas_disponiveis:
        pasta_norm = normalizar_nome(pasta)
        if pasta_norm == curso_norm:
            caminho = os.path.join(pasta_saep_raiz, pasta)
            logger.info(f"SAEP localizado (normalizado): {caminho} ← '{nome_curso}'")
            return caminho

    # ── Prioridade 3: Correspondência parcial ─────────────────────────────────
    # Útil quando o nome do curso é abreviado ou ligeiramente diferente
    for pasta in pastas_disponiveis:
        pasta_norm = normalizar_nome(pasta)
        # Verifica se um contém o outro (mínimo 5 chars para evitar falsos positivos)
        if len(curso_norm) >= 5 and len(pasta_norm) >= 5:
            if curso_norm in pasta_norm or pasta_norm in curso_norm:
                caminho = os.path.join(pasta_saep_raiz, pasta)
                logger.info(
                    f"SAEP localizado (parcial): {caminho} ← '{nome_curso}'"
                )
                return caminho

    logger.info(
        f"SAEP não encontrado para '{nome_curso}' (normalizado: '{curso_norm}'). "
        f"Pastas disponíveis: {pastas_disponiveis}"
    )
    return None


class SAEPReader:
    """
    Lê recursivamente o histórico SAEP de um curso específico.
    Usa mapeamento inteligente para localizar a pasta correta.
    """

    def __init__(self, pasta_saep: str = "SAEP"):
        self.pasta_saep = pasta_saep
        self.doc_reader = DocumentReader()
        os.makedirs(pasta_saep, exist_ok=True)

    def ler_curso(self, nome_curso: str) -> dict:
        """
        Lê todos os arquivos SAEP do curso, separando Diagnóstica e Prática.

        MELHORIA V1.8: Usa localizar_pasta_saep() para encontrar a pasta
        corretamente mesmo com variações de nome (acentos, espaços, case).

        Args:
            nome_curso: Nome do curso (como vem do formulário ou da pasta Cursos/)

        Returns:
            ok(diagnostica, pratica, consolidado, total_arquivos, ...)
        """
        # ── Localiza pasta SAEP automaticamente ──────────────────────────────
        pasta_curso = localizar_pasta_saep(self.pasta_saep, nome_curso)

        estrutura = {
            "diagnostica": {"texto": "", "arquivos": [], "ciclos": []},
            "pratica":      {"texto": "", "arquivos": [], "ciclos": []},
            "outros":       {"texto": "", "arquivos": [], "ciclos": []},
        }

        if not pasta_curso:
            # Não encontrou — retorna vazio sem erro, geração continua normalmente
            logger.info(f"SAEP não disponível para '{nome_curso}' — continuando sem histórico.")
            return ok(
                diagnostica        = estrutura["diagnostica"],
                pratica            = estrutura["pratica"],
                outros             = estrutura["outros"],
                consolidado        = "",
                total_arquivos     = 0,
                total_chars        = 0,
                ciclos_encontrados = [],
                pasta_encontrada   = False,
                tem_conteudo       = False,
            )

        logger.info(f"Varrendo SAEP: {pasta_curso}")
        ciclos_encontrados = set()

        # ── Percorre recursivamente ───────────────────────────────────────────
        for raiz, pastas, arquivos in os.walk(pasta_curso):
            pastas[:] = sorted([p for p in pastas if not p.startswith(".")])

            tipo  = self._identificar_tipo(raiz, pasta_curso)
            ciclo = self._identificar_ciclo(raiz, pasta_curso)
            if ciclo:
                ciclos_encontrados.add(ciclo)

            for nome_arq in sorted(arquivos):
                if nome_arq.startswith("."):
                    continue
                ext = os.path.splitext(nome_arq)[1].lower()
                if ext not in EXTENSOES_VALIDAS:
                    continue

                caminho = os.path.join(raiz, nome_arq)
                resultado = self.doc_reader.ler(caminho)
                if not resultado.get("sucesso"):
                    continue

                texto = resultado["dados"].get("texto", "").strip()
                if not texto:
                    continue

                cabecalho = f"\n[{tipo.upper()} | {ciclo or 'Geral'} | {nome_arq}]\n"
                estrutura[tipo]["texto"]    += cabecalho + texto + "\n"
                estrutura[tipo]["arquivos"].append(nome_arq)
                if ciclo and ciclo not in estrutura[tipo]["ciclos"]:
                    estrutura[tipo]["ciclos"].append(ciclo)

        # ── Consolida ─────────────────────────────────────────────────────────
        partes = []
        for tipo, dados in estrutura.items():
            if dados["texto"].strip():
                partes.append(
                    f"\n{'═'*50}\n  SAEP — {tipo.upper()}\n{'═'*50}\n"
                    + dados["texto"]
                )

        consolidado    = "\n".join(partes)
        total_arquivos = sum(len(e["arquivos"]) for e in estrutura.values())
        total_chars    = len(consolidado)

        logger.info(
            f"SAEP lido | Curso: '{nome_curso}' | "
            f"Arquivos: {total_arquivos} | "
            f"Chars: {total_chars} | "
            f"Ciclos: {sorted(ciclos_encontrados)}"
        )

        return ok(
            diagnostica        = estrutura["diagnostica"],
            pratica            = estrutura["pratica"],
            outros             = estrutura["outros"],
            consolidado        = consolidado,
            total_arquivos     = total_arquivos,
            total_chars        = total_chars,
            ciclos_encontrados = sorted(ciclos_encontrados),
            pasta_encontrada   = True,
            tem_conteudo       = total_chars > 100,
        )

    def curso_tem_saep(self, nome_curso: str) -> bool:
        """Verifica se existe SAEP para o curso (com mapeamento inteligente)."""
        return localizar_pasta_saep(self.pasta_saep, nome_curso) is not None

    def listar_cursos(self) -> list:
        """Lista cursos com SAEP disponível."""
        if not os.path.exists(self.pasta_saep):
            return []
        return sorted([
            d for d in os.listdir(self.pasta_saep)
            if os.path.isdir(os.path.join(self.pasta_saep, d))
            and not d.startswith(".")
        ])

    def _identificar_tipo(self, raiz: str, pasta_base: str) -> str:
        relativo = os.path.relpath(raiz, pasta_base).lower().replace("\\", "/")
        partes   = relativo.split("/")
        for parte in partes:
            if any(i in parte for i in IDENTIFICADORES_DIAGNOSTICA):
                return "diagnostica"
            if any(i in parte for i in IDENTIFICADORES_PRATICA):
                return "pratica"
        return "outros"

    def _identificar_ciclo(self, raiz: str, pasta_base: str) -> str:
        relativo = os.path.relpath(raiz, pasta_base).replace("\\", "/")
        anos = re.findall(r"\b(20\d{2})\b", relativo)
        return anos[-1] if anos else ""
