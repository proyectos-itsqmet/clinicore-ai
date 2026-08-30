import json
import os
import uuid

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, Response, jsonify, request     
from flask_cors import CORS                           

import agente                                            

app = Flask(__name__)
CORS(app, origins=os.getenv("CORS_ORIGINS", "*").split(","))

def evento_sse(tipo, datos_evento):
    return f"event: {tipo}\ndata: {json.dumps(datos_evento, ensure_ascii=False)}\n\n"

CABECERAS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}

@app.route("/", methods=["GET"])
def estado():
    return jsonify({
        "estado": "ok",
        "modelo": agente.MODELO,
        "servicio": "Interpretador cualitativo de Escalas Wechsler"
    })

@app.route("/chat", methods=["POST"])
def chat():
    cuerpo = request.get_json(silent=True) or {}
    
    # La aplicación web puede enviar los datos en 'mensaje' o 'datos'
    datos_paciente = cuerpo.get("mensaje") or cuerpo.get("datos")
    session_id = cuerpo.get("session_id") or uuid.uuid4().hex

    if not datos_paciente:
        return jsonify({"error": "Faltan los datos del paciente"}), 400

    # Si nos llega como objeto JSON, lo pasamos a texto stringificado
    if isinstance(datos_paciente, dict):
        datos_paciente = json.dumps(datos_paciente, ensure_ascii=False)

    def generar():
        yield evento_sse("session", {"session_id": session_id})

        for tipo, texto in agente.generar_interpretacion(datos_paciente):
            if tipo == "texto":
                yield evento_sse("delta", {"texto": texto})
            elif tipo == "fin":
                yield evento_sse("done", {"texto": texto})
            elif tipo == "error":
                yield evento_sse("error", {"mensaje": texto})

    return Response(generar(), mimetype="text/event-stream", headers=CABECERAS)

if __name__ == "__main__":
    puerto = int(os.getenv("PORT", "8000"))
    print(f"API Escalas Wechsler en http://localhost:{puerto}")
    print(f"Modelo:       {agente.MODELO}")
    app.run(host="0.0.0.0", port=puerto, threaded=True)
