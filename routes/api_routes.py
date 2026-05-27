"""routes/api_routes.py  (V1.8) — Entrega DOCX, endpoint DELETE"""

import os
import logging
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from werkzeug.utils import secure_filename

from modules.readers.course_reader     import CourseReader
from modules.readers.saep_reader       import SAEPReader
from modules.services.apostila_service import ApostilaService
from modules.exporters.docx_builder    import DocxBuilder
from modules.utils.response            import extrair

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)
EXT_OK = {"pdf", "docx", "txt"}

def _ext_ok(nome):
    return "." in nome and nome.rsplit(".",1)[1].lower() in EXT_OK


@api_bp.route("/status")
def status():
    try:
        return jsonify(ApostilaService(current_app.config).verificar_status())
    except Exception as e:
        return jsonify({"conectado": False, "mensagem": str(e)}), 500


@api_bp.route("/ucs")
def listar_ucs():
    curso = request.args.get("curso","").strip()
    if not curso:
        return jsonify({"erro":"Parâmetro 'curso' obrigatório"}), 400
    r = CourseReader(pasta_cursos=current_app.config["CURSOS_FOLDER"])
    p = r.listar_ucs(curso)
    return jsonify({"curso":curso,"ucs_pastas":p,
                    "ucs_formatadas":[r.formatar_nome(u) for u in p],"total":len(p)})


@api_bp.route("/uc/info")
def info_uc():
    curso = request.args.get("curso","").strip()
    uc    = request.args.get("uc","").strip()
    if not curso or not uc:
        return jsonify({"erro":"Parâmetros obrigatórios"}), 400
    reader   = CourseReader(pasta_cursos=current_app.config["CURSOS_FOLDER"])
    saep_rdr = SAEPReader(pasta_saep=current_app.config.get("SAEP_FOLDER","SAEP"))
    info     = reader.info_uc(curso, uc)
    avisos   = list(extrair(info,"avisos",[]))
    tem_saep = saep_rdr.curso_tem_saep(curso)
    if not tem_saep:
        avisos.append(f"SAEP não encontrado para '{curso}'.")
    return jsonify({"curso":extrair(info,"curso"),"uc":extrair(info,"uc"),
                    "status":extrair(info,"status"),"tem_pdf":extrair(info,"tem_arquivo"),
                    "tem_saep":tem_saep,"avisos":avisos})


@api_bp.route("/gerar", methods=["POST"])
def gerar():
    curso  = request.form.get("curso","").strip()
    uc     = request.form.get("uc","").strip()
    bloco  = request.form.get("bloco_aula","").strip()
    obs    = request.form.get("informacoes_adicionais","").strip()
    prof   = request.form.get("professor","").strip()

    faltando = [f for f,v in [("curso",curso),("uc",uc),("bloco_aula",bloco)] if not v]
    if faltando:
        return jsonify({"sucesso":False,"erro":f"Campos obrigatórios: {', '.join(faltando)}"}), 400

    caminho_plano = ""
    if "plano_aula" in request.files:
        arq = request.files["plano_aula"]
        if arq and arq.filename:
            if not _ext_ok(arq.filename):
                return jsonify({"sucesso":False,"erro":"Use PDF, DOCX ou TXT"}), 400
            nome_s = secure_filename(arq.filename)
            caminho_plano = os.path.join(current_app.config["UPLOAD_FOLDER"], nome_s)
            arq.save(caminho_plano)

    try:
        svc = ApostilaService(config=current_app.config)
        res = svc.gerar(curso=curso, uc=uc, bloco_aula=bloco,
                        caminho_plano=caminho_plano,
                        observacoes=obs or None, professor=prof or None)
        if res.get("sucesso"):
            return jsonify({"sucesso":True,
                            "apostila": res["dados"].get("apostila",{}),
                            "metricas": res["dados"].get("metricas",{}),
                            "avisos":   res["dados"].get("avisos",[]),
                            "erro":None})
        return jsonify({"sucesso":False,"erro":res.get("erro")}), 500
    except Exception as e:
        logger.error(f"Erro /gerar: {e}", exc_info=True)
        return jsonify({"sucesso":False,"erro":str(e)}), 500
    finally:
        if caminho_plano and os.path.exists(caminho_plano):
            try: os.remove(caminho_plano)
            except: pass


@api_bp.route("/apostilas")
def listar_apostilas():
    exp = DocxBuilder(pasta_output=current_app.config.get("OUTPUT_FOLDER","output"))
    apostilas = exp.listar()
    for a in apostilas: a.pop("caminho", None)
    return jsonify({"apostilas":apostilas,"total":len(apostilas)})


@api_bp.route("/apostilas/<nome_arquivo>", methods=["DELETE"])
def deletar_apostila(nome_arquivo):
    exp = DocxBuilder(pasta_output=current_app.config.get("OUTPUT_FOLDER","output"))
    res = exp.deletar(nome_arquivo)
    if res.get("sucesso"):
        return jsonify({"sucesso":True,"mensagem":extrair(res,"mensagem","Removido")}), 200
    return jsonify({"sucesso":False,"erro":res.get("erro")}), 400
