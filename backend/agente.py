"""
backend/agente.py
-------------------------------------------------------------
Agente "Pregúntale a la ENAHO" (orquestado con crewAI).

Flujo principal (crewAI):
  pregunta -> Analista ENAHO (SQL + ejecución) -> Redactor -> interpretación
Fallback (simple, 1 paso a la vez):
  pregunta -> generar_sql -> ejecutar -> interpretar
-------------------------------------------------------------
"""
import os
import re
import json
import time
from pathlib import Path

import duckdb
from dotenv import load_dotenv
from google import genai
from google.genai import errors as gerr
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

load_dotenv()  # lee GEMINI_API_KEY desde el archivo .env

MODELO = "gemini-2.5-flash"          # modelo gratuito; rápido y suficiente
PARQUET = "data/enaho_hogar.parquet"
CATALOGO = "data/catalogo_mini.json"

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# --- Catálogo de variables (el "cerebro" que evita que invente columnas) ---
catalogo = json.loads(Path(CATALOGO).read_text(encoding="utf-8"))


def _describir_catalogo(cat):
    lineas = []
    for col, info in cat.items():
        etq = info.get("etiqueta", "")
        vals = info.get("valores", {})
        extra = ""
        if vals:
            extra = " | valores: " + ", ".join(f"{k}={lab}" for k, lab in vals.items())
        lineas.append(f"- {col}: {etq}{extra}")
    return "\n".join(lineas)


VARS = _describir_catalogo(catalogo)

# Mapa de departamentos (2 primeros dígitos del ubigeo)
DEPARTAMENTOS = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa",
    "05": "Ayacucho", "06": "Cajamarca", "07": "Callao", "08": "Cusco",
    "09": "Huancavelica", "10": "Huánuco", "11": "Ica", "12": "Junín",
    "13": "La Libertad", "14": "Lambayeque", "15": "Lima", "16": "Loreto",
    "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
    "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes",
    "25": "Ucayali",
}
DEPT_TXT = ", ".join(f"{k}={v}" for k, v in DEPARTAMENTOS.items())

SISTEMA = f"""Eres un analista experto en la ENAHO 2024 (INEI, Perú).
Traduces preguntas en español a UNA consulta SQL para DuckDB.

La tabla vive en el archivo parquet. En el FROM escríbelo así, con comillas simples:
    FROM '{PARQUET}'

Cada fila es un HOGAR. Usa SOLO estas variables:
{VARS}

REGLAS OBLIGATORIAS:
1) La ENAHO usa factor de expansión. Para totales/conteos poblacionales SIEMPRE
   pondera por factor07.
2) Para estimar PERSONAS (población) pondera por (factor07 * mieperho), porque
   cada hogar representa factor07 hogares con mieperho personas.
   Ej. personas en pobreza:
       SUM(factor07 * mieperho) FILTER (WHERE pobreza IN (1, 2))
3) pobreza: 1=pobre extremo, 2=pobre no extremo, 3=no pobre. "Pobre" = 1 o 2.
4) Departamento = 2 primeros dígitos de ubigeo. Códigos: {DEPT_TXT}.
   Para filtrar por departamento:
       SUBSTR(LPAD(CAST(ubigeo AS VARCHAR), 6, '0'), 1, 2) = 'CC'
5) Para ingreso/gasto promedio usa promedio ponderado por factor07.
6) Excluye filas nulas relevantes (ej. WHERE pobreza IS NOT NULL) cuando calcules tasas.
7) Devuelve SOLO el SQL: sin explicación, sin ```sql, sin texto adicional.
8) Solo SELECT (lectura). Nunca INSERT/UPDATE/DELETE/DROP/CREATE.
"""


def _limpiar_sql(texto: str) -> str:
    t = texto.strip()
    t = re.sub(r"^```sql", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"^```", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    return t


def _llamar_gemini(contenido: str, intentos: int = 4):
    """Llama a Gemini con reintento ante errores transitorios (503/429)."""
    for i in range(intentos):
        try:
            return client.models.generate_content(model=MODELO, contents=contenido)
        except gerr.APIError as e:
            code = getattr(e, "code", None)
            msg = str(e).lower()
            transitorio = code in (429, 500, 503) or "unavailable" in msg or "overloaded" in msg
            if transitorio and i < intentos - 1:
                espera = 3 * (i + 1)
                print(f"   (Gemini ocupado, reintentando en {espera}s...)")
                time.sleep(espera)
                continue
            raise


def generar_sql(pregunta: str, error_previo: str | None = None) -> str:
    contenido = SISTEMA + f"\n\nPregunta: {pregunta}\n"
    if error_previo:
        contenido += (f"\nTu SQL anterior falló con este error:\n{error_previo}\n"
                      "Corrígelo y devuelve solo el SQL corregido.")
    resp = _llamar_gemini(contenido)
    return _limpiar_sql(resp.text)


def interpretar(pregunta: str, df) -> str:
    muestra = df.head(20).to_string(index=False)
    contenido = (
        f"Pregunta del usuario: {pregunta}\n\n"
        f"Resultado de la consulta a la ENAHO 2024:\n{muestra}\n\n"
        "Redacta una respuesta clara y breve en español respondiendo la pregunta "
        "con estos números. Redondea cifras grandes de forma legible (ej. 9.4 millones, "
        "27.6%). No inventes datos que no estén en el resultado."
    )
    resp = _llamar_gemini(contenido)
    return resp.text.strip()


def _consultar_simple(pregunta: str):
    """Fallback: flujo original sin crewAI. Devuelve (sql, dataframe, interpretacion)."""
    con = duckdb.connect()
    sql = generar_sql(pregunta)
    if not sql.lower().lstrip().startswith("select"):
        raise ValueError(f"La consulta generada no es un SELECT válido:\n{sql}")
    try:
        df = con.execute(sql).df()
    except Exception as e:
        sql = generar_sql(pregunta, error_previo=str(e))
        df = con.execute(sql).df()
    interpretacion = interpretar(pregunta, df)
    return sql, df, interpretacion


# --- Capa crewAI ---

_ULTIMO: dict = {'sql': None, 'df': None}

_llm = LLM(
    model='gemini/gemini-2.5-flash',
    api_key=os.environ.get("GEMINI_API_KEY"),
)


@tool("ejecutar_sql")
def ejecutar_sql(sql: str) -> str:
    """Ejecuta una consulta SQL SELECT sobre el archivo parquet de la ENAHO y devuelve una vista previa del resultado."""
    global _ULTIMO
    sql = _limpiar_sql(sql)
    if not sql.lower().lstrip().startswith("select"):
        return "Error: solo se permiten consultas SELECT."
    con = duckdb.connect()
    df = con.execute(sql).df()
    _ULTIMO = {'sql': sql, 'df': df}
    return df.head().to_string()


def _hacer_crew() -> Crew:
    analista = Agent(
        role='Analista de datos ENAHO',
        goal=(
            'Dada la pregunta del usuario, escribir el SQL correcto siguiendo '
            'las reglas del sistema y ejecutarlo con la herramienta ejecutar_sql.'
        ),
        backstory=SISTEMA,
        tools=[ejecutar_sql],
        llm=_llm,
        verbose=False,
    )
    redactor = Agent(
        role='Redactor',
        goal=(
            'Interpretar el resultado de la consulta SQL y redactar una respuesta '
            'breve en español con cifras legibles.'
        ),
        backstory='Eres experto en comunicar estadísticas del INEI Perú de forma clara y accesible.',
        llm=_llm,
        verbose=False,
    )
    tarea_sql = Task(
        description=(
            'Pregunta: {pregunta}\n'
            'Escribe el SQL siguiendo EXACTAMENTE las reglas del sistema y ejecútalo '
            'con la herramienta ejecutar_sql.'
        ),
        expected_output='Vista previa del resultado de la consulta SQL ejecutada.',
        agent=analista,
    )
    tarea_interpretacion = Task(
        description=(
            'Con el resultado de la consulta anterior, redacta una respuesta clara y breve '
            'en español que responda la pregunta: {pregunta}. '
            'Usa cifras legibles (ej. 9.4 millones, 27.6%). '
            'No inventes datos que no estén en el resultado.'
        ),
        expected_output='Interpretación en español del resultado de la ENAHO.',
        agent=redactor,
    )
    return Crew(
        agents=[analista, redactor],
        tasks=[tarea_sql, tarea_interpretacion],
        process=Process.sequential,
        verbose=False,
    )


def consultar(pregunta: str):
    """Devuelve (sql, dataframe, interpretacion)."""
    try:
        _ULTIMO['sql'] = None
        _ULTIMO['df'] = None
        crew = _hacer_crew()
        resultado = crew.kickoff(inputs={'pregunta': pregunta})
        sql = _ULTIMO['sql']
        df = _ULTIMO['df']
        if sql is None or df is None:
            raise ValueError("ejecutar_sql no guardó resultados.")
        return sql, df, resultado.raw
    except Exception:
        return _consultar_simple(pregunta)


if __name__ == "__main__":
    print("=" * 55)
    print("Pregúntale a la ENAHO 2024  (escribe 'salir' para terminar)")
    print("=" * 55)
    while True:
        pregunta = input("\nTu pregunta: ").strip()
        if not pregunta or pregunta.lower() in ("salir", "exit", "quit"):
            print("¡Listo!")
            break
        try:
            sql, df, texto = consultar(pregunta)
            print("\n--- SQL generado ---")
            print(sql)
            print("\n--- Resultado ---")
            print(df.to_string(index=False))
            print("\n--- Respuesta ---")
            print(texto)
        except Exception as e:
            print("\n[Error]", e)
