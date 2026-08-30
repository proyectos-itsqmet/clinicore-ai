import requests
import json

url = "http://localhost:8000/chat"

# Simulamos los datos que enviaría tu aplicación web
datos_paciente = """
Paciente: Niño, 8 años.
Prueba: WISC V
Resultados de Índices Compuestos:
- Índice de Comprensión Verbal (ICV): 75
- Índice Visoespacial (IVE): 92
- Índice de Razonamiento Fluido (IRF): 112
- Índice de Memoria de Trabajo (IMT): 68
- Índice de Velocidad de Procesamiento (IVP): 100
"""

print(f"Conectando a {url} ...\n")
print("=== RESPUESTA DEL PSICÓLOGO AI ===\n")

try:
    # Hacemos la petición POST con stream=True porque la API devuelve los datos por partes (SSE)
    respuesta = requests.post(url, json={"mensaje": datos_paciente}, stream=True)
    
    # Leemos la respuesta a medida que llega en tiempo real
    for linea in respuesta.iter_lines():
        if linea:
            linea_texto = linea.decode('utf-8')
            if linea_texto.startswith("data: "):
                datos_evento = json.loads(linea_texto[6:]) # Quitamos el "data: "
                
                # Si el evento trae texto, lo imprimimos sin salto de línea para simular el tipeo
                if "texto" in datos_evento and datos_evento["texto"]:
                    print(datos_evento["texto"], end="", flush=True)
                    
    print("\n\n==================================")
except requests.exceptions.ConnectionError:
    print("Error: No se pudo conectar. ¿Te aseguraste de ejecutar 'python app.py' en otra terminal?")
