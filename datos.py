import os
from datetime import date, datetime

import requests

QMS_URL = os.getenv("QMS_API_URL", "http://localhost:8080")

STATUS_LIBRE = "STATUS_FREE"

EXCLUIR = [p.strip().lower() for p in os.getenv("EXCLUIR", "demo,test,prueba").split(",")
           if p.strip()]

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


#! Fecha de actual
def fecha_hoy():
    return date.today()


def fecha_hoy_texto():

    ahora = datetime.now()
    return (f"{DIAS[ahora.weekday()]} {ahora.day} de {MESES[ahora.month - 1]} "
            f"de {ahora.year}, {ahora.strftime('%H:%M')}")


def consultar(ruta, params=None):

    params = {k: v for k, v in (params or {}).items() if v is not None}
    
    # Imprime la peticion que se va a hacer (forzando salida con flush=True)
    print(f"\n[BACKEND-REQ] --> GET {ruta} | Params: {params}", flush=True)
    
    respuesta = requests.get(f"{QMS_URL}{ruta}", params=params, timeout=10)
    respuesta.raise_for_status()
    
    json_data = respuesta.json()
    
    # Imprime un resumen de la respuesta
    print(f"[BACKEND-RES] <-- Respuesta: {str(json_data)[:300]}...\n", flush=True)
    
    return json_data


def contenido(respuesta):

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
    junto = " ".join(t for t in textos if t).lower()
    return any(palabra in junto for palabra in EXCLUIR)

def ver_servicios(nombre=None):

#! Servicios de clinica
    respuesta = consultar("/api/services", {"name": nombre, "size": 60})

    servicios = []
    for s in contenido(respuesta):
        if es_de_prueba(s.get("name")):
            continue

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

#! Medicos
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

#! Sedes / Direcciones
    respuesta = consultar("/api/stablishments", {"size": 60})

    sedes = []
    for e in contenido(respuesta):
        if es_de_prueba(e.get("name"), e.get("address")):
            continue
        sedes.append({"id": e.get("id"), "nombre": e.get("name"),
                      "direccion": e.get("address")})
    return sedes


def ver_disponibilidad(servicio=None, doctor=None, desde=None, hasta=None):

    hoy = fecha_hoy()

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

    respuesta = consultar("/api/schedules", {

        "from": inicio.isoformat(),      
        "status": STATUS_LIBRE,         

        "to": fin.isoformat() if fin else None,
        "doctorName": doctor,
        "size": 150,
    })

    ahora = datetime.now()

    cupos = []
    for c in contenido(respuesta):
        medico = c.get("doctor") or {}
        servicio_dto = c.get("service") or {}
        sede = c.get("stablishment") or {}

#! No ofrecer turnos de servicios o sedes de prueba.
        if es_de_prueba(servicio_dto.get("name"), sede.get("name")):
            continue

        fecha = c.get("date")
        if not fecha or date.fromisoformat(fecha) < hoy:
            continue

        hora = (c.get("hour") or "")[:5]

#! Si el turno es de HOY, comparar tambien hora actual
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

#! Retornar solo los 25 mas proximos
    return cupos[:25]
