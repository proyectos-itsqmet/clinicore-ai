"""
app.py — Servidor web del asistente virtual, con Flask.

Es la parte de la clase de despliegue: crear una API con Flask para que el
frontend pueda usar el modelo. Aqui en lugar de servir el modelo de imagenes,
sirve el agente de texto y audio.

Rutas:
    GET  /              estado del servicio
    POST /chat          mensaje de texto  -> respuesta en streaming
    POST /chat/audio    audio grabado     -> transcripcion + respuesta
    POST /chat/reset    borra la conversacion de una sesion

Para levantarlo:
    python app.py
"""

import json
import os
import uuid

from dotenv import load_dotenv

# Se cargan las variables del archivo .env ANTES de importar los otros
# modulos, porque ellos leen os.getenv() al importarse.
load_dotenv()

from flask import Flask, Response, jsonify, request      # noqa: E402
from flask_cors import CORS                              # noqa: E402

import agente                                            # noqa: E402
import datos                                             # noqa: E402

app = Flask(__name__)

# Permiso para que Angular (puerto 4200) y Flutter web puedan llamar a esta
# API desde el navegador.
CORS(app, origins=os.getenv("CORS_ORIGINS", "*").split(","))


# Las conversaciones se guardan en memoria: {session_id: [mensajes]}.
# Cada paciente tiene su propio historial, asi el agente recuerda lo que se
# hablo antes. Es el "messages" del notebook, uno por sesion.
conversaciones = {}


def obtener_conversacion(session_id):
    if session_id not in conversaciones:
        conversaciones[session_id] = []
    return conversaciones[session_id]


def evento_sse(tipo, datos_evento):
    """Arma un evento en formato Server-Sent Events.

    Es el formato que el navegador entiende para recibir datos de a poco:

        event: texto
        data: {"texto": "Hola"}

    """
    return f"event: {tipo}\ndata: {json.dumps(datos_evento, ensure_ascii=False)}\n\n"


# Cabeceras necesarias para que el streaming llegue fragmento por fragmento.
# Sin "X-Accel-Buffering: no", nginx guarda toda la respuesta y la manda junta
# al final, y se pierde el efecto de streaming aunque el servidor lo haga bien.
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
    """Mensaje de texto del paciente."""
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
    """Audio grabado por el paciente.

    Se transcribe primero y el texto entra al mismo agente que el chat
    escrito. El audio no cambia el agente: es solo un traductor en la entrada.
    """
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

        # Se le manda al frontend lo que dijo el paciente, para mostrarlo en
        # el chat como si lo hubiera escrito.
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
    """Borra la conversacion de una sesion."""
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
    # threaded=True para poder atender a varios pacientes a la vez.
    app.run(host="0.0.0.0", port=puerto, threaded=True)
