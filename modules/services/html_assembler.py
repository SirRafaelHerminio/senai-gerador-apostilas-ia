"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         modules/services/html_assembler.py  (V1.7 — NOVO)                  ║
║         Responsabilidade: Montar apostila final a partir dos capítulos      ║
╚══════════════════════════════════════════════════════════════════════════════╝

ETAPA 5 DA PIPELINE V1.7:

Recebe a lista de capítulos gerados (cada um como HTML parcial)
e os monta num único HTML completo com:
    - Cabeçalho visual profissional (título + UC + bloco)
    - Índice de capítulos com âncoras de navegação
    - Capítulos numerados com separadores visuais
    - Seção de métricas de geração (para debug/transparência)
    - Rodapé com identidade SENAI

Por que separar o assembler do exporter:
    - O exporter lida com disco (salvar, deletar, listar)
    - O assembler lida com HTML (estrutura, navegação, visual)
    - Separação de responsabilidades — facilita testes e evolução
"""

import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# CSS base injetado no envelope — completa o CSS inline dos capítulos
CSS_BASE = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.85;
     color:#1a2a3a;background:#f0f4f9;padding:20px 16px 64px}
.apostila-wrap{max-width:940px;margin:0 auto;background:#fff;
               border-radius:8px;box-shadow:0 4px 28px rgba(13,59,102,.12);overflow:hidden}
h2{font-size:20px;font-weight:700;color:#0d3b66;
   border-left:4px solid #1a5fa8;padding-left:14px;margin:36px 0 14px}
h3{font-size:16px;font-weight:700;color:#1a5fa8;margin:24px 0 10px}
h4{font-size:14px;font-weight:700;color:#1a2a3a;margin:18px 0 8px}
p{font-size:15px;line-height:1.85;color:#1a2a3a;margin:10px 0}
ul,ol{padding-left:22px;margin:10px 0}
li{margin:5px 0;line-height:1.75}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;border-radius:6px;overflow:hidden;box-shadow:0 1px 4px rgba(13,59,102,.08)}
th{background:#0d3b66;color:#fff;padding:11px 14px;text-align:left;font-weight:700}
td{padding:10px 14px;border-bottom:1px solid #e0e8f4;vertical-align:top}
tr:nth-child(even) td{background:#f5f8ff}
pre,code{font-family:'Courier New',Courier,monospace}
pre{background:#1e293b;color:#e2e8f0;border-radius:8px;padding:18px 20px;
    margin:16px 0;overflow-x:auto;font-size:13.5px;line-height:1.7;white-space:pre}
code{background:#eaf2fb;color:#0d3b66;padding:2px 6px;border-radius:3px;font-size:13px}
pre code{background:none;color:inherit;padding:0;font-size:inherit}
hr{border:none;border-top:2px solid #eaf2fb;margin:40px 0}
section{padding:0 40px}
@media print{
  body{background:#fff;padding:0;font-size:13px}
  .apostila-wrap{max-width:100%;box-shadow:none;border-radius:0}
  pre{font-size:11.5px;break-inside:avoid}
  section{padding:0 24px}
  @page{margin:1.8cm}
}
@media(max-width:640px){
  body{padding:8px}
  section{padding:0 16px}
  pre{font-size:12px;padding:12px}
  h2{font-size:17px}
}
"""


class HTMLAssembler:
    """
    Monta o HTML final da apostila a partir dos capítulos gerados.

    Uso:
        assembler = HTMLAssembler()
        html_final = assembler.montar(
            titulo_apostila="...",
            curso="...", uc="...", bloco_aula="...",
            capitulos_gerados=[{html, numero, titulo, ...}, ...],
            metricas={...}
        )
    """

    def montar(
        self,
        titulo_apostila:  str,
        curso:            str,
        uc:               str,
        bloco_aula:       str,
        capitulos_gerados: list,
        metricas:         dict = None,
        provider:         str = "gemini",
    ) -> str:
        """
        Une todos os capítulos num HTML completo e válido.

        Args:
            titulo_apostila:   Título gerado pelo mapa pedagógico
            curso/uc/bloco:    Dados educacionais
            capitulos_gerados: Lista de dicts com {html, numero, titulo, ...}
            metricas:          Dict com totais de tokens, palavras, tempo
            provider:          Nome do provider usado

        Returns:
            String com HTML completo, pronto para salvar em disco
        """
        data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M")

        cabecalho   = self._cabecalho(titulo_apostila, curso, uc, bloco_aula, capitulos_gerados)
        indice      = self._indice(capitulos_gerados)
        corpo       = self._corpo_capitulos(capitulos_gerados)
        rodape      = self._rodape(uc, bloco_aula, metricas, data_geracao, provider)

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="Gerador de Apostilas SENAI V1.7 — Geração Modular">
    <title>Apostila SENAI | {uc} | {bloco_aula}</title>
    <style>{CSS_BASE}</style>
</head>
<body>
<div class="apostila-wrap">
{cabecalho}
{indice}
{corpo}
{rodape}
</div>
<!-- Gerador SENAI V1.7 | {data_geracao} | {provider} | {len(capitulos_gerados)} capítulos -->
</body>
</html>"""

        logger.info(
            f"HTMLAssembler: apostila montada | "
            f"{len(capitulos_gerados)} capítulos | "
            f"{len(html)} chars"
        )

        return html

    # ─── Seções da apostila ───────────────────────────────────────────────────

    def _cabecalho(
        self,
        titulo: str,
        curso:  str,
        uc:     str,
        bloco:  str,
        caps:   list,
    ) -> str:
        """Cabeçalho visual profissional com gradiente azul SENAI."""
        n_caps = len(caps)
        return f"""
<div style="background:linear-gradient(135deg,#0d3b66 0%,#1a5fa8 100%);
            color:#fff;padding:36px 40px 28px;position:relative;overflow:hidden">
  <div style="position:absolute;right:-40px;top:-40px;width:220px;height:220px;
              border-radius:50%;background:rgba(255,255,255,.04)"></div>
  <div style="font-size:10px;font-weight:700;letter-spacing:2px;
              color:rgba(255,255,255,.5);text-transform:uppercase;margin-bottom:10px">
    SENAI &mdash; {curso}
  </div>
  <h1 style="font-size:26px;font-weight:800;color:#fff;margin:0 0 6px;line-height:1.25">
    {titulo}
  </h1>
  <div style="font-size:14px;color:rgba(255,255,255,.75);margin-bottom:20px">
    {uc} &mdash; {bloco}
  </div>
  <div style="display:flex;gap:10px;flex-wrap:wrap">
    <span style="background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);
                 border-radius:20px;padding:4px 14px;font-size:11px;font-weight:600">
      {n_caps} {"capítulo" if n_caps == 1 else "capítulos"}
    </span>
    <span style="background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);
                 border-radius:20px;padding:4px 14px;font-size:11px;font-weight:600">
      Geração Modular V1.7
    </span>
  </div>
</div>"""

    def _indice(self, caps: list) -> str:
        """Índice de navegação com âncoras para cada capítulo."""
        if not caps:
            return ""

        itens = ""
        for c in caps:
            num   = c.get("numero", "?")
            tit   = c.get("titulo", f"Capítulo {num}")
            saep  = c.get("saep_relevante", False)
            saep_badge = (
                '<span style="font-size:9px;font-weight:700;letter-spacing:.5px;'
                'background:#eaf2fb;color:#0d3b66;border-radius:3px;'
                'padding:2px 6px;margin-left:8px">SAEP</span>'
                if saep else ""
            )
            itens += f"""
    <li style="display:flex;align-items:center;padding:8px 0;
               border-bottom:1px solid #f0f4f9;font-size:14px">
      <span style="min-width:28px;height:28px;border-radius:50%;background:#0d3b66;
                   color:#fff;display:inline-flex;align-items:center;
                   justify-content:center;font-size:11px;font-weight:700;
                   margin-right:12px;flex-shrink:0">{num}</span>
      <a href="#cap{num}" style="color:#1a2a3a;text-decoration:none;flex:1">
        {tit}
      </a>
      {saep_badge}
    </li>"""

        return f"""
<section style="padding:28px 40px 8px">
  <div style="background:#f8faff;border:1px solid #d0dae8;
              border-radius:10px;padding:22px 26px">
    <div style="font-size:11px;font-weight:700;letter-spacing:1px;
                text-transform:uppercase;color:#0d3b66;margin-bottom:14px;
                padding-bottom:10px;border-bottom:2px solid #eaf2fb">
      Índice
    </div>
    <ul style="list-style:none;padding:0;margin:0">{itens}
    </ul>
  </div>
</section>"""

    def _corpo_capitulos(self, caps: list) -> str:
        """Monta o corpo com todos os capítulos, separados visualmente."""
        partes = []

        for i, c in enumerate(caps):
            num     = c.get("numero", i + 1)
            titulo  = c.get("titulo", f"Capítulo {num}")
            html_c  = c.get("html", "")

            # Cabeçalho do capítulo (gerado pelo assembler, não pela IA)
            cabecalho_cap = f"""
<div id="cap{num}" style="background:#f8faff;border-left:5px solid #0d3b66;
                          padding:18px 40px;margin-top:40px">
  <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;
              color:#1a5fa8;text-transform:uppercase;margin-bottom:4px">
    Capítulo {num}
  </div>
  <div style="font-size:19px;font-weight:700;color:#0d3b66">{titulo}</div>
</div>"""

            # Conteúdo do capítulo (HTML gerado pela IA, limpo)
            html_limpo = self._limpar_html_capitulo(html_c)

            # Separador entre capítulos (exceto o último)
            sep = '<hr style="border:none;border-top:2px solid #eaf2fb;margin:40px 40px 0">' \
                  if i < len(caps) - 1 else ""

            partes.append(f"{cabecalho_cap}\n{html_limpo}\n{sep}")

        return "\n".join(partes)

    def _rodape(
        self,
        uc:           str,
        bloco:        str,
        metricas:     dict,
        data_geracao: str,
        provider:     str,
    ) -> str:
        """Rodapé com identidade SENAI e métricas de geração."""
        met = metricas or {}
        caps        = met.get("total_capitulos",  "?")
        palavras    = met.get("total_palavras",   "?")
        tokens_out  = met.get("total_tokens_out", "?")
        tempo       = met.get("tempo_total",      "?")

        metricas_html = f"""
  <div style="font-size:10px;color:rgba(255,255,255,.35);margin-top:8px;
              padding-top:8px;border-top:1px solid rgba(255,255,255,.1)">
    {caps} capítulos &bull; ~{palavras} palavras &bull;
    {tokens_out} tokens saída &bull; {tempo}s
  </div>""" if metricas else ""

        return f"""
<div style="background:#0d3b66;color:rgba(255,255,255,.65);padding:18px 40px;
            display:flex;justify-content:space-between;align-items:flex-end;
            flex-wrap:wrap;gap:8px;margin-top:48px">
  <div>
    <div style="font-size:12px;font-weight:700;color:#fff;letter-spacing:.3px">
      SENAI &mdash; Gerador de Apostilas V1.7
    </div>
    <div style="font-size:11px;margin-top:3px">Geração Modular por Capítulos</div>
    {metricas_html}
  </div>
  <div style="font-size:11px;text-align:right">
    <div>{uc}</div>
    <div style="margin-top:2px">{bloco}</div>
    <div style="margin-top:2px;color:rgba(255,255,255,.4)">{data_geracao}</div>
  </div>
</div>"""

    # ─── Utilitários ──────────────────────────────────────────────────────────

    def _limpar_html_capitulo(self, html: str) -> str:
        """
        Limpa o HTML de um capítulo gerado pela IA.
        Remove markdown residual e garante que começa com tag HTML válida.
        """
        if not html:
            return '<section style="padding:20px 40px"><p>Conteúdo não gerado.</p></section>'

        t = html.strip()

        # Remove markdown
        t = re.sub(r"^```html\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"^```\s*",     "", t)
        t = re.sub(r"\s*```$",     "", t)

        # Remove DOCTYPE/html/head/body se a IA gerou erroneamente
        t = re.sub(r"<!DOCTYPE[^>]*>", "", t, flags=re.IGNORECASE)
        t = re.sub(r"<html[^>]*>",     "", t, flags=re.IGNORECASE)
        t = re.sub(r"</html>",         "", t, flags=re.IGNORECASE)
        t = re.sub(r"<head>.*?</head>","", t, flags=re.IGNORECASE | re.DOTALL)
        t = re.sub(r"<body[^>]*>",     "", t, flags=re.IGNORECASE)
        t = re.sub(r"</body>",         "", t, flags=re.IGNORECASE)

        # Remove texto antes da primeira tag HTML
        match = re.search(r"<(section|div|h[1-6]|p|ul|ol|table|pre)", t, re.IGNORECASE)
        if match and match.start() > 0:
            t = t[match.start():]

        # Envolve em section com padding se não tiver wrapper
        if t.strip() and not t.strip().lower().startswith("<section"):
            t = f'<section style="padding:20px 40px 4px">\n{t}\n</section>'

        return t.strip()
