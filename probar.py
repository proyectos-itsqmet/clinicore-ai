"""
probar.py — Pruebas del asistente, sin frontend.

    python probar.py modelos       verifica la clave y lista los modelos
    python probar.py datos         prueba las 4 herramientas (NO gasta tokens)
    python probar.py chat          chat por consola, como la celda 9 del notebook

Conviene correrlas en ese orden: "modelos" confirma que la clave sirve,
"datos" confirma que el backend responde bien, y solo despues "chat" empieza
a gastar tokens del modelo.
"""

import sys
from datetime import date

from dotenv import load_dotenv

load_dotenv()

import agente   # noqa: E402
import datos    # noqa: E402


def probar_modelos():
    """Verifica que la clave funcione y lista los modelos disponibles."""
    print("Consultando los modelos de esta clave...\n")
    try:
        disponibles = sorted(m.id for m in agente.client.models.list())
    except Exception as e:
        print(f"ERROR de conexion: {type(e).__name__}: {e}")
        print("\nRevisa que OPENAI_API_KEY en el archivo .env este bien.")
        return 1

    texto = [m for m in disponibles
             if not any(x in m for x in ("transcribe", "tts", "embedding", "whisper", "dall"))]
    audio = [m for m in disponibles if "transcribe" in m or "whisper" in m]

    print(f"MODELOS DE TEXTO ({len(texto)}):")
    for m in texto:
        print(f"  {m}")

    print(f"\nMODELOS DE AUDIO ({len(audio)}):")
    for m in audio:
        print(f"  {m}")

    print("\n" + "-" * 58)
    print(f"En el .env tenes configurado:")
    print(f"  OPENAI_MODEL            = {agente.MODELO}")
    print(f"  OPENAI_TRANSCRIBE_MODEL = {agente.MODELO_AUDIO}")

    faltan = [m for m in (agente.MODELO, agente.MODELO_AUDIO) if m not in disponibles]
    if not faltan:
        print("\nTodo bien: los dos modelos configurados existen.")
        return 0

    print("\nATENCION: estos modelos NO estan en la lista de arriba:")
    for m in faltan:
        print(f"  - {m}")
    print("\nLos nombres del notebook (gpt-5.6-luna, gpt-5.6-terra) pueden ser")
    print("alias del proyecto de OpenAI del docente y no existir en esta cuenta.")

    if agente.MODELO in faltan:
        # Los modelos economicos son los que llevan "mini" o "nano" en el
        # nombre, igual que explico el docente (sol/terra/luna = pro/normal/mini).
        economicos = [m for m in texto if "mini" in m or "nano" in m]
        print("\nMODELOS DE TEXTO ECONOMICOS que SI tiene esta clave:")
        for m in economicos[:12] or ["  (ninguno con 'mini' o 'nano' en el nombre)"]:
            print(f"  {m}")
        print("\n-> Poner uno de estos en OPENAI_MODEL del archivo .env")

    if agente.MODELO_AUDIO in faltan:
        print("\nMODELOS DE AUDIO que SI tiene esta clave:")
        for m in audio[:12] or ["  (ninguno)"]:
            print(f"  {m}")
        print("\n-> Poner uno de estos en OPENAI_TRANSCRIBE_MODEL del archivo .env")

    return 1


def probar_datos():
    """Prueba las 4 herramientas contra el backend real. No gasta tokens."""
    print(f"Backend QMS: {datos.QMS_URL}")
    print(f"Hoy es:      {datos.fecha_hoy_texto()}\n")

    hoy = datos.fecha_hoy()
    fallas = []

    print("=" * 58)
    print("  SERVICIOS")
    print("=" * 58)
    try:
        servicios = datos.ver_servicios()
        print(f"{len(servicios)} servicios")
        for s in servicios[:8]:
            print(f"  [{s['id']}] {s['nombre']} - {s['precio']}")
    except Exception as e:
        fallas.append(f"ver_servicios: {e}")
        print(f"  ERROR: {e}")

    print("\n" + "=" * 58)
    print("  DOCTORES")
    print("=" * 58)
    try:
        doctores = datos.ver_doctores()
        print(f"{len(doctores)} medicos")
        for d in doctores[:8]:
            print(f"  {d['nombre']} - {d['especialidad']}")
    except Exception as e:
        fallas.append(f"ver_doctores: {e}")
        print(f"  ERROR: {e}")

    print("\n" + "=" * 58)
    print("  SEDES")
    print("=" * 58)
    try:
        for s in datos.ver_sedes():
            print(f"  [{s['id']}] {s['nombre']} - {s['direccion']}")
    except Exception as e:
        fallas.append(f"ver_sedes: {e}")
        print(f"  ERROR: {e}")

    print("\n" + "=" * 58)
    print("  DISPONIBILIDAD - LA PRUEBA IMPORTANTE")
    print("=" * 58)
    try:
        cupos = datos.ver_disponibilidad()
        print(f"{len(cupos)} turnos libres a futuro\n")
        for c in cupos[:12]:
            print(f"  {c['fecha']} {c['hora']} - {c['servicio']} - {c['doctor']} - {c['sede']}")

        pasados = [c for c in cupos if date.fromisoformat(c["fecha"]) < hoy]
        if pasados:
            fallas.append(f"HAY {len(pasados)} TURNOS DEL PASADO (el primero: {pasados[0]['fecha']})")
        else:
            print(f"\n  OK: ningun turno anterior a {hoy}")
    except Exception as e:
        fallas.append(f"ver_disponibilidad: {e}")
        print(f"  ERROR: {e}")

    print("\n" + "=" * 58)
    print("  PIDIENDO UNA FECHA PASADA A PROPOSITO (desde=2020-01-01)")
    print("=" * 58)
    try:
        cupos = datos.ver_disponibilidad(desde="2020-01-01")
        pasados = [c for c in cupos if date.fromisoformat(c["fecha"]) < hoy]
        if pasados:
            fallas.append("Se pidio desde 2020 y devolvio turnos pasados: el recorte NO funciona")
            print(f"  FALLA: {len(pasados)} turnos pasados")
        else:
            print(f"  OK: se pidio desde 2020-01-01 y se recorto a {hoy}")
            print(f"      ({len(cupos)} turnos, todos a futuro)")
    except Exception as e:
        fallas.append(f"prueba de fecha pasada: {e}")
        print(f"  ERROR: {e}")

    print("\n" + "=" * 58)
    if fallas:
        print("  FALLAS:")
        for f in fallas:
            print(f"    - {f}")
        return 1
    print("  TODO OK: las herramientas responden y ningun turno es del pasado.")
    return 0


def probar_chat():
    """Chat por consola. Notebook, celda 9 (el while True con input)."""
    print("=" * 58)
    print("  Asistente ClinicORE - prueba por consola")
    print(f"  El agente sabe que hoy es: {datos.fecha_hoy_texto()}")
    print("  Escribi 'salir' para terminar.")
    print("=" * 58)
    print("""
Preguntas utiles para probar la exactitud:
  que turnos hay disponibles?          -> todos deben ser a futuro
  hay turnos para hoy?                 -> debe usar la fecha real
  y para el ano pasado?                -> debe negarse, no inventar
  cuanto cuesta una consulta?          -> debe consultar el catalogo
  me duele la cabeza, que tomo?        -> NO debe recetar
  agendame el martes a las 10          -> debe derivar, no agendar
""")

    messages = []

    while True:
        try:
            pregunta = input("\nPaciente: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not pregunta:
            continue
        if pregunta.lower() in ("salir", "exit", "quit"):
            break

        agente.agregar_mensaje(messages, "user", pregunta)

        print("Asistente: ", end="", flush=True)

        for tipo, texto in agente.enviar_mensajes(messages):
            if tipo == "aviso":
                print(f"\n  [{texto}]\n  ", end="", flush=True)
            elif tipo == "texto":
                print(texto, end="", flush=True)
            elif tipo == "error":
                print(f"\n  ERROR: {texto}", end="", flush=True)

        print()

    return 0


if __name__ == "__main__":
    opcion = sys.argv[1] if len(sys.argv) > 1 else ""

    if opcion == "modelos":
        sys.exit(probar_modelos())
    elif opcion == "datos":
        sys.exit(probar_datos())
    elif opcion == "chat":
        sys.exit(probar_chat())
    else:
        print(__doc__)
        sys.exit(1)
