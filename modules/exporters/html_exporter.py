"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         modules/exporters/html_exporter.py  (V1.6)                         ║
║         Envelope HTML com CSS profissional + delete de apostilas           ║
╚══════════════════════════════════════════════════════════════════════════════╝

MUDANÇAS V1.5 → V1.6:
    - Envelope HTML com CSS base aprimorado (tipografia, código, tabelas, print)
    - Método deletar() para remoção física de apostilas
    - Validação com métricas de palavras
    - CSS @media print otimizado
"""

import os
import re
import logging
from datetime import datetime
from typing import Optional
from modules.utils.response import ok, erro

logger = logging.getLogger(__name__)

ENVELOPE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="Gerador de Apostilas SENAI V1.6">
    <title>{titulo}</title>
    <style>
        *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
        body{{
            font-family:Arial,Helvetica,sans-serif;
            font-size:15px;line-height:1.85;
            color:#1a2a3a;background:#f0f4f9;
            padding:20px 16px 56px;
        }}
        .apostila-body,body>div{{
            max-width:920px;margin:0 auto;background:#fff;
            border-radius:8px;
            box-shadow:0 4px 24px rgba(13,59,102,.12);
            overflow:hidden;
        }}
        h1{{font-size:28px;font-weight:800;color:#0d3b66;margin:0 0 8px;line-height:1.2}}
        h2{{font-size:20px;font-weight:700;color:#0d3b66;
            border-left:4px solid #1a5fa8;padding-left:14px;margin:36px 0 14px}}
        h3{{font-size:16px;font-weight:700;color:#1a5fa8;margin:24px 0 10px}}
        h4{{font-size:14px;font-weight:700;color:#1a2a3a;margin:18px 0 8px}}
        p{{font-size:15px;line-height:1.85;color:#1a2a3a;margin:10px 0}}
        ul,ol{{padding-left:22px;margin:10px 0}}
        li{{margin:5px 0;line-height:1.75}}
        table{{width:100%;border-collapse:collapse;margin:16px 0;
               font-size:14px;border-radius:6px;overflow:hidden}}
        th{{background:#0d3b66;color:#fff;padding:11px 14px;
            text-align:left;font-weight:700}}
        td{{padding:10px 14px;border-bottom:1px solid #e0e8f4;vertical-align:top}}
        tr:nth-child(even) td{{background:#f5f8ff}}
        pre,code{{font-family:'Courier New',Courier,monospace}}
        pre{{background:#1e293b;color:#e2e8f0;border-radius:8px;
             padding:18px 20px;margin:16px 0;overflow-x:auto;
             font-size:13.5px;line-height:1.7;white-space:pre}}
        code{{background:#eaf2fb;color:#0d3b66;padding:2px 6px;
              border-radius:3px;font-size:13px}}
        pre code{{background:none;color:inherit;padding:0;font-size:inherit}}
        hr{{border:none;border-top:2px solid #eaf2fb;margin:36px 0}}
        @media print{{
            body{{background:#fff;padding:0;font-size:13px}}
            .apostila-body,body>div{{max-width:100%;box-shadow:none;border-radius:0}}
            pre{{font-size:11.5px;break-inside:avoid}}
            h2{{break-before:auto}}
            @page{{margin:1.8cm}}
        }}
        @media(max-width:640px){{
            body{{padding:8px}}
            h1{{font-size:22px}}
            h2{{font-size:17px}}
            pre{{font-size:12px;padding:12px}}
        }}
    </style>
</head>
<body>
{conteudo}
<!-- Gerador SENAI V1.6 | {data} | {provider} -->
</body>
</html>"""


class HTMLExporter:

    def __init__(self, pasta_output: str = "output"):
        self.pasta_output = pasta_output
        os.makedirs(pasta_output, exist_ok=True)

    def exportar(
        self,
        conteudo_ia: str,
        curso:       str,
        uc:          str,
        bloco_aula:  str,
        professor:   Optional[str] = None,
        provider:    str = "gemini",
    ) -> dict:
        if not conteudo_ia or not conteudo_ia.strip():
            return erro("Conteúdo retornado pela IA está vazio")

        conteudo_limpo = self._limpar_markdown(conteudo_ia)
        html_final     = self._construir(conteudo_limpo, uc, bloco_aula, provider)

        v = self._validar(html_final)
        if not v["valido"]:
            return erro(f"HTML inválido: {'; '.join(v['erros'])}")

        nome    = self._gerar_nome(curso, uc, bloco_aula)
        caminho = os.path.join(self.pasta_output, nome)

        try:
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(html_final)
        except Exception as e:
            return erro(f"Falha ao salvar: {e}")

        tamanho = os.path.getsize(caminho)
        data_hr = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        logger.info(f"Apostila V1.6 salva: {nome} ({self._fmt(tamanho)})")

        return ok(
            nome_arquivo    = nome,
            caminho_arquivo = caminho,
            tamanho_bytes   = tamanho,
            tamanho_legivel = self._fmt(tamanho),
            data_geracao    = data_hr,
            qualidade       = v.get("qualidade", {}),
            avisos          = v.get("avisos", []),
        )

    def listar(self) -> list:
        if not os.path.exists(self.pasta_output):
            return []
        apostilas = []
        for nome in os.listdir(self.pasta_output):
            if not nome.endswith(".html"):
                continue
            caminho = os.path.join(self.pasta_output, nome)
            stat    = os.stat(caminho)
            apostilas.append({
                "nome_arquivo": nome,
                "caminho":      caminho,
                "tamanho":      self._fmt(stat.st_size),
                "data_criacao": datetime.fromtimestamp(stat.st_ctime).strftime("%d/%m/%Y %H:%M"),
            })
        return sorted(apostilas, key=lambda x: x["data_criacao"], reverse=True)

    def deletar(self, nome_arquivo: str) -> dict:
        """
        Remove fisicamente uma apostila do disco.
        Valida o nome para evitar path traversal.
        """
        # Segurança: garante que o nome não contém path traversal
        nome_seguro = os.path.basename(nome_arquivo)
        if not nome_seguro.endswith(".html"):
            return erro("Apenas arquivos .html podem ser removidos")

        caminho = os.path.join(self.pasta_output, nome_seguro)

        if not os.path.exists(caminho):
            return erro(f"Arquivo não encontrado: {nome_seguro}")

        try:
            os.remove(caminho)
            logger.info(f"Apostila removida: {nome_seguro}")
            return ok(mensagem=f"Apostila '{nome_seguro}' removida com sucesso")
        except Exception as e:
            return erro(f"Falha ao remover arquivo: {e}")

    # ─── Privados ─────────────────────────────────────────────

    def _limpar_markdown(self, texto: str) -> str:
        t = texto.strip()
        t = re.sub(r"^```html\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"^```\s*",     "", t)
        t = re.sub(r"\s*```$",     "", t)
        match = re.search(r"(?i)(<div|<!doctype)", t)
        if match and match.start() > 0:
            t = t[match.start():]
        return t.strip()

    def _construir(self, conteudo: str, uc: str, bloco: str, provider: str) -> str:
        if conteudo.lower().startswith("<!doctype"):
            return conteudo
        titulo = f"Apostila SENAI | {uc} | {bloco}"
        return ENVELOPE.format(
            titulo   = titulo,
            conteudo = conteudo,
            data     = datetime.now().strftime("%d/%m/%Y às %H:%M"),
            provider = provider,
        )

    def _validar(self, html: str) -> dict:
        erros, avisos, qualidade = [], [], {}
        if not html or len(html.strip()) < 200:
            erros.append("Conteúdo vazio ou muito curto")
            return {"valido": False, "erros": erros, "avisos": avisos, "qualidade": qualidade}

        texto_puro = re.sub(r"<[^>]+>", "", html)
        qualidade["palavras"]      = len(texto_puro.split())
        qualidade["tem_codigo"]    = "<pre" in html or "<code" in html
        qualidade["tem_tabela"]    = "<table" in html
        qualidade["tamanho_html"]  = self._fmt(len(html))

        if "<div" not in html.lower():
            erros.append("Nenhuma tag <div> encontrada")
        if qualidade["palavras"] < 300:
            erros.append(f"Conteúdo muito curto ({qualidade['palavras']} palavras)")
        if qualidade["palavras"] < 800:
            avisos.append(f"Apostila com poucas palavras ({qualidade['palavras']}) — pode estar incompleta")

        return {"valido": len(erros) == 0, "erros": erros, "avisos": avisos, "qualidade": qualidade}

    def _gerar_nome(self, curso: str, uc: str, bloco: str) -> str:
        def s(t, n):
            return re.sub(r"\s+", "_", re.sub(r"[^\w\s]", "", t).strip())[:n]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"apostila_{s(curso,10)}_{s(uc,12)}_{s(bloco,10)}_{ts}.html"

    def _fmt(self, b: int) -> str:
        if b < 1024:    return f"{b} B"
        if b < 1024**2: return f"{b/1024:.1f} KB"
        return f"{b/1024**2:.1f} MB"
