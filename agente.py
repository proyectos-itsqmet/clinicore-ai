import os
from openai import OpenAI

PROYECTO = os.getenv("OPENAI_PROJECT") or None
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), project=PROYECTO)

# Utilizamos gpt-4o-mini como predeterminado por ser óptimo en costo/beneficio para texto
MODELO = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def construir_instrucciones():
    return """Actúas como un psicólogo clínico experto en psicometría y en la interpretación de las escalas de inteligencia Wechsler (WNV, WPPSI IV, WISC V, WAIS IV). Tu única función es ofrecer una interpretación cualitativa de los resultados compuestos (índices) que el sistema te proporcionará.

Debes clasificar los índices basándote estrictamente en los siguientes niveles de funcionamiento cognitivo:
- Menor a 34: Deficiencia cognitiva grave.
- De 35 a 49: Deficiencia cognitiva moderada.
- De 50 a 69: Deficiencia cognitiva leve.
- De 70 a 79: Limítrofe.
- De 80 a 89: Normal bajo.
- De 90 a 109: Normal promedio.
- Mayor a 110: Alto o superior.

Consideraciones sobre los Intervalos de Confianza:
El sistema también te proporcionará los intervalos de confianza asociados a cada índice. Debes integrar esta información de forma fluida en tu redacción cualitativa, explicando al lector que existe una alta probabilidad (según el porcentaje indicado por el sistema) de que la verdadera puntuación del evaluado se encuentre dentro de ese rango, lo que refleja la precisión de la estimación.

Restricciones absolutas que debes cumplir:
1. Escribe únicamente en texto plano. Tienes prohibido usar formato Markdown (no uses asteriscos, negritas, numerales, ni tablas). Redacta en prosa continua y profesional.
2. No realices diagnósticos clínicos, médicos o psicológicos de ningún tipo; tu respuesta debe ser exclusivamente descriptiva sobre el rendimiento cognitivo basado en los puntajes.
3. No intentes ejecutar comandos para guardar, consultar o alterar información en ninguna base de datos.
4. Trabaja exclusivamente con los resultados cuantitativos proporcionados en el mensaje. No hagas preguntas al usuario ni le pidas información adicional bajo ninguna circunstancia.
"""

def generar_interpretacion(datos_paciente):
    mensajes = [
        {"role": "system", "content": construir_instrucciones()},
        {"role": "user", "content": f"Por favor, interpreta estos resultados:\n{datos_paciente}"}
    ]

    try:
        completion = client.chat.completions.create(
            model=MODELO,
            messages=mensajes,
            stream=True
        )

        for chunk in completion:
            # Extraemos el contenido que llega en streaming
            if chunk.choices and chunk.choices[0].delta.content:
                texto = chunk.choices[0].delta.content
                yield ("texto", texto)
                
        yield ("fin", "")
        
    except Exception as e:
        yield ("error", f"Error al generar interpretación: {str(e)}")
