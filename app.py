"""GERADOR DE APOSTILAS SENAI — V1.8 | Gemini JSON → DOCX"""
import os, logging
from flask import Flask
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

from routes.main_routes import main_bp
from routes.api_routes  import api_bp

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(
        SECRET_KEY         = os.getenv("SECRET_KEY","senai-v18-2024"),
        MAX_CONTENT_LENGTH = 50*1024*1024,
        UPLOAD_FOLDER      = "uploads",
        OUTPUT_FOLDER      = "output",
        CURSOS_FOLDER      = os.getenv("CURSOS_FOLDER","Cursos"),
        SAEP_FOLDER        = os.getenv("SAEP_FOLDER","SAEP"),
        PROMPT_MESTRE_PATH = os.getenv("PROMPT_MESTRE_PATH","Prompt Apostilas SENAI.docx"),
        AI_PROVIDER        = os.getenv("AI_PROVIDER","gemini"),
    )
    for p in [app.config["UPLOAD_FOLDER"],app.config["OUTPUT_FOLDER"],
              app.config["CURSOS_FOLDER"],app.config["SAEP_FOLDER"]]:
        os.makedirs(p, exist_ok=True)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    return app

if __name__ == "__main__":
    app = create_app()
    print("\n" + "═"*62)
    print("  GERADOR DE APOSTILAS SENAI  —  V1.8")
    print("  Arquitetura: Gemini JSON → python-docx → DOCX")
    print("═"*62)
    print("  Acesse : http://localhost:5000")
    print("  Modelo :", os.getenv("GEMINI_MODEL","gemini-2.5-flash"))
    print("  Saída  : arquivo .docx pronto para download")
    print("═"*62+"\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
