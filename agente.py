import json
import os

from openai import OpenAI

import datos


PROYECTO = os.getenv("OPENAI_PROJECT") or None

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), project=PROYECTO)


MODELO = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
MODELO_AUDIO = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe")

tools = [
    {
        "type": "function",
        "name": "ver_servicios",
        "description": "Lista los servicios y examenes de la clinica con su precio. "
                       "Usar cuando el paciente pregunte que servicios hay o cuanto cuesta algo.",
        "parameters": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Filtro opcional por nombre del servicio"},
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "ver_doctores",
        "description": "Lista los medicos de la clinica con su especialidad. "
                       "Usar cuando el paciente pregunte que especialidades hay.",
        "parameters": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Filtro opcional por nombre del medico"},
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "ver_sedes",
        "description": "Lista las sedes de la clinica con su direccion. "
                       "Usar cuando el paciente pregunte donde queda la clinica.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "type": "function",
        "name": "ver_disponibilidad",
        "description": "Consulta los turnos LIBRES de la agenda, siempre a futuro. "
                       "Usar cuando el paciente pregunte por turnos, citas u horarios. "
                       "Si devuelve una lista vacia significa que NO hay turnos: "
                       "en ese caso hay que decirlo, no inventar horarios.",
        "parameters": {
            "type": "object",
            "properties": {
                "servicio": {"type": "string", "description": "Nombre del servicio o examen"},
                "doctor": {"type": "string", "description": "Nombre o apellido del medico"},
                "desde": {"type": "string", "description": "Fecha inicial, formato AAAA-MM-DD"},
                "hasta": {"type": "string", "description": "Fecha final, formato AAAA-MM-DD"},
            },
            "required": [],
        },
    },
]

funciones = {
    "ver_servicios": datos.ver_servicios,
    "ver_doctores": datos.ver_doctores,
    "ver_sedes": datos.ver_sedes,
    "ver_disponibilidad": datos.ver_disponibilidad,
}

avisos = {
    "ver_servicios": "Revisando el catalogo de servicios...",
    "ver_doctores": "Consultando los medicos...",
    "ver_sedes": "Buscando las sedes...",
    "ver_disponibilidad": "Consultando la agenda...",
}

def construir_instrucciones():
    return f"""Eres el asistente virtual de ClinicORE, una clinica medica.
Atiendes a pacientes por el chat de la pagina web y de la aplicacion movil.

# QUE DIA ES HOY
Hoy es {datos.fecha_hoy_texto()} (en formato ISO: {datos.fecha_hoy().isoformat()}).
Usa SIEMPRE esta fecha como referencia. Si el paciente dice "hoy", "manana" o
"esta semana", calculalo desde esta fecha y de ninguna otra.

# TU FUNCION ES INFORMAR
Das informacion sobre servicios, precios, especialidades, medicos, sedes y
turnos disponibles.

NO agendas, NO cancelas y NO modificas turnos. No tienes forma de hacerlo.
Cuando el paciente quiera reservar, dale los datos del turno y decile:
"Para reservar puedes hacerlo desde la seccion Agendar del sitio web o
llamando a recepcion."

# REGLAS DE EXACTITUD (las mas importantes)
1. Todo dato concreto (una fecha, una hora, un precio, un nombre de medico,
   una direccion) tiene que venir de una herramienta que acabas de ejecutar.
2. Si no ejecutaste la herramienta, no tienes el dato. No lo estimes ni lo
   supongas.
3. Si una herramienta devuelve una lista vacia, no hay disponibilidad. Decilo
   y ofrece buscar otra fecha. Nunca completes el vacio con horarios
   inventados.
4. Si una herramienta devuelve un error, decilo con naturalidad: "No pude
   consultar la agenda en este momento, intenta en unos minutos."
5. Nunca digas un precio sin haber consultado ver_servicios.

# LIMITES
No diagnosticas, no interpretas sintomas y no recomiendas medicamentos. Si el
paciente cuenta un sintoma, puedes orientarlo sobre que especialidad suele
atender eso y mostrarle los turnos, aclarando que la valoracion la hace el
medico.

Si el mensaje parece una urgencia (dolor en el pecho, falta de aire, sangrado
abundante, perdida de conciencia), deja todo lo demas y responde primero:
"Por lo que me contas, no esperes un turno: anda ya a emergencias o llama al 911."

# NO PREGUNTES DE MAS
Si el paciente pregunta por turnos sin dar detalles ("que turnos hay?",
"cuando puedo ir?"), NO le pidas que aclare primero: ejecuta
ver_disponibilidad sin filtros, muestrale los proximos turnos y RECIEN
despues ofrecele filtrar por servicio, medico o fecha.

Solo pregunta cuando la respuesta cambie de verdad segun lo que conteste.
Mostrar primero y refinar despues es mejor que dejar al paciente respondiendo
un cuestionario.

# COMO RESPONDER
Espanol neutro, breve y amable. Dos o tres oraciones, salvo cuando listes
turnos. Trata al paciente de "tu".

Para listar turnos usa este formato, del mas proximo al mas lejano:
- martes 2 de septiembre, 10:30 - Medicina General - Dr. Perez - Sede Norte

ESCRIBE EN TEXTO PLANO. Nada de markdown: ni **negritas**, ni ## titulos, ni
tablas. La burbuja del chat muestra el texto tal cual, asi que los asteriscos
se ven como asteriscos y quedan mal. Solo guiones para las listas.

# DATOS PERSONALES
No pidas cedula, telefono ni direccion. No los necesitas y este chat es
publico. Si el paciente los escribe, no los repitas en tu respuesta.
"""

def agregar_mensaje(messages, role, content):
    messages.append({"role": role, "content": content})


def ejecutar_herramienta(nombre, argumentos_json):
    funcion = funciones.get(nombre)
    if funcion is None:
        return json.dumps({"error": f"No existe la herramienta {nombre}"})

    try:
        argumentos = json.loads(argumentos_json) if argumentos_json else {}
    except json.JSONDecodeError:
        argumentos = {}

    argumentos = {k: v for k, v in argumentos.items() if v not in ("", None)}

    print(f"\n[TOOL-CALL] {nombre}({argumentos})", flush=True)

    try:
        resultado = funcion(**argumentos)
    except Exception as e:
        print(f"[TOOL-ERROR] {type(e).__name__}: {e}", flush=True)
        return json.dumps({"error": f"No se pudo consultar el sistema: {type(e).__name__}"})

    if isinstance(resultado, list) and not resultado:
        print(f"[TOOL-RESULT] Lista vacia", flush=True)
        return json.dumps({"resultados": [], "nota": "No hay resultados."},
                          ensure_ascii=False)

    print(f"[TOOL-RESULT] {len(resultado) if isinstance(resultado, list) else 1} resultados", flush=True)
    return json.dumps({"resultados": resultado}, ensure_ascii=False, default=str)


def enviar_mensajes(messages):
    respuesta_final = ""

    try:
        for _ in range(3):
            completion = client.responses.create(
                model=MODELO,
                instructions=construir_instrucciones(),
                input=messages,
                tools=tools,
                stream=True,
                store=False, 
            )

            salida = []
            hubo_texto = False

            for chunk in completion:
                if chunk.type == "response.output_text.delta":
                    if chunk.delta:
                        hubo_texto = True
                        respuesta_final += chunk.delta
                        yield ("texto", chunk.delta)

                elif chunk.type == "response.completed":
                    salida = list(chunk.response.output or [])

            llamadas = []
            for item in salida:
                messages.append(item)
                if item.type == "function_call":
                    llamadas.append(item)

            if not llamadas:
                break

            for llamada in llamadas:
                yield ("aviso", avisos.get(llamada.name, "Consultando..."))

                resultado = ejecutar_herramienta(llamada.name, llamada.arguments)

                messages.append({
                    "type": "function_call_output",
                    "call_id": llamada.call_id,
                    "output": resultado,
                })

            if hubo_texto:
                respuesta_final = ""

        if not respuesta_final:
            respuesta_final = ("No pude completar la consulta. Intenta de nuevo "
                               "o comunicate con recepcion.")
            yield ("texto", respuesta_final)
            agregar_mensaje(messages, "assistant", respuesta_final)

        yield ("fin", respuesta_final)

    except Exception as e:
        yield ("error", f"No pude procesar tu mensaje ({type(e).__name__}).")

TIPOS_AUDIO = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/aac": "m4a",
    "audio/x-m4a": "m4a",
}


def transcribir(contenido_audio, tipo=None, nombre=None):
    if not contenido_audio:
        raise ValueError("El audio llego vacio.")

    limite = int(os.getenv("MAX_AUDIO_BYTES", "8000000"))
    if len(contenido_audio) > limite:
        raise ValueError(f"El audio es muy grande (maximo {limite // 1000000} MB).")

    extension = TIPOS_AUDIO.get((tipo or "").split(";")[0].strip())
    if not extension and nombre and "." in nombre:
        extension = nombre.rsplit(".", 1)[-1].lower()
    if not extension:
        extension = "webm"

    transcript = client.audio.transcriptions.create(
        model=MODELO_AUDIO,
        file=(f"audio.{extension}", contenido_audio, tipo or f"audio/{extension}"),
    )

    texto = (transcript.text or "").strip()
    if not texto:
        raise ValueError("No se entendio el audio. Intenta grabar de nuevo.")

    return texto
