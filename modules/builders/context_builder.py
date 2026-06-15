"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         modules/builders/context_builder.py  (V1.6)                        ║
║         Prompt pedagógico — profundidade máxima, início técnico imediato   ║
╚══════════════════════════════════════════════════════════════════════════════╝

MUDANÇAS V1.5.1 → V1.6:
    - Proporção de tokens revisada: 85% para conteúdo técnico
    - Instrução explícita de densidade mínima por conceito
    - Cabeçalho visual mais rico (título + UC + bloco estilizados)
    - CSS do cabeçalho embutido nas instruções de design
    - Remoção total de introduções genéricas — conteúdo começa imediatamente
    - Instrução de profundidade por nível: fundamentos → aplicação → mercado
    - Guia de CSS compacto mas suficiente para visual profissional
"""

import logging
from typing import Optional
from modules.utils.response import ok, erro

logger = logging.getLogger(__name__)

LIMITE_MESTRE  = 8000
LIMITE_EXTRATO = 5000
LIMITE_SAEP    = 3000
LIMITE_PLANO   = 6000


class ContextBuilder:
    """
    Monta o prompt V1.6 — início rápido, profundidade máxima, visual rico.
    """

    def montar(
        self,
        prompt_mestre: str,
        extrato_uc:    str,
        resumo_saep:   str,
        plano_aula:    str,
        curso:         str,
        uc:            str,
        bloco_aula:    str,
        observacoes:   Optional[str] = None,
    ) -> dict:

        if not extrato_uc and not plano_aula:
            return erro("Ao menos o extrato da UC ou o plano de aula devem estar presentes")

        m = self._t(prompt_mestre, LIMITE_MESTRE,  "Prompt Mestre")
        e = self._t(extrato_uc,   LIMITE_EXTRATO,  "Extrato UC")
        s = self._t(resumo_saep,  LIMITE_SAEP,     "SAEP")
        p = self._t(plano_aula,   LIMITE_PLANO,    "Plano de Aula")

        blocos = [
            self._b_mestre(m),
            self._b_contexto(curso, uc, bloco_aula),
            self._b_uc(e),
            self._b_saep(s),
            self._b_plano(p),
            self._b_obs(observacoes),
            self._b_instrucoes(),
            self._b_design(curso, uc, bloco_aula),
            self._b_instrucao_final(curso, uc, bloco_aula),
        ]

        prompt = "\n\n".join(b for b in blocos if b).strip()
        tokens = len(prompt) // 4
        logger.info(f"Prompt V1.6 | {len(prompt)} chars | ~{tokens} tokens estimados")
        return ok(prompt=prompt, tokens_estimados=tokens)

    # ── Bloco 0: Prompt Mestre ─────────────────────────────────────────────────
    def _b_mestre(self, texto: str) -> str:
        if not texto:
            return (
                "PAPEL: Professor técnico sênior do SENAI. "
                "Gere material de referência didática denso e profundo. "
                "Escreva como especialista, não como enciclopédia. "
                "Linguagem técnica, didática, direta."
            )
        return "PROMPT MESTRE — REGRAS GERAIS:\n" + texto

    # ── Bloco 1: Contexto educacional ─────────────────────────────────────────
    def _b_contexto(self, curso: str, uc: str, bloco: str) -> str:
        return (
            f"CONTEXTO: Curso: {curso} | UC: {uc} | Bloco: {bloco}\n"
            "Gere a apostila especificamente para este bloco. "
            "Todo conteúdo ancorado nas competências desta UC."
        )

    # ── Bloco 2: Extrato da UC ────────────────────────────────────────────────
    def _b_uc(self, extrato: str) -> str:
        if not extrato:
            return ""
        return "CONTEXTO PEDAGÓGICO DA UC:\n" + extrato

    # ── Bloco 3: SAEP ─────────────────────────────────────────────────────────
    def _b_saep(self, resumo: str) -> str:
        if not resumo or "não disponível" in resumo.lower():
            return ""
        return (
            "HISTÓRICO SAEP — use para priorizar tópicos e inserir boxes SAEP:\n"
            + resumo
        )

    # ── Bloco 4: Plano de aula ────────────────────────────────────────────────
    def _b_plano(self, plano: str) -> str:
        if not plano or not plano.strip():
            return ""
        return "PLANO DE AULA DO PROFESSOR (siga esta sequência):\n" + plano

    # ── Bloco 5: Observações ──────────────────────────────────────────────────
    def _b_obs(self, obs: Optional[str]) -> str:
        if not obs or not obs.strip():
            return ""
        return "INSTRUÇÃO DO PROFESSOR (prioridade máxima):\n" + obs.strip()

    # ── Bloco 6: Instruções pedagógicas V1.6 ──────────────────────────────────
    def _b_instrucoes(self) -> str:
        return """INSTRUÇÕES DE GERAÇÃO V1.6
══════════════════════════════════════════════════════

DISTRIBUIÇÃO DE TOKENS:
  3%  → Cabeçalho visual + Capacidades + Competências + SA
  85% → Desenvolvimento técnico (núcleo — expanda ao máximo)
  12% → Pontos SAEP + Checklist + Próximos passos

REGRA CENTRAL:
  Esta apostila é o material de estudo de um bloco que pode ter até 20h de aula.
  Ela deve ser DENSA, COMPLETA e APROFUNDADA como um capítulo de livro técnico.
  NÃO é um resumo. NÃO é uma apresentação. É um material de formação profissional.

SEÇÕES INICIAIS — máximo 3% dos tokens:
  • Cabeçalho visual: título, UC, bloco — apenas isso
  • Capacidades: lista direta, sem parágrafo explicativo
  • Competências: uma linha por competência
  • Relação com SA: 1 parágrafo objetivo e curto
  PROIBIDO: introdução longa, motivação, contextualização genérica, repetição

DESENVOLVIMENTO TÉCNICO — mínimo 85% dos tokens:
  Para CADA conceito do bloco, desenvolva em 5 profundidades:

  1. DEFINIÇÃO TÉCNICA PRECISA
     • O que é exatamente — sem simplificações excessivas
     • Por que existe — qual problema resolve
     • Quando usar — contexto de aplicação
     • Como se relaciona com outros conceitos do bloco
     Extensão mínima: 3 parágrafos densos por conceito

  2. EXPLICAÇÃO PROGRESSIVA (do simples ao complexo)
     • Comece pelo fundamento mais básico
     • Adicione camadas de complexidade gradualmente
     • Cada camada explicada antes de adicionar a próxima
     • Use analogias concretas quando ajudar a fixar
     Nunca pule etapas — o aluno precisa acompanhar a progressão

  3. DEMONSTRAÇÃO COM CÓDIGO (quando aplicável)
     • Código funcional, testável e comentado LINHA A LINHA
     • Versão 1: mais simples possível, apenas o essencial
     • Versão 2: com variações e casos adicionais
     • Versão 3: próxima do que é usado em produção
     • Mostre a saída esperada de cada versão
     • Use dados realistas (nomes, valores, situações de empresa)
     Nunca use foo, bar, x, y como variáveis — use nomes descritivos

  4. VARIAÇÕES E CASOS ESPECIAIS
     • O que muda em cenários diferentes
     • Comportamentos inesperados e como identificar
     • Diferenças entre abordagens e critério de escolha
     • Tabela comparativa quando houver mais de 2 opções

  5. APLICAÇÃO PROFISSIONAL REAL
     • Como isso funciona em empresa real (cite: Nubank, iFood, etc.)
     • Qual problema de negócio concreto resolve
     • Ferramentas do mercado que implementam este conceito
     • O que muda do código de estudante para o código de produção

BOXES OBRIGATÓRIOS — use abundantemente ao longo do conteúdo:
  [ATENÇÃO]       → erros comuns, armadilhas, o que não fazer
  [DICA PRO]      → conhecimento de profissional sênior
  [SAEP]          → tópico com alta probabilidade de cobrança
  [BOAS PRÁTICAS] → padrões e convenções do mercado
  Coloque boxes DENTRO das seções, não apenas no final

PONTOS SAEP — 8% dos tokens:
  • Liste os tópicos mais cobrados deste bloco
  • Para cada um: o que saber, como costuma cair, erro mais comum
  • Baseie-se no histórico SAEP se disponível

CHECKLIST — 4% dos tokens:
  • 10 a 15 itens de autoavaliação
  • Linguagem de ação: "Sei explicar...", "Consigo implementar..."
  • Cubra os principais conceitos do bloco

PROIBIÇÕES ABSOLUTAS:
  × Parágrafos genéricos ("A programação é muito importante...")
  × Frases motivacionais ("Ao final desta jornada...")
  × Repetir o mesmo conceito com palavras diferentes
  × Objetivos textuais em múltiplos formatos
  × Seções decorativas sem conteúdo técnico real
  × Encerrar o conteúdo antes de esgotar o limite de tokens
  × Respostas curtas — use TODO o espaço disponível"""

    # ── Bloco 7: Design HTML V1.6 ─────────────────────────────────────────────
    def _b_design(self, curso: str, uc: str, bloco: str) -> str:
        return f"""DESIGN HTML V1.6 — AVA/SENAI
══════════════════════════════════════════════════════

SAÍDA: Uma única <div style="..."> com CSS inline.
Comece com <div — sem texto antes.
PROIBIDO: ```html, <!DOCTYPE>, <html>, <head>, <body>, JavaScript, CSS externo.
Fontes: Arial, Helvetica, sans-serif apenas.

PALETA SENAI:
  #0d3b66 azul escuro | #1a5fa8 azul médio | #eaf2fb azul claro
  #1a2a3a texto | #4a6a8a texto2 | #d0dae8 borda
  #1e293b fundo código | #e2e8f0 texto código
  #fffbeb/#d97706 atenção | #f3f0ff/#7c3aed dica
  #e8f5ee/#0f6b3a boas práticas | #eaf2fb/#0d3b66 SAEP

CABEÇALHO VISUAL OBRIGATÓRIO (use estes estilos exatos):
  <div style="background:#0d3b66;color:#fff;padding:32px 40px 24px;border-radius:8px 8px 0 0">
    <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:rgba(255,255,255,.5);
                text-transform:uppercase;margin-bottom:12px">
      SENAI — {curso}
    </div>
    <h1 style="font-size:28px;font-weight:800;color:#fff;margin:0 0 8px;line-height:1.2">
      {bloco}
    </h1>
    <div style="font-size:15px;color:rgba(255,255,255,.75);margin-bottom:20px">
      {uc}
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      [badges: Capacidades como tags visuais — background:rgba(255,255,255,.12)]
    </div>
  </div>

WRAPPER PRINCIPAL:
  <div style="max-width:920px;margin:0 auto;font-family:Arial,Helvetica,sans-serif;
              background:#fff;border-radius:8px;box-shadow:0 4px 20px rgba(13,59,102,.1)">

SEÇÕES DENTRO DO CORPO (padding: 0 40px):
  Cabeçalho de seção:
    <h2 style="font-size:20px;font-weight:700;color:#0d3b66;
               border-left:4px solid #1a5fa8;padding-left:14px;margin:36px 0 16px">

  Subtítulo:
    <h3 style="font-size:16px;font-weight:700;color:#1a5fa8;margin:24px 0 10px">

  Parágrafo:
    <p style="font-size:15px;line-height:1.85;color:#1a2a3a;margin:10px 0">

BLOCOS DE CÓDIGO:
  <div style="background:#1e293b;border-radius:8px;margin:18px 0;overflow:hidden">
    <div style="background:#0f172a;padding:8px 16px;font-size:11px;font-weight:700;
                color:#94a3b8;letter-spacing:1px;text-transform:uppercase">
      LINGUAGEM — Descrição do exemplo
    </div>
    <pre style="margin:0;padding:18px 20px;font-family:'Courier New',monospace;
                font-size:13.5px;color:#e2e8f0;line-height:1.7;overflow-x:auto">
      código aqui
    </pre>
  </div>

BOXES DE DESTAQUE:
  ATENÇÃO:        background:#fffbeb; border-left:4px solid #d97706; padding:14px 18px; border-radius:6px
  DICA PRO:       background:#f3f0ff; border-left:4px solid #7c3aed; padding:14px 18px; border-radius:6px
  SAEP:           background:#eaf2fb; border:1px solid #b3d4f0; border-left:4px solid #0d3b66; padding:14px 18px; border-radius:6px
  BOAS PRÁTICAS:  background:#e8f5ee; border-left:4px solid #0f6b3a; padding:14px 18px; border-radius:6px
  Label do box:   <strong style="font-size:10px;font-weight:900;letter-spacing:1.5px;
                              text-transform:uppercase;display:block;margin-bottom:6px">TIPO</strong>

TABELAS:
  <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;border-radius:6px;overflow:hidden">
    <thead><tr style="background:#0d3b66;color:#fff">
      <th style="padding:11px 14px;text-align:left;font-weight:700">Col</th>
    </tr></thead>
    <tbody>
      <tr><td style="padding:10px 14px;border-bottom:1px solid #e0e8f4">val</td></tr>
      <tr style="background:#f5f8ff"><td style="padding:10px 14px;border-bottom:1px solid #e0e8f4">val</td></tr>
    </tbody>
  </table>

SEPARADOR DE SEÇÃO:
  <hr style="border:none;border-top:2px solid #eaf2fb;margin:36px 0">

CHECKLIST:
  <ul style="list-style:none;padding:0;margin:12px 0">
    <li style="display:flex;gap:12px;padding:8px 0;border-bottom:1px solid #f0f4f9;font-size:14px">
      <span style="width:18px;height:18px;border:2px solid #1a5fa8;border-radius:3px;
                   flex-shrink:0;margin-top:2px;display:inline-block"></span>
      Item do checklist
    </li>
  </ul>

RODAPÉ:
  <div style="background:#0d3b66;color:rgba(255,255,255,.7);padding:16px 40px;
              display:flex;justify-content:space-between;font-size:12px;
              border-radius:0 0 8px 8px">
    <span>SENAI — Gerador de Apostilas V1.6</span>
    <span>{uc} | {bloco}</span>
  </div>

REGRAS VISUAIS:
  • SEM emojis em nenhuma parte
  • Espaçamento generoso — leitura confortável
  • Código: SEMPRE com comentários em português
  • Tabelas: SEMPRE que houver comparação entre 2+ elementos"""

    # ── Bloco 8: Instrução final ──────────────────────────────────────────────
    def _b_instrucao_final(self, curso: str, uc: str, bloco: str) -> str:
        return f"""GERE A APOSTILA AGORA
══════════════════════════════════════════════════════

Curso: {curso} | UC: {uc} | Bloco: {bloco}

ESTRUTURA OBRIGATÓRIA:

  [1] CABEÇALHO VISUAL                           (3% dos tokens)
      Use o template de cabeçalho exato fornecido acima.
      Inclua capacidades como badges visuais.

  [2] COMPETÊNCIAS + RELAÇÃO COM SA              (2% dos tokens)
      Lista direta. Um parágrafo para SA. Sem mais.

  [3] DESENVOLVIMENTO TÉCNICO                   (85% dos tokens)
      Para CADA tópico do bloco:
        → Definição técnica precisa e extensa
        → Explicação progressiva com analogia
        → Código versão simples → intermediário → profissional
        → Variações, casos especiais, tabela comparativa
        → Box ATENÇÃO (erros comuns)
        → Box BOAS PRÁTICAS
        → Box DICA PRO
        → Aplicação profissional real com empresa nomeada
      Use boxes SAEP ao longo de todo o desenvolvimento.
      NÃO encerre o desenvolvimento antes de esgotar os tokens.

  [4] PONTOS-CHAVE SAEP                          (8% dos tokens)
      Tópicos mais cobrados com profundidade de resposta.

  [5] CHECKLIST DE APRENDIZAGEM                 (4% dos tokens)
      10 a 15 itens. Linguagem de ação.

  [6] PRÓXIMOS PASSOS                            (1% dos tokens)
      Uma frase conectando ao próximo bloco.

  [7] RODAPÉ
      Use o template de rodapé fornecido.

REGRAS CRÍTICAS:
  • Comece DIRETAMENTE com <div — nada antes
  • NUNCA use ```html ou markdown
  • NUNCA use placeholders [inserir aqui]
  • NUNCA encerre antes do limite — use todo o espaço disponível
  • Se aproximar do limite: conclua a seção atual → checklist → feche tags
  • HTML sempre válido — nunca corte no meio de uma tag"""

    def _t(self, texto: str, limite: int, nome: str) -> str:
        if not texto:
            return ""
        if len(texto) <= limite:
            return texto
        logger.warning(f"'{nome}' truncado: {len(texto)} → {limite} chars")
        return texto[:limite] + f"\n[... {nome} truncado ...]"
