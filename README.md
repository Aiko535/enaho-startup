# Pregúntale a la ENAHO

> Convertimos los microdatos de la ENAHO en respuestas, para que cualquiera consulte las cifras oficiales del Perú preguntando en español.

**Demo en vivo:** https://preguntale-enaho2024.streamlit.app/
**Video demo:** https://drive.google.com/drive/folders/198wgGx1aOeP5zuR6QZ4u3SCQ5xGf5LhA?usp=sharing

Proyecto final del curso **Data Science con Python 2026-I** (Universidad del Pacífico). Founder: **Aiko Yeckle Montoya**.

---

## ¿Qué hace?

La ENAHO (Encuesta Nacional de Hogares del INEI) es la fuente oficial de las cifras de pobreza, ingresos y servicios del Perú. Es pública, pero **inusable** para quien no programa: viene en 30+ módulos, con códigos crípticos y un factor de expansión que, mal aplicado, produce cifras erróneas.

**Pregúntale a la ENAHO** recibe una pregunta en español (ej. *"¿Cuál es la tasa de pobreza en Loreto?"*), genera la consulta SQL correcta —ponderada por el factor de expansión— y devuelve la respuesta interpretada, mostrando el SQL para que sea **auditable**.

Lo más importante: **no inventa cifras**. La herramienta reproduce las cifras oficiales del INEI 2024 al decimal (pobreza nacional 27.6%, pobreza extrema 5.5%), lo que se verifica con el script `scripts/validar_pobreza.py`.

---

## Herramientas del curso usadas (y dónde en el código)

| Herramienta | Dónde se usa | Para qué |
|---|---|---|
| **Gemini API** (tipo OpenAI) | `backend/agente.py` → `generar_sql()` e `interpretar()` (modelo `gemini-2.5-flash`) | Traduce la pregunta a SQL e interpreta el resultado en español |
| **crewAI** | `backend/agente.py` → `_hacer_crew()` (Crew con 2 agentes: *Analista SQL* y *Redactor*) y la tool `ejecutar_sql` | Orquesta el flujo en agentes especializados |

Complementos de la arquitectura: **DuckDB** (motor SQL embebido que consulta el parquet sin servidor, en la tool `ejecutar_sql`) y **Streamlit** (interfaz, en `frontend/app.py`).

---

## Arquitectura

```
Usuario → Streamlit (frontend/app.py)
        → crewAI (backend/agente.py)
            1. Agente Analista SQL  → escribe el SQL (Gemini)
            2. Tool ejecutar_sql    → ejecuta en DuckDB sobre el parquet
            3. Agente Redactor      → interpreta el resultado (Gemini)
        → respuesta en español
Datos: data/enaho_hogar.parquet (ENAHO 2024, INEI) + data/catalogo_mini.json
```

Diagrama detallado en `docs/arquitectura.svg`.

---

## Cómo correrlo localmente

Requiere **Python 3.12**.

```bash
# 1. Clonar
git clone https://github.com/Aiko535/enaho-startup.git
cd enaho-startup

# 2. Entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

# 3. Dependencias
pip install -r requirements.txt

# 4. Variable de entorno: crea un archivo .env con tu clave de Gemini
#    (puedes copiar .env.example). Consíguela gratis en aistudio.google.com
echo GEMINI_API_KEY=tu_clave_aqui > .env

# 5. Correr
streamlit run frontend/app.py
```

La app abre en `http://localhost:8501`.

---

## Estructura del repositorio

```
enaho-startup/
├── frontend/
│   └── app.py                  # interfaz Streamlit
├── backend/
│   └── agente.py               # agente crewAI: Gemini (SQL) + DuckDB + Gemini (redacción)
├── data/
│   ├── enaho_hogar.parquet     # microdatos ENAHO 2024 (módulos vivienda + sumaria)
│   ├── catalogo_mini.json      # catálogo curado de variables (el "cerebro" del agente)
│   └── catalogo_completo.json
├── scripts/
│   ├── cargar_enaho.py         # descarga y unión de los módulos de la ENAHO
│   ├── recortar_catalogo.py    # genera el catálogo curado de variables
│   └── validar_pobreza.py      # validación contra cifras oficiales del INEI
├── docs/
│   ├── arquitectura.svg        # diagrama de arquitectura
│   ├── dossier.pdf             # pitch deck (formato Y Combinator)
│   └── research/               # evidencias de validación (capturas, evidencia.md)
├── requirements.txt
├── .env.example                # plantilla de variables (la clave real NUNCA se sube)
├── .gitignore · LICENSE · README.md
```

---

## Datos y metodología

- **Fuente:** ENAHO 2024, INEI (metodología actualizada). Microdatos públicos de los módulos de vivienda (100) y sumaria (34), unidos a nivel de hogar.
- **Factor de expansión:** todas las estimaciones se ponderan por `factor07`; las poblacionales por `factor07 * mieperho`.
- **Validación:** `scripts/validar_pobreza.py` reproduce la tasa de pobreza oficial 2024 (27.6%) y el ranking departamental, confirmando que el pipeline es correcto.

---

## Uso de IA en el desarrollo

El frontend y partes del backend fueron generados/asistidos con **Claude Code**, bajo revisión del autor. La lógica de dominio (catálogo de variables, reglas metodológicas y validación) es propia.

---

## Licencia

MIT — ver `LICENSE`.