# Correções — Gerador de Apostilas SENAI

Este pacote é o seu projeto com a correção do problema dos **capítulos vazios** já aplicada,
mais um script para testar localmente sem gastar API.

---

## O que estava acontecendo

Eram **três bugs em série**:

1. **Resposta do Gemini truncada.** O `gemini-2.5-flash` tem "thinking" ligado por
   padrão, que consome parte do orçamento de 16.000 tokens *antes* de escrever o JSON.
   Somado a capítulos longos (várias seções de 400+ palavras, código, tabelas, boxes),
   o JSON era cortado no meio — e o provider nem detectava (não checava `finish_reason`).

2. **O parser transformava "truncado" em "vazio".** Quando o JSON vinha cortado, o reparo
   antigo só fechava chaves/colchetes (não fechava strings abertas). O objeto principal
   não decodificava, e o código acabava pegando um *fragmento interno* (um box, uma seção
   solta) que por acaso tinha `"titulo"` e devolvia como se fosse o capítulo inteiro —
   um dicionário com título mas **sem `secoes`**. A validação rejeitava ("Sem seções").

3. **Capítulo válido descartado na leitura.** O `apostila_service` lia o resultado com
   `extrair(res_cap, "dados")`, que procura uma chave `"dados"` *dentro* do capítulo
   (não existe) e devolvia `{}`. Todo capítulo era rejeitado com "Título genérico: ''".

---

## Arquivos alterados

- `providers/gemini_provider.py`
  - Ativado JSON mode (`response_mime_type="application/json"`) — sem markdown/texto extra.
  - Teto de saída subido para 32.000 tokens (o 2.5-flash suporta até 65.536).
  - Detecção de corte por limite de tokens (`finish_reason == MAX_TOKENS`) com aviso no log.

- `modules/services/content_generator.py`
  - Parser só aceita como capítulo um objeto com `secoes` não-vazio (bloqueia fragmentos).
  - Novo `_salvar_json_truncado`: recupera o máximo de seções completas de um JSON cortado.
  - Cai no fallback de texto só quando não dá pra recuperar nenhuma seção.

- `modules/services/apostila_service.py`
  - Leitura corrigida: `dados_cap = res_cap.get("dados", {})`.

- `testar_correcao.py` *(novo, na raiz)* — teste local sem API.

---

## Antes de testar com o Gemini de verdade

Abra o arquivo `.env` e confira a sua chave:

```
GEMINI_API_KEY=...   # precisa ser a sua chave real (começa com AIza...)
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MAX_TOKENS=32000
```

A chave que estava no `.env` enviado não parece uma chave válida do Gemini.
Pegue a sua em https://aistudio.google.com/app/apikey e cole ali.

---

## Como rodar

Instalar dependências (uma vez):

```
pip install -r requirements.txt
```

### 1) Teste local (sem API, recomendado primeiro)

```
python testar_correcao.py
```

Roda o pipeline real com um provider falso. Dois níveis:
- **Nível A:** alimenta o parser com 6 respostas problemáticas (JSON truncado, texto
  antes/depois, cerca markdown, resposta cortada) e confere que nenhum capítulo sai vazio.
- **Nível B:** roda o `ApostilaService.gerar()` inteiro (mapa → capítulos → DOCX), com um
  capítulo truncado de propósito, e gera um DOCX real em `output_teste/`.

Esperado: `7/7 testes passaram`.

### 2) Teste real com o Gemini

```
python app.py
```

Abra o navegador no endereço indicado, escolha curso/UC/bloco e gere a apostila.
O `.docx` sai na pasta `output/`. Se algum capítulo vier truncado, o log mostra
`finish_reason=MAX_TOKENS` — nesse caso aumente `GEMINI_MAX_TOKENS` no `.env`.

---

## Comportamento esperado após a correção

| Situação da resposta do Gemini | Antes        | Agora                              |
|--------------------------------|--------------|------------------------------------|
| JSON completo                  | OK           | OK (todas as seções)               |
| JSON truncado (40–99%)         | capítulo vazio | recupera as seções completas     |
| JSON cortado muito cedo (<30%) | capítulo vazio | fallback de texto com conteúdo    |
| Texto antes/depois ou ```json  | às vezes vazio | parseia normalmente              |
