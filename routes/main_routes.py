"""routes/main_routes.py  (V1.8)"""
import os
from flask import Blueprint, render_template, current_app, send_from_directory
from modules.readers.course_reader import CourseReader
from modules.exporters.docx_builder import DocxBuilder

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def index():
    reader = CourseReader(pasta_cursos=current_app.config["CURSOS_FOLDER"])
    return render_template("index.html", cursos=reader.listar_cursos())

@main_bp.route("/historico")
def historico():
    exp = DocxBuilder(pasta_output=current_app.config.get("OUTPUT_FOLDER","output"))
    return render_template("historico.html", apostilas=exp.listar())

@main_bp.route("/download/<nome_arquivo>")
def download(nome_arquivo):
    pasta = current_app.config.get("OUTPUT_FOLDER","output")
    return send_from_directory(os.path.abspath(pasta), nome_arquivo,
                               as_attachment=True, download_name=nome_arquivo)
