"""
diagnostico.py — Rode este script na raiz do projeto:
    python diagnostico.py

Ele vai identificar exatamente por que a API Key está falhando.
"""

import os
import sys

print("\n" + "═" * 55)
print("  DIAGNÓSTICO — API Key Gemini")
print("═" * 55)

# ── 1. Verifica se o .env existe ──────────────────────────────
env_path = os.path.join(os.getcwd(), ".env")
print(f"\n📁 Pasta atual : {os.getcwd()}")
print(f"📄 .env existe : {os.path.exists(env_path)}")

if not os.path.exists(env_path):
    print("\n❌ PROBLEMA: arquivo .env não encontrado nesta pasta.")
    print("   Certifique-se de rodar o script NA MESMA PASTA que o app.py")
    sys.exit(1)

# ── 2. Lê o .env manualmente e mostra o que encontra ─────────
print("\n── Conteúdo relevante do .env ──")
chave_encontrada = False
with open(env_path, "r", encoding="utf-8") as f:
    for i, linha in enumerate(f, 1):
        linha_orig = linha
        linha = linha.rstrip("\n")
        if "GEMINI_API_KEY" in linha or "AI_PROVIDER" in linha:
            # Mostra a linha (ocultando parte da chave)
            if "GEMINI_API_KEY" in linha and "=" in linha:
                chave_encontrada = True
                partes = linha.split("=", 1)
                valor  = partes[1] if len(partes) > 1 else ""
                valor_limpo = valor.strip()

                print(f"\n   Linha {i}: {partes[0]}=***")
                print(f"   Tamanho original  : {len(valor)} chars")
                print(f"   Tamanho sem espaços: {len(valor_limpo)} chars")

                # Detecta problemas comuns
                if valor != valor_limpo:
                    print("   ⚠️  PROBLEMA: há espaços antes ou depois da chave!")
                    print(f"      Valor com espaços: '{valor}'")

                if valor.startswith('"') or valor.startswith("'"):
                    print("   ⚠️  PROBLEMA: chave está entre aspas — remova as aspas!")

                if not valor_limpo.startswith("AIzaSy"):
                    print("   ⚠️  AVISO: chave não começa com 'AIzaSy' — verifique se copiou corretamente")
                else:
                    print(f"   ✅ Prefixo correto: AIzaSy...")
                    print(f"   ✅ Primeiros chars: {valor_limpo[:12]}...")

                if "\r" in linha_orig:
                    print("   ⚠️  PROBLEMA: arquivo tem quebras de linha Windows (\\r\\n) — pode causar erro")
            else:
                print(f"   Linha {i}: {linha}")

if not chave_encontrada:
    print("\n❌ PROBLEMA: GEMINI_API_KEY não encontrada no .env!")
    print("   Adicione: GEMINI_API_KEY=AIzaSy_sua_chave_aqui")

# ── 3. Carrega com python-dotenv e testa ──────────────────────
print("\n── Teste com python-dotenv ──")
try:
    from dotenv import load_dotenv, dotenv_values
    load_dotenv(override=True)

    valores = dotenv_values(env_path)
    chave_dotenv = valores.get("GEMINI_API_KEY", "")

    if chave_dotenv:
        print(f"   ✅ dotenv leu a chave: {chave_dotenv[:12]}... ({len(chave_dotenv)} chars)")
    else:
        print("   ❌ dotenv não conseguiu ler GEMINI_API_KEY")

    chave_env = os.getenv("GEMINI_API_KEY", "")
    if chave_env:
        print(f"   ✅ os.getenv leu a chave: {chave_env[:12]}... ({len(chave_env)} chars)")
    else:
        print("   ❌ os.getenv retornou vazio após load_dotenv()")

except ImportError:
    print("   ❌ python-dotenv não instalado: pip install python-dotenv")

# ── 4. Testa a chave diretamente na API ───────────────────────
print("\n── Teste direto na API Gemini ──")
try:
    import google.generativeai as genai

    chave = os.getenv("GEMINI_API_KEY", "").strip()
    if not chave:
        print("   ❌ Chave vazia — não é possível testar")
    else:
        genai.configure(api_key=chave)
        modelo = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=genai.GenerationConfig(max_output_tokens=5)
        )
        resposta = modelo.generate_content("Responda: OK")
        if resposta.text:
            print(f"   ✅ API FUNCIONANDO! Resposta: {resposta.text.strip()}")
        else:
            print("   ⚠️  API respondeu mas sem texto")

except Exception as e:
    erro_str = str(e)
    print(f"   ❌ Erro na API: {erro_str[:200]}")

    if "api_key_invalid" in erro_str.lower() or "api key not valid" in erro_str.lower():
        print("\n   CAUSA PROVÁVEL:")
        print("   1. A chave foi copiada com espaço ou caractere invisível")
        print("   2. A chave ainda não foi ativada (aguarde 1-2 min após criar)")
        print("   3. A chave foi criada num projeto diferente do que está ativo")
        print("\n   SOLUÇÃO:")
        print("   → Acesse: https://aistudio.google.com/app/apikey")
        print("   → Crie uma NOVA chave")
        print("   → Copie com Ctrl+C diretamente do site")
        print("   → Cole no .env SEM espaços: GEMINI_API_KEY=AIzaSy...")

    elif "quota" in erro_str.lower():
        print("   CAUSA: Cota esgotada — aguarde ou verifique seu plano")

print("\n" + "═" * 55 + "\n")
