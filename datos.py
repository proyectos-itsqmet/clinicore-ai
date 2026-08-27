"""
datos.py — Consultas al backend del QMS (Spring Boot).

En el notebook de clase, la herramienta del agente devolvia un valor fijo:

    def obtener_clima_actual(ubicacion, unidad="C"):
        temperatura = 30 # Esto se puede cambiar por una llamada a una API
        return f"La temperatura en {ubicacion} es de {temperatura} {unidad}"

Este archivo es ese comentario cumplido: en lugar de un valor inventado, las
herramientas consultan la base de datos real de la clinica.

IMPORTANTE — POR QUE EXISTE ESTE ARCHIVO SEPARADO
--------------------------------------------------
Una version anterior del chatbot (hecha con n8n) ofrecia turnos de meses
pasados. La causa NO era el modelo, era la consulta:

  GET /api/schedules del backend tiene los filtros "from", "to" y "status"
  OPCIONALES, y por defecto devuelve los 10 registros MAS ANTIGUOS de toda
  la base de datos, en cualquier estado.

Si se le deja al modelo decidir los filtros, no los pone, y el bot razona
bien sobre datos malos. Aqui los filtros se ponen SIEMPRE desde el codigo.
"""

import os
from datetime import date, datetime

import requests

# URL del backend Spring. Se lee del archivo .env
QMS_URL = os.getenv("QMS_API_URL", "http://localhost:8080")

# Valor exacto del enum ScheduleStatus del backend para un cupo libre.
# Esta verificado en el codigo Java: NO es "DISPONIBLE" ni "FREE".
STATUS_LIBRE = "STATUS_FREE"

# Palabras que marcan un registro de prueba. Cualquier servicio, sede o medico
# cuyo nombre las contenga NO se le muestra al paciente.
#
# La base de datos tiene datos de seed mezclados con los reales: servicios
# "DEMO - Limpieza Dental", sedes "Establecimiento test", y medicos generados
# al azar con especialidades que no son medicas ("International Brand
# Facilitator", "Dynamic Program Assistant"). Sin este filtro el asistente los
# ofrece como si fueran reales.
#
# Se configura en el .env con EXCLUIR (separado por comas). Vacio = no filtra.
EXCLUIR = [p.strip().lower() for p in os.getenv("EXCLUIR", "demo,test,prueba").split(",")
           if p.strip()]

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_hoy():
    """Devuelve la fecha de hoy."""
    return date.today()


def fecha_hoy_texto():
    """Fecha y hora de hoy en texto, para decirle al agente que dia es.

    Sin esto el modelo no sabe en que fecha esta y ofrece turnos de meses
    pasados. Es la mitad de la solucion al error de "turnos de mayo".
    """
    ahora = datetime.now()
    return (f"{DIAS[ahora.weekday()]} {ahora.day} de {MESES[ahora.month - 1]} "
            f"de {ahora.year}, {ahora.strftime('%H:%M')}")


def consultar(ruta, params=None):
    """Hace un GET al backend del QMS y devuelve el JSON.

    Los endpoints que se usan aqui son publicos (permitAll en el backend),
    por eso no hace falta enviar token de autenticacion.
    """
    params = {k: v for k, v in (params or {}).items() if v is not None}
    respuesta = requests.get(f"{QMS_URL}{ruta}", params=params, timeout=10)
    respuesta.raise_for_status()
    return respuesta.json()


def contenido(respuesta):
    """El backend devuelve las listas paginadas como {"content": [...]}."""
    if isinstance(respuesta, dict):
        return respuesta.get("content") or []
    if isinstance(respuesta, list):
        return respuesta
    return []


def nombre_completo(persona):
    nombre = persona.get("firstName") or ""
    apellido = persona.get("lastName") or ""
    return f"{nombre} {apellido}".strip()


def es_de_prueba(*textos):
    """True si alguno de los textos contiene una palabra de la lista EXCLUIR."""
    junto = " ".join(t for t in textos if t).lower()
    return any(palabra in junto for palabra in EXCLUIR)


# ---------------------------------------------------------------------------
# Las 4 herramientas del agente. Todas son de SOLO LECTURA: el asistente
# informa, no agenda ni modifica nada.
# ---------------------------------------------------------------------------


def ver_servicios(nombre=None):
    """Servicios y examenes de la clinica, con su precio final."""
    respuesta = consultar("/api/services", {"name": nombre, "size": 60})

    servicios = []
    for s in contenido(respuesta):
        if es_de_prueba(s.get("name")):
            continue

        # netPrice ya es precio menos descuento, calculado por el backend.
        precio = s.get("netPrice")
        if precio is None:
            precio = s.get("price")
        servicios.append({
            "id": s.get("id"),
            "nombre": s.get("name"),
            "precio": precio,
        })
    return servicios


def ver_doctores(nombre=None):
    """Medicos de la clinica con su especialidad.

    Se devuelve solo nombre y especialidad. El backend manda tambien el
    correo y la cedula del medico, pero un paciente que pregunta por
    especialidades no necesita los datos personales del doctor.
    """
    respuesta = consultar("/api/doctors", {"name": nombre, "size": 60})

    medicos = []
    for d in contenido(respuesta):
        nombre = nombre_completo(d)
        especialidad = d.get("speciality")
        if es_de_prueba(nombre, especialidad):
            continue
        medicos.append({"nombre": nombre, "especialidad": especialidad})
    return medicos


def ver_sedes():
    """Sedes de la clinica con su direccion."""
    respuesta = consultar("/api/stablishments", {"size": 60})

    sedes = []
    for e in contenido(respuesta):
        if es_de_prueba(e.get("name"), e.get("address")):
            continue
        sedes.append({"id": e.get("id"), "nombre": e.get("name"),
                      "direccion": e.get("address")})
    return sedes


def ver_disponibilidad(servicio=None, doctor=None, desde=None, hasta=None):
    """Cupos LIBRES y a FUTURO, del mas proximo al mas lejano.

    AQUI ESTA LA CORRECCION DEL ERROR DE LOS "TURNOS DE MAYO".
    Los filtros "from" y "status" se ponen siempre desde el codigo, nunca
    los elige el modelo.
    """
    hoy = fecha_hoy()

    # Si el modelo pide una fecha pasada, se la corrige a hoy. Es mejor
    # responder con el proximo turno real que con uno que ya paso.
    inicio = hoy
    if desde:
        try:
            pedida = date.fromisoformat(desde)
            if pedida > hoy:
                inicio = pedida
        except ValueError:
            pass

    fin = None
    if hasta:
        try:
            candidata = date.fromisoformat(hasta)
            if candidata >= inicio:
                fin = candidata
        except ValueError:
            pass

    # El modelo dice el servicio por su nombre ("ecografia"), pero el backend
    # filtra por id. Se busca el id en el catalogo real antes de consultar.
    servicio_id = None
    if servicio:
        for s in ver_servicios():
            if servicio.lower() in (s["nombre"] or "").lower():
                servicio_id = s["id"]
                break

    respuesta = consultar("/api/schedules", {
        # ---- Estos dos filtros son obligatorios y los pone el codigo ----
        "from": inicio.isoformat(),      # nunca antes de hoy
        "status": STATUS_LIBRE,          # solo cupos libres
        # -----------------------------------------------------------------
        "to": fin.isoformat() if fin else None,
        "serviceId": servicio_id,
        "doctorName": doctor,
        # Se piden bastantes mas de los que se van a mostrar, porque despues
        # se descartan los turnos de hoy cuya hora ya paso. Con size=25 se
        # traian los 25 turnos de hoy a las 08:00, se descartaban todos por la
        # hora y quedaban 0 resultados, sin llegar nunca a los de manana.
        "size": 150,
    })

    ahora = datetime.now()

    cupos = []
    for c in contenido(respuesta):
        medico = c.get("doctor") or {}
        servicio_dto = c.get("service") or {}
        sede = c.get("stablishment") or {}

        # No ofrecer turnos de servicios o sedes de prueba.
        if es_de_prueba(servicio_dto.get("name"), sede.get("name")):
            continue

        # Se descarta cualquier fecha pasada que se pudiera colar.
        fecha = c.get("date")
        if not fecha or date.fromisoformat(fecha) < hoy:
            continue

        hora = (c.get("hour") or "")[:5]

        # Si el turno es de HOY, hay que comparar tambien la HORA. El backend
        # filtra por fecha, asi que a las 11:44 seguia devolviendo los turnos
        # de las 08:00 de hoy. Es el mismo problema que los turnos de meses
        # pasados, pero a escala de horas.
        if date.fromisoformat(fecha) == hoy and hora:
            try:
                h, m = hora.split(":")
                if ahora.hour * 60 + ahora.minute >= int(h) * 60 + int(m):
                    continue
            except ValueError:
                pass

        cupos.append({
            "fecha": fecha,
            "hora": hora,
            "servicio": servicio_dto.get("name"),
            "doctor": nombre_completo(medico),
            "especialidad": medico.get("speciality"),
            "sede": sede.get("name"),
        })

    # Solo los 25 mas proximos. Ya vienen ordenados por fecha y hora desde el
    # backend, y mandarle 150 turnos al modelo es gastar tokens de mas.
    return cupos[:25]
