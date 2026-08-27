import json
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, Response, jsonify, request     
from flask_cors import CORS                           

import agente                                            
import datos                                             

app = Flask(__name__)

CORS(app, origins=os.getenv("CORS_ORIGINS", "*").split(","))

conversaciones = {}


def obtener_conversacion(session_id):
    if session_id not in conversaciones:
        conversaciones[session_id] = []
    return conversaciones[session_id]


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
        "modelo_audio": agente.MODELO_AUDIO,
        "backend_qms": datos.QMS_URL,
        "hoy": datos.fecha_hoy_texto(),
    })


@app.route("/chat", methods=["POST"])
def chat():
    cuerpo = request.get_json(silent=True) or {}
    mensaje = (cuerpo.get("mensaje") or "").strip()
    session_id = cuerpo.get("session_id") or uuid.uuid4().hex

    if not mensaje:
        return jsonify({"error": "Falta el mensaje"}), 400
    if len(mensaje) > 1000:
        return jsonify({"error": "El mensaje es demasiado largo"}), 400

    messages = obtener_conversacion(session_id)
    agente.agregar_mensaje(messages, "user", mensaje)

    def generar():
        yield evento_sse("session", {"session_id": session_id})

        for tipo, texto in agente.enviar_mensajes(messages):
            if tipo == "aviso":
                yield evento_sse("status", {"texto": texto})
            elif tipo == "texto":
                yield evento_sse("delta", {"texto": texto})
            elif tipo == "fin":
                yield evento_sse("done", {"texto": texto})
            elif tipo == "error":
                yield evento_sse("error", {"mensaje": texto})

    return Response(generar(), mimetype="text/event-stream", headers=CABECERAS)


@app.route("/chat/audio", methods=["POST"])
def chat_audio():
    if "file" not in request.files:
        return jsonify({"error": "Falta el archivo de audio (campo 'file')"}), 400

    archivo = request.files["file"]
    contenido_audio = archivo.read()
    tipo_audio = archivo.mimetype
    nombre_audio = archivo.filename

    session_id = request.form.get("session_id") or uuid.uuid4().hex
    messages = obtener_conversacion(session_id)

    def generar():
        yield evento_sse("session", {"session_id": session_id})
        yield evento_sse("status", {"texto": "Transcribiendo tu audio..."})

        try:
            texto = agente.transcribir(contenido_audio, tipo_audio, nombre_audio)
        except ValueError as e:
            yield evento_sse("error", {"mensaje": str(e)})
            return
        except Exception as e:
            yield evento_sse("error", {"mensaje": f"No se pudo transcribir ({type(e).__name__})."})
            return

        yield evento_sse("transcripcion", {"texto": texto})

        agente.agregar_mensaje(messages, "user", texto)

        for tipo, contenido in agente.enviar_mensajes(messages):
            if tipo == "aviso":
                yield evento_sse("status", {"texto": contenido})
            elif tipo == "texto":
                yield evento_sse("delta", {"texto": contenido})
            elif tipo == "fin":
                yield evento_sse("done", {"texto": contenido})
            elif tipo == "error":
                yield evento_sse("error", {"mensaje": contenido})

    return Response(generar(), mimetype="text/event-stream", headers=CABECERAS)


@app.route("/chat/reset", methods=["POST"])
def reset():
    cuerpo = request.get_json(silent=True) or {}
    session_id = cuerpo.get("session_id")
    if session_id:
        conversaciones.pop(session_id, None)
    return jsonify({"estado": "ok"})


if __name__ == "__main__":
    puerto = int(os.getenv("PORT", "8000"))
    print(f"Asistente ClinicORE en http://localhost:{puerto}")
    print(f"Backend QMS:  {datos.QMS_URL}")
    print(f"Modelo:       {agente.MODELO}")
    print(f"Hoy es:       {datos.fecha_hoy_texto()}")
    app.run(host="0.0.0.0", port=puerto, threaded=True)
