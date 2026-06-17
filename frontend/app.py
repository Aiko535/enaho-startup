"""frontend/app.py — Interfaz Streamlit para Pregúntale a la ENAHO 2024."""
import sys, os

# Añade la raíz del proyecto al path para que "from backend.agente import consultar"
# funcione al ejecutar: streamlit run frontend/app.py (desde la raíz del proyecto)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

from backend.agente import consultar


# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Pregúntale a la ENAHO 2024",
    page_icon="📊",
    layout="wide",
)

st.title("Pregúntale a la ENAHO 2024")
st.caption(
    "Responde preguntas sobre los microdatos de la ENAHO (INEI) en lenguaje natural."
)

# ---------------------------------------------------------------------------
# Sección informativa: alcance de la herramienta
# ---------------------------------------------------------------------------
st.info(
    "Esta herramienta responde con microdatos de la ENAHO 2024 (INEI), a nivel de "
    "hogares. Pregunta sobre: pobreza, ingreso y gasto, servicios básicos (agua, luz, "
    "desagüe, cocina) y tamaño del hogar — a nivel nacional o por departamento."
)

with st.expander("¿Qué puedo preguntar?"):
    st.markdown(
        """
**Pobreza**
- ¿Cuál es la tasa de pobreza extrema en Cajamarca?
- ¿Cómo se compara la pobreza entre la sierra y la costa?

**Ingreso y gasto**
- ¿Cuál es el ingreso promedio de los hogares por departamento?
- ¿Cuánto gasta en promedio un hogar pobre no extremo?

**Servicios básicos**
- ¿Qué porcentaje de hogares tiene acceso a agua potable?
- ¿Cuántos hogares cocinan con leña o carbón?

**Demografía del hogar**
- ¿Cuál es el número promedio de miembros por hogar en Puno?
- ¿Cuántos hogares tienen más de un perceptor de ingreso?
"""
    )

# ---------------------------------------------------------------------------
# Estado inicial de la sesión
# ---------------------------------------------------------------------------
if "pregunta" not in st.session_state:
    st.session_state.pregunta = ""

# Guarda el último resultado para que no desaparezca al re-renderizar la página.
# Formato: ("ok", sql, df, interpretacion) | ("error", mensaje) | None
if "resultado" not in st.session_state:
    st.session_state.resultado = None

# ---------------------------------------------------------------------------
# Botones de preguntas de ejemplo
# Al hacer clic, el texto del botón rellena la caja de pregunta vía session_state.
# ---------------------------------------------------------------------------
EJEMPLOS = [
    "¿Cuál es la tasa de pobreza en Loreto?",
    "¿Cuántas personas pobres hay en el Perú?",
    "¿Cuál es el ingreso promedio de hogares pobres?",
    "¿Cuántos hogares hay por nivel de pobreza?",
]

st.markdown("**Preguntas de ejemplo:**")
cols = st.columns(len(EJEMPLOS))
for i, (col, ejemplo) in enumerate(zip(cols, EJEMPLOS)):
    with col:
        if st.button(ejemplo, key=f"ej_{i}", use_container_width=True):
            st.session_state.pregunta = ejemplo

# ---------------------------------------------------------------------------
# Caja de pregunta y botón de consulta
# El key="pregunta" vincula el widget con st.session_state.pregunta,
# por lo que los botones de ejemplo y el usuario comparten el mismo valor.
# ---------------------------------------------------------------------------
pregunta = st.text_input(
    "Tu pregunta:",
    key="pregunta",
    placeholder="Ej. ¿Cuál es la tasa de pobreza en Lima?",
)

consultar_btn = st.button("Consultar", type="primary")

# ---------------------------------------------------------------------------
# Lógica de consulta
# ---------------------------------------------------------------------------
if consultar_btn:
    if not pregunta.strip():
        st.warning("Por favor ingresa una pregunta.")
    else:
        with st.spinner("Consultando la ENAHO..."):
            try:
                sql, df, interpretacion = consultar(pregunta)
                st.session_state.resultado = ("ok", sql, df, interpretacion)
            except Exception as e:
                st.session_state.resultado = ("error", str(e))

# ---------------------------------------------------------------------------
# Mostrar resultados (persisten en session_state entre rerenders)
# ---------------------------------------------------------------------------
if st.session_state.resultado is not None:
    tipo = st.session_state.resultado[0]

    if tipo == "error":
        st.error(f"Error al consultar: {st.session_state.resultado[1]}")

    else:
        _, sql, df, interpretacion = st.session_state.resultado

        # Interpretación del modelo de forma prominente
        st.success(interpretacion)

        if df is not None and not df.empty:
            col_nums = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            col_cats = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]

            # Caso especial: una sola celda numérica
            if df.shape == (1, 1) and col_nums:
                valor = df.iloc[0, 0]
                col_nombre = df.columns[0].lower()

                # Solo mostramos st.metric para conteos grandes e inequívocos (>= 1000).
                # Valores pequeños (tasas, porcentajes, promedios) los comunica la frase verde.
                if valor >= 1_000:
                    es_dinero = any(p in col_nombre for p in ("ingreso", "gasto", "monto", "sueldo"))
                    if valor >= 1_000_000:
                        valor_fmt = f"{valor / 1_000_000:.1f} millones"
                    else:
                        valor_fmt = f"{valor:,.0f}"
                    if es_dinero:
                        valor_fmt = f"S/ {valor_fmt}"
                    st.metric(label=df.columns[0], value=valor_fmt)

            else:
                # Tabla completa
                st.dataframe(df, use_container_width=True)

                # Gráfico de barras cuando hay al menos una columna categórica
                # y una numérica, y más de una fila (un solo dato no necesita gráfico)
                if col_cats and col_nums and len(df) > 1:
                    chart_df = df.set_index(col_cats[0])[[col_nums[0]]]
                    st.bar_chart(chart_df)

        # SQL generado, oculto por defecto para no distraer al usuario
        with st.expander("Ver el SQL generado"):
            st.code(sql, language="sql")

# ---------------------------------------------------------------------------
# Nota al pie con la fuente de los datos
# ---------------------------------------------------------------------------
st.caption(
    "Fuente: ENAHO 2024, INEI. Cifras ponderadas con el factor de expansión. "
    "Solo cubre las variables disponibles a nivel de hogar."
)
