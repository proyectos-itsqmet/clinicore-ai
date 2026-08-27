# ClinicORE AI — Asistente virtual de informacion

Servidor Flask que expone un agente de IA para los pacientes de ClinicORE.
Responde por **texto** y por **audio**, con **streaming real** (palabra por
palabra), y solo dice datos que existen en la base de datos del sistema.

Hecho con lo del taller practico: API de OpenAI, Responses API, function
calling, streaming y transcripcion de audio.

---

## Los tres archivos

| Archivo | Que tiene | De donde sale |
|---------|-----------|---------------|
| `datos.py` | Las 4 herramientas: consultan el backend Spring del QMS | Celda 22, con la API real en lugar del valor fijo |
| `agente.py` | `tools[]`, `instructions`, `enviar_mensajes()`, `transcribir()` | Celdas 16-18, 20-28, 33, 44 |
| `app.py` | El servidor Flask con las rutas | La clase de despliegue |

Mas `probar.py`, que son las pruebas por consola.

---

## Puesta en marcha

```powershell
cd clinicore-ai

python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Git Bash: source .venv/Scripts/activate

pip install -r requirements.txt

copy .env.example .env              # Git Bash: cp .env.example .env
notepad .env                        # poner la OPENAI_API_KEY
```

### Probar en orden (los dos primeros no gastan tokens del modelo)

```powershell
python probar.py modelos    # 1. la clave funciona? que modelos hay?
python probar.py datos      # 2. el backend responde? los turnos son a futuro?
python probar.py chat       # 3. conversar por consola
```

El paso 1 no es opcional: el notebook de clase usaba alias de modelo del
proyecto del docente (`gpt-5.6-luna`, `gpt-5.6-terra`) que no existen en otra
cuenta. El script lista los nombres reales de esta clave.

El paso 2 necesita el backend Spring levantado en `localhost:8080`.

### Levantar el servidor

```powershell
python app.py
```

Queda en `http://localhost:8000`.

---

## Rutas

### `GET /`
Estado del servicio: modelo configurado, backend y fecha que ve el agente.

### `POST /chat`
```json
{ "mensaje": "que turnos hay para medicina general?", "session_id": "abc123" }
```
Responde en streaming (`text/event-stream`). El `session_id` es opcional: si
no se manda, el servidor genera uno y lo devuelve en el primer evento.

### `POST /chat/audio`
`multipart/form-data`:

| Campo | Tipo | Obligatorio |
|-------|------|-------------|
| `file` | audio (`webm`, `mp3`, `m4a`, `wav`, `ogg`, `mp4`) | si |
| `session_id` | texto | no |

Mismo streaming, precedido por un evento `transcripcion` con lo que dijo el
paciente.

### `POST /chat/reset`
```json
{ "session_id": "abc123" }
```

---

## Eventos del streaming

| Evento | Contenido | Que hace la interfaz |
|--------|-----------|----------------------|
| `session` | `{"session_id": "..."}` | Guardarlo para los mensajes siguientes |
| `transcripcion` | `{"texto": "..."}` | Mostrarlo como mensaje del paciente |
| `status` | `{"texto": "Consultando la agenda..."}` | Mostrar el indicador de carga |
| `delta` | `{"texto": "frag"}` | Ir agregando al mensaje del asistente |
| `done` | `{"texto": "respuesta completa"}` | Cerrar el mensaje |
| `error` | `{"mensaje": "..."}` | Mostrar el error y permitir reintentar |

Prueba rapida con curl (el `-N` desactiva el buffer, sin eso parece que no
hubiera streaming):

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"mensaje":"que turnos hay disponibles?"}'
```

---

## Por que el asistente no ofrece turnos de meses pasados

Una version anterior hecha con n8n ofrecia turnos de mayo. Habia **dos**
causas y las dos estan corregidas:

**1. El agente no sabia que dia era hoy.**
`agente.construir_instrucciones()` le mete la fecha real en cada consulta.
Sin eso el modelo interpreta "manana" contra su fecha de entrenamiento.

**2. La consulta de agenda se hacia sin filtros.**
`GET /api/schedules` del backend Spring tiene `from`, `to` y `status`
**opcionales**, y por defecto devuelve los **10 registros mas antiguos** de
toda la base (`@PageableDefault(size = 10, sort = {"date","hour"}, ASC)`), en
cualquier estado. El bot razonaba bien sobre datos malos.

En `datos.ver_disponibilidad()` los filtros los pone **el codigo, nunca el
modelo**:
- `from` es siempre hoy. Si el modelo pide una fecha pasada, se le corrige a hoy.
- `status` es siempre `STATUS_FREE` (el valor exacto del enum del backend; no
  es "DISPONIBLE" ni "FREE").
- Al final se descarta cualquier fecha pasada que se cuele.

**3. Y ademas, reglas en el prompt.** Todo dato concreto tiene que venir de
una herramienta ejecutada en esa conversacion. Una lista vacia se informa como
"no hay turnos", nunca se rellena con horarios plausibles.

La regla general, que es la leccion de todo esto: **el modelo nunca elige los
filtros de una consulta.** Los pone el codigo.

---

## Que puede y que no puede hacer

| Puede | No puede |
|-------|----------|
| Informar servicios, precios, especialidades, medicos y sedes | Agendar, cancelar o modificar turnos |
| Consultar turnos libres reales | Diagnosticar o recetar |
| Recibir texto y audio | Pedir datos personales |

No existe ninguna herramienta de escritura en el codigo, asi que el agente no
tiene forma tecnica de modificar nada del sistema.

---

## Diferencias con el notebook

- **`store=False`** en las llamadas. El notebook usa `store=True`, que deja la
  conversacion guardada del lado de OpenAI. En un chat de clinica no
  corresponde.
- **`enviar_mensajes()` se repite hasta 3 veces sola.** En el notebook ejecuta
  la herramienta y termina; el docente la vuelve a llamar a mano en la celda
  27. En un servidor no hay nadie para llamarla de nuevo.
- **Un diccionario `funciones` en lugar de `if item.name == ...`.** Con cuatro
  herramientas, cuatro `if` anidados es peor de leer.
