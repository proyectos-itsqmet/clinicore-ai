"""
agente.py — El agente virtual: herramientas, instrucciones y streaming.

Es el mismo flujo del notebook de clase (QMS.ipynb), juntando tres partes:

    celdas 20 a 28  ->  function calling: tools[] y enviar_mensajes()
    celdas 16 a 18  ->  streaming: leer los eventos delta uno por uno
    celda 44        ->  instructions: el rol del agente

Se conservan los nombres de las funciones del notebook (agregar_mensaje,
enviar_mensajes) para que se pueda seguir celda por celda.
"""

import json
import os

from openai import OpenAI

import datos

# ---------------------------------------------------------------------------
# 1. El cliente. Notebook, celda 2.
# ---------------------------------------------------------------------------

# El notebook (celda 2) creaba el cliente pasandole el proyecto del docente:
#
#     client = OpenAI(project="proj_GGs9WDB...")
#
# Aqui el proyecto es OPCIONAL y solo se envia si esta puesto en el .env.
# Con una clave que empieza con "sk-proj-" el proyecto ya viene incluido en la
# clave, asi que no hace falta. Y el proyecto del docente NO sirve con otra
# clave: la API responde con error de permisos.
PROYECTO = os.getenv("OPENAI_PROJECT") or None

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), project=PROYECTO)

# Modelos del notebook de clase. "luna" es la version mini de la familia
# (sol = Pro, terra = normal, luna = mini) y es la que el docente recomendo
# por precio: 0.20 USD de entrada contra 2 USD de terra.
MODELO = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
MODELO_AUDIO = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe")


# ---------------------------------------------------------------------------
# 2. Las herramientas. Notebook, celda 24.
#    Mismo formato: type, name, description, parameters.
# ---------------------------------------------------------------------------

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


# Nombre de la herramienta -> funcion de datos.py que la ejecuta.
# En el notebook esto era un "if item.name == ..." (celda 26). Con cuatro
# herramientas, un diccionario es mas corto y mas facil de leer.
funciones = {
    "ver_servicios": datos.ver_servicios,
    "ver_doctores": datos.ver_doctores,
    "ver_sedes": datos.ver_sedes,
    "ver_disponibilidad": datos.ver_disponibilidad,
}

# Texto que se le muestra al paciente mientras se ejecuta cada herramienta,
# para que no quede esperando sin saber que pasa.
avisos = {
    "ver_servicios": "Revisando el catalogo de servicios...",
    "ver_doctores": "Consultando los medicos...",
    "ver_sedes": "Buscando las sedes...",
    "ver_disponibilidad": "Consultando la agenda...",
}


# ---------------------------------------------------------------------------
# 3. Las instrucciones del agente. Notebook, celda 44.
#    Se arman con una funcion, y no como texto fijo, porque hay que meterle
#    la fecha de HOY en cada consulta. Sin eso el modelo no sabe en que dia
#    esta y ofrece turnos de meses pasados.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 4. Las funciones del notebook: agregar_mensaje y enviar_mensajes.
#    Celdas 25 y 26.
# ---------------------------------------------------------------------------


def agregar_mensaje(messages, role, content):
    """Notebook, celda 25. Igual."""
    messages.append({"role": role, "content": content})


def ejecutar_herramienta(nombre, argumentos_json):
    """Ejecuta una herramienta y devuelve el resultado como texto JSON.

    Si algo falla se devuelve el error como dato en lugar de cortar la
    conversacion, para que el agente pueda disculparse con el paciente.
    """
    funcion = funciones.get(nombre)
    if funcion is None:
        return json.dumps({"error": f"No existe la herramienta {nombre}"})

    try:
        argumentos = json.loads(argumentos_json) if argumentos_json else {}
    except json.JSONDecodeError:
        argumentos = {}

    # El modelo suele mandar "" para los parametros que no quiere usar. Se
    # descartan, porque un filtro con string vacio no es lo mismo que no
    # filtrar.
    argumentos = {k: v for k, v in argumentos.items() if v not in ("", None)}

    try:
        resultado = funcion(**argumentos)
    except Exception as e:
        return json.dumps({"error": f"No se pudo consultar el sistema: {type(e).__name__}"})

    if isinstance(resultado, list) and not resultado:
        # Se dice explicitamente que vino vacio, para que el modelo no lo
        # confunda con una falla y se invente una respuesta.
        return json.dumps({"resultados": [], "nota": "No hay resultados."},
                          ensure_ascii=False)

    return json.dumps({"resultados": resultado}, ensure_ascii=False, default=str)


def enviar_mensajes(messages):
    """Notebook, celda 26 + celdas 16 a 18 (streaming).

    Es un generador: va entregando ("tipo", "texto") a medida que el modelo
    responde, en lugar de esperar la respuesta completa.

    Tipos que entrega:
        aviso  -> "Consultando la agenda..."   (para el indicador de carga)
        texto  -> un fragmento de la respuesta (para ir escribiendo)
        fin    -> la respuesta completa
        error  -> algo fallo

    En el notebook, enviar_mensajes() ejecutaba la herramienta y terminaba: el
    profesor la volvia a llamar a mano en la celda 27. En un servidor no hay
    nadie para llamarla de nuevo, asi que aqui se repite hasta 3 veces sola.
    """
    respuesta_final = ""

    try:
        for _ in range(3):
            # Misma llamada que la celda 17, mas tools y stream.
            completion = client.responses.create(
                model=MODELO,
                instructions=construir_instrucciones(),
                input=messages,
                tools=tools,
                stream=True,
                store=False,   # no dejar la conversacion guardada en OpenAI
            )

            salida = []
            hubo_texto = False

            # Celda 18: leer los fragmentos uno por uno.
            for chunk in completion:
                if chunk.type == "response.output_text.delta":
                    if chunk.delta:
                        hubo_texto = True
                        respuesta_final += chunk.delta
                        yield ("texto", chunk.delta)

                elif chunk.type == "response.completed":
                    salida = list(chunk.response.output or [])

            # Celda 26: "messages += completion.output"
            #
            # Se agregan los OBJETOS tal como vienen, no item.model_dump().
            # El dump incluye campos de solo salida ("status", "caller",
            # "namespace") y la API los rechaza al reenviarlos:
            #     400 - Unknown parameter: 'input[1].status'
            # El SDK sabe serializar los objetos dejando afuera esos campos.
            llamadas = []
            for item in salida:
                messages.append(item)
                if item.type == "function_call":
                    llamadas.append(item)

            # Si el modelo no pidio herramientas, ya termino de responder.
            if not llamadas:
                break

            # Celda 26: ejecutar cada herramienta y guardar su resultado.
            for llamada in llamadas:
                yield ("aviso", avisos.get(llamada.name, "Consultando..."))

                resultado = ejecutar_herramienta(llamada.name, llamada.arguments)

                messages.append({
                    "type": "function_call_output",
                    "call_id": llamada.call_id,
                    "output": resultado,
                })

            # Si escribio algo antes de pedir la herramienta, era un preambulo
            # ("dejame revisar..."). Se descarta para que no quede duplicado.
            if hubo_texto:
                respuesta_final = ""

        if not respuesta_final:
            respuesta_final = ("No pude completar la consulta. Intenta de nuevo "
                               "o comunicate con recepcion.")
            yield ("texto", respuesta_final)
            # Solo en este caso se agrega a mano, porque el modelo no
            # respondio nada. En el camino normal la respuesta ya quedo en el
            # historial dentro de "completion.output": agregarla otra vez la
            # duplicaba y el agente se leia a si mismo dos veces.
            agregar_mensaje(messages, "assistant", respuesta_final)

        yield ("fin", respuesta_final)

    except Exception as e:
        yield ("error", f"No pude procesar tu mensaje ({type(e).__name__}).")


# ---------------------------------------------------------------------------
# 5. Voz a texto. Notebook, celdas 32 a 35.
# ---------------------------------------------------------------------------

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
    """Convierte un audio en texto. Notebook, celda 33.

    En el notebook el audio se leia del disco con open("prueba.mp3", "rb").
    Aqui llega por HTTP, asi que se le pasa la tupla (nombre, bytes, tipo)
    que tambien acepta el SDK.
    """
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
