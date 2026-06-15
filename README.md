# Gerador de Apostilas SENAI — IA Educacional
## Versao 1.5 — Google Gemini 2.5 Flash | Foco em Profundidade Pedagogica

---

## O que ha de novo na V1.5

- **Provider principal**: Google Gemini 2.5 Flash (substituiu Groq)
- **Apostilas sem exercicios automaticos**: foco 100% em ensinar com profundidade
- **8.000 tokens de saida**: apostilas muito mais completas e detalhadas
- **Controle de finalizacao**: o HTML nunca e cortado abruptamente
- **Prompt pedagogico reformulado**: 3 camadas por conceito (fundamentos → aplicacao → mercado)

---

## Estrutura do Projeto

```
senai_gerador/
│
├── app.py                         <- Ponto de entrada Flask (V1.5)
├── requirements.txt               <- google-generativeai como principal
├── .env.exemplo                   <- Renomeie para .env
├── .gitignore
├── "Prompt Apostilas SENAI.docx"  <- Prompt Mestre (ja incluido)
│
├── providers/
│   ├── base_provider.py           <- Contrato abstrato
│   ├── gemini_provider.py         <- PRINCIPAL V1.5 (Gemini 2.5 Flash)
│   ├── groq_provider.py           <- Backup (opcional)
│   └── provider_manager.py        <- Gerenciador automatico
│
├── modules/
│   ├── readers/
│   │   ├── document_reader.py     <- TXT / DOCX / PDF
│   │   ├── course_reader.py       <- Estrutura Cursos/
│   │   └── saep_reader.py         <- Recursivo: Diagnostica + Pratica
│   ├── analyzers/
│   │   └── content_extractor.py   <- Extracao pedagogica
│   ├── builders/
│   │   └── context_builder.py     <- Prompt V1.5 (sem exercicios)
│   ├── exporters/
│   │   └── html_exporter.py       <- HTML profissional AVA/SENAI
│   ├── services/
│   │   └── apostila_service.py    <- Orquestrador (pipeline 7 etapas)
│   └── utils/
│       └── response.py            <- Retornos padronizados
│
├── routes/
│   ├── main_routes.py
│   └── api_routes.py
│
├── templates/
│   ├── index.html
│   └── historico.html
│
├── Cursos/                        <- Seus PDFs de UC
│   └── Nome_Curso/
│       └── Nome_UC/
│           └── qualquer_nome.pdf
│
├── SAEP/                          <- Historico de avaliacoes
│   └── Nome_Curso/
│       ├── Diagnostica/
│       │   └── 2024/
│       │       └── prova.pdf
│       └── Pratica/
│           └── 2024/
│               └── checklist.docx
│
└── output/                        <- Apostilas geradas
```

---

## Instalacao Rapida

### 1. Ambiente virtual (recomendado)
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Dependencias
```bash
pip install -r requirements.txt
```

### 3. Configure a chave Gemini
```bash
cp .env.exemplo .env
```

Edite o `.env`:
```
GEMINI_API_KEY=AIzaSy_sua_chave_aqui
AI_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MAX_TOKENS=8000
```

**Como obter a chave Gemini (gratis):**
1. Acesse https://aistudio.google.com/app/apikey
2. Login com conta Google
3. Create API Key
4. Cole no .env

### 4. Coloque o Prompt Mestre na raiz
```
"Prompt Apostilas SENAI.docx"   <- ja incluido no ZIP
```

### 5. Organize os documentos
```
Cursos/
└── Desenvolvimento_de_Sistemas/
    └── Backend/
        └── UC_Backend.pdf

SAEP/
└── Desenvolvimento_de_Sistemas/
    ├── Diagnostica/
    │   └── 2024/
    │       └── prova.pdf
    └── Pratica/
        └── 2024/
            └── checklist.docx
```

### 6. Inicie
```bash
python app.py
# Acesse: http://localhost:5000
```

---

## Git — Versionamento

```bash
# Primeira vez
git init
git add .
git commit -m "feat: Gerador SENAI V1.5 — Gemini 2.5 Flash"

# Criar repo no GitHub e subir
git remote add origin https://github.com/seu-usuario/gerador-apostilas-senai.git
git branch -M main
git push -u origin main

# Atualizacoes futuras
git add .
git commit -m "feat: descricao da mudanca"
git push
```

---

## Trocar de Provider

Edite apenas o `.env`:
```bash
# Gemini (padrao V1.5)
AI_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...

# Groq (alternativa)
AI_PROVIDER=groq
GROQ_API_KEY=gsk_...
```

Nenhum arquivo Python precisa ser alterado.

---

## Roadmap

| Versao | Funcionalidade |
|--------|---------------|
| V1.0 | Pipeline base |
| V1.1 | SAEP recursivo |
| V1.2 | Multi-provider + Groq |
| V1.3 | Pipeline inteligente |
| V1.4 | Qualidade pedagogica + HTML profissional |
| V1.5 | Gemini 2.5 Flash + apostilas sem exercicios |
| V1.6 | Cache MD5 por arquivo |
| V2.0 | Banco SQLite + historico |
| V2.1 | Exportacao PDF |
| V3.0 | RAG com ChromaDB |
| V4.0 | Sistema multiagente |
