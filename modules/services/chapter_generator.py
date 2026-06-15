"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         modules/services/chapter_generator.py  (V1.7 — NOVO)               ║
║         Responsabilidade: Gerar cada capítulo individualmente               ║
╚══════════════════════════════════════════════════════════════════════════════╝

ETAPA 3 DA PIPELINE V1.7:

Recebe um capítulo do mapa pedagógico e gera seu conteúdo HTML completo
usando uma chamada dedicada à IA — com todos os tokens focados apenas
naquele capítulo.

Por que isso produz apostilas muito melhores:
    - A IA não precisa se preocupar com estrutura global
    - Todos os tokens vão para CONTEÚDO daquele capítulo específico
    - Cada capítulo é uma mini-apostila robusta e aprofundada
    - Erros em um capítulo não afetam os outros
    - Possibilidade futura: regenerar capítulo individualmente

Cada chamada retorna HTML puro do capítulo (sem DOCTYPE, head, body).
O html_assembler depois une tudo num HTML final coerente.
"""

import logging
import time
from typing import Optional
from modules.utils.response import ok, erro

logger = logging.getLogger(__name__)


# ─── Template de prompt por capítulo ──────────────────────────────────────────
PROMPT_CAPITULO = """Você é um professor técnico sênior do SENAI gerando UM CAPÍTULO específico de uma apostila.

CONTEXTO GERAL:
Curso     : {curso}
UC        : {uc}
Apostila  : {titulo_apostila}
Bloco     : {bloco_aula}

CAPÍTULO ATUAL:
Número    : {numero}/{total}
Título    : {titulo}
Subtítulo : {subtitulo}
Tópicos   : {topicos}
Nível     : {profundidade}
SAEP      : {saep_relevante}

{conexao_anterior_texto}

CONTEXTO PEDAGÓGICO (use para embasar o conteúdo):
{extrato_uc}

{saep_resumo}

{obs_professor}

CAPÍTULOS JÁ GERADOS (para continuidade — NÃO repita):
{capitulos_anteriores}

══════════════════════════════════════════════════════════════
INSTRUÇÕES DE GERAÇÃO DESTE CAPÍTULO
══════════════════════════════════════════════════════════════

MISSÃO: Gerar o Capítulo {numero} completo, denso e aprofundado.
Use TODOS os tokens disponíveis para ENSINAR. Não encerre cedo.

PARA CADA TÓPICO DESTE CAPÍTULO:

1. DEFINIÇÃO TÉCNICA PRECISA
   • O que é exatamente — sem simplificações desnecessárias
   • Por que existe — qual problema técnico resolve
   • Quando usar e quando NÃO usar
   • Como se diferencia de conceitos similares
   Mínimo: 3 parágrafos densos por tópico

2. EXPLICAÇÃO PROGRESSIVA
   • Comece pelo fundamento mais básico
   • Adicione camadas de complexidade gradualmente
   • Use analogia concreta do cotidiano quando ajudar
   • Conecte com conhecimentos que o aluno já tem
   Nunca pule etapas — construa o conhecimento passo a passo

3. DEMONSTRAÇÃO TÉCNICA (código quando aplicável)
   • Versão mínima: funcional e comentada LINHA A LINHA
   • Versão intermediária: com variações e casos adicionais
   • Versão profissional: próxima do que é usado em produção
   • Mostre a saída esperada após cada bloco
   • Use dados realistas — nunca foo, bar, x, y
   • Explique CADA linha que não é óbvia

4. VARIAÇÕES E CASOS ESPECIAIS
   • O que muda em cenários diferentes
   • Comportamentos inesperados e como identificar
   • Tabela comparativa quando houver 2+ abordagens

5. ERROS COMUNS (box ATENÇÃO)
   • 3 a 5 erros reais que iniciantes cometem
   • Como identificar cada erro
   • Como corrigir cada erro

6. BOAS PRÁTICAS (box BOAS PRÁTICAS)
   • Convenções e padrões do mercado
   • O que diferencia código bom de código ruim aqui

7. APLICAÇÃO PROFISSIONAL (box CONTEXTO PROFISSIONAL)
   • Empresa real que usa isso (Nubank, iFood, Magazine Luiza, etc.)
   • Como aparece no dia a dia de um desenvolvedor/técnico
   • Problema de negócio concreto que resolve

{saep_instrucao}

DESIGN HTML DESTE CAPÍTULO:
• Retorne APENAS o HTML do capítulo — sem DOCTYPE, html, head, body
• Comece com: <section style="margin-bottom:48px">
• Use CSS inline em todos os elementos
• Paleta: #0d3b66 azul-escuro | #1a5fa8 azul-médio | #eaf2fb azul-claro
         #1a2a3a texto | #4a6a8a texto2 | #1e293b fundo-código | #e2e8f0 código
• Código: fundo #1e293b, texto #e2e8f0, 'Courier New' monospace, comentários em português
• Boxes: ATENÇÃO=#fffbeb/#d97706 | DICA PRO=#f3f0ff/#7c3aed | BOAS PRÁTICAS=#e8f5ee/#0f6b3a
         SAEP=#eaf2fb/borda #0d3b66 | CONTEXTO PROFISSIONAL=#fff7ed/#ea580c
• SEM emojis | Espaçamento generoso | Hierarquia visual clara

REGRAS CRÍTICAS:
• Use TODO o espaço disponível — não encerre antes do limite
• NUNCA use placeholders [inserir aqui]
• NUNCA repita conteúdo de capítulos anteriores
• Comece DIRETAMENTE com <section — sem texto antes
• NUNCA use ```html ou markdown
• Se aproximar do limite: conclua o tópico atual e feche as tags HTML"""


class ChapterGenerator:
    """
    Gera o conteúdo HTML de um capítulo individual.

    Cada capítulo é uma chamada independente à IA, com contexto focado
    e todos os tokens dedicados àquele conteúdo específico.

    Uso:
        gen = ChapterGenerator(provider)
        resultado = gen.gerar_capitulo(
            capitulo=capitulo_do_mapa,
            total_capitulos=5,
            curso="...", uc="...", ...
        )
    """

    def __init__(self, provider):
        self.provider = provider

    def gerar_capitulo(
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
        """
        Gera o HTML de um capítulo específico.

        Args:
            capitulo:           Dicionário do capítulo vindo do mapa pedagógico
            total_capitulos:    Total de capítulos da apostila (para contexto)
            curso/uc/bloco:     Contexto educacional
            titulo_apostila:    Título geral da apostila
            extrato_uc:         Extrato pedagógico da UC
            resumo_saep:        Análise SAEP compacta
            observacoes:        Instrução do professor
            titulos_anteriores: Lista de títulos já gerados (para evitar repetição)

        Returns:
            ok(html=str, numero=int, titulo=str, tokens=int, palavras=int)
            erro("mensagem")
        """
        numero   = capitulo.get("numero", 1)
        titulo   = capitulo.get("titulo", f"Capítulo {numero}")
        subtit   = capitulo.get("subtitulo", "")
        topicos  = capitulo.get("topicos", [])
        profund  = capitulo.get("profundidade", "aplicacao")
        saep_rel = capitulo.get("saep_relevante", False)
        conexao  = capitulo.get("conexao_anterior", None)

        logger.info(f"Gerando Capítulo {numero}/{total_capitulos}: {titulo}")

        # Formata os tópicos para o prompt
        topicos_fmt = "\n".join(f"  • {t}" for t in topicos) if topicos else "  • Conteúdo do capítulo"

        # Texto de conexão com capítulo anterior
        conexao_txt = ""
        if conexao:
            conexao_txt = f"CONEXÃO COM CAPÍTULO ANTERIOR:\n{conexao}\n"

        # Instrução SAEP específica para capítulos relevantes
        saep_instrucao = ""
        if saep_rel:
            saep_instrucao = (
                "ATENÇÃO SAEP: Este capítulo tem ALTA relevância para avaliações.\n"
                "Adicione boxes SAEP nos tópicos mais cobrados.\n"
                "Para cada tópico SAEP: o que saber, como costuma cair, erro mais comum.\n"
            )

        # Resumo dos capítulos anteriores (apenas títulos — não repete conteúdo)
        ant_txt = ""
        if titulos_anteriores:
            ant_txt = "Capítulos já cobertos (NÃO repita):\n" + "\n".join(
                f"  - {t}" for t in titulos_anteriores
            )
        else:
            ant_txt = "Este é o primeiro capítulo."

        # Limita o extrato_uc para este capítulo (tokens são preciosos aqui)
        extrato_cap = extrato_uc[:3500]
        saep_cap    = resumo_saep[:1500] if resumo_saep else ""
        obs_txt     = f"INSTRUÇÃO DO PROFESSOR: {observacoes}" if observacoes else ""

        saep_resumo_bloco = f"CONTEXTO SAEP:\n{saep_cap}" if saep_cap else ""

        prompt = PROMPT_CAPITULO.format(
            curso                  = curso,
            uc                     = uc,
            titulo_apostila        = titulo_apostila,
            bloco_aula             = bloco_aula,
            numero                 = numero,
            total                  = total_capitulos,
            titulo                 = titulo,
            subtitulo              = subtit,
            topicos                = topicos_fmt,
            profundidade           = profund,
            saep_relevante         = "Sim — adicione boxes SAEP" if saep_rel else "Não prioritário",
            conexao_anterior_texto = conexao_txt,
            extrato_uc             = extrato_cap,
            saep_resumo            = saep_resumo_bloco,
            obs_professor          = obs_txt,
            capitulos_anteriores   = ant_txt,
            saep_instrucao         = saep_instrucao,
        )

        t0 = time.time()
        resultado_ia = self.provider.gerar(prompt)
        tempo_cap    = round(time.time() - t0, 1)

        if not resultado_ia.get("sucesso"):
            logger.error(f"Falha no Capítulo {numero}: {resultado_ia.get('erro')}")
            return erro(
                f"Falha ao gerar Capítulo {numero} ({titulo}): "
                f"{resultado_ia.get('erro', 'Erro desconhecido')}"
            )

        html_cap    = resultado_ia.get("conteudo", "")
        tokens_cap  = resultado_ia.get("tokens_usados",  0)
        tokens_in   = resultado_ia.get("tokens_entrada", 0)
        tokens_out  = resultado_ia.get("tokens_saida",   0)
        palavras    = resultado_ia.get("palavras",        0)

        logger.info(
            f"Capítulo {numero} gerado | {tempo_cap}s | "
            f"Tokens: in={tokens_in} out={tokens_out} | "
            f"Palavras: {palavras} | HTML: {len(html_cap)} chars"
        )

        return ok(
            html        = html_cap,
            numero      = numero,
            titulo      = titulo,
            tokens      = tokens_cap,
            tokens_in   = tokens_in,
            tokens_out  = tokens_out,
            palavras    = palavras,
            tempo       = tempo_cap,
        )
