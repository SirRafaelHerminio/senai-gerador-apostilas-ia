"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           modules/readers/course_reader.py  (V1.3)                         ║
║           Responsabilidade: Navegação e leitura da estrutura Cursos/        ║
╚══════════════════════════════════════════════════════════════════════════════╝

ESTRUTURA ESPERADA:
    Cursos/
    └── Desenvolvimento_de_Sistemas/   ← curso
        ├── Backend/                   ← UC
        │   └── UC_Backend.pdf         ← PDF principal (qualquer nome)
        └── Banco_de_Dados/
            └── UC_Banco.pdf
"""

import os
import logging
from modules.readers.document_reader import DocumentReader
from modules.utils.response import ok, erro

logger = logging.getLogger(__name__)

EXTENSOES_UC = (".pdf", ".docx", ".txt")


class CourseReader:
    """
    Navega na estrutura Cursos/ e lê o documento principal de uma UC.
    """

    def __init__(self, pasta_cursos: str = "Cursos"):
        self.pasta_cursos = pasta_cursos
        self.doc_reader   = DocumentReader()
        os.makedirs(pasta_cursos, exist_ok=True)

    def listar_cursos(self) -> list:
        """Retorna lista de nomes de cursos disponíveis."""
        if not os.path.exists(self.pasta_cursos):
            return []
        return sorted([
            d for d in os.listdir(self.pasta_cursos)
            if os.path.isdir(os.path.join(self.pasta_cursos, d))
            and not d.startswith(".")
        ])

    def listar_ucs(self, curso: str) -> list:
        """Retorna lista de UCs de um curso."""
        pasta = os.path.join(self.pasta_cursos, curso)
        if not os.path.exists(pasta):
            return []
        return sorted([
            d for d in os.listdir(pasta)
            if os.path.isdir(os.path.join(pasta, d))
            and not d.startswith(".")
        ])

    def localizar_arquivo_uc(self, curso: str, uc: str) -> str | None:
        """
        Localiza automaticamente o arquivo principal da UC.
        Prioridade: .pdf > .docx > .txt
        Qualquer nome de arquivo é aceito.
        """
        pasta = os.path.join(self.pasta_cursos, curso, uc)
        if not os.path.exists(pasta):
            return None

        for ext in EXTENSOES_UC:
            for nome in sorted(os.listdir(pasta)):
                if nome.lower().endswith(ext) and not nome.startswith("."):
                    return os.path.join(pasta, nome)
        return None

    def ler_uc(self, curso: str, uc: str) -> dict:
        """
        Lê o documento principal de uma UC e retorna texto + metadados.

        Returns:
            ok(texto, arquivo, curso, uc)
            erro("mensagem")
        """
        arquivo = self.localizar_arquivo_uc(curso, uc)

        if not arquivo:
            return erro(
                f"Nenhum documento encontrado para a UC '{uc}'. "
                f"Adicione um PDF em Cursos/{curso}/{uc}/"
            )

        resultado = self.doc_reader.ler(arquivo)
        if not resultado["sucesso"]:
            return resultado

        texto = resultado["dados"].get("texto", "")
        if not texto.strip():
            return erro(f"O arquivo da UC está vazio: {os.path.basename(arquivo)}")

        return ok(
            texto         = texto,
            arquivo       = os.path.basename(arquivo),
            caminho       = arquivo,
            curso         = curso.replace("_", " "),
            uc            = uc.replace("_", " "),
            curso_pasta   = curso,
            uc_pasta      = uc,
            paginas       = resultado["dados"].get("paginas", 1),
        )

    def info_uc(self, curso: str, uc: str) -> dict:
        """
        Retorna informações da UC sem ler o arquivo completo.
        Usado pela interface para mostrar status antes de gerar.
        """
        arquivo    = self.localizar_arquivo_uc(curso, uc)
        tem_arquivo = arquivo is not None

        avisos = []
        if not tem_arquivo:
            avisos.append(f"Nenhum PDF/DOCX encontrado em Cursos/{curso}/{uc}/")

        return ok(
            curso         = curso.replace("_", " "),
            uc            = uc.replace("_", " "),
            curso_pasta   = curso,
            uc_pasta      = uc,
            tem_arquivo   = tem_arquivo,
            nome_arquivo  = os.path.basename(arquivo) if arquivo else None,
            status        = "ok" if tem_arquivo else "sem_arquivo",
            avisos        = avisos,
        )

    @staticmethod
    def formatar_nome(nome: str) -> str:
        return nome.replace("_", " ")
