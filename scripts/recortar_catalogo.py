"""
recortar_catalogo.py
-------------------------------------------------------------
Reduce data/catalogo_completo.json a un catálogo "mini" con SOLO las
variables que un usuario real preguntaría. Lista elegida a mano a partir
de los nombres reales de tu ENAHO 2024.

Por qué: pasarle cientos de variables al LLM gasta tokens y lo confunde.
Con ~24 variables limpias, el agente escribe mejor SQL y más barato.
-------------------------------------------------------------
"""
import json
from pathlib import Path

catalogo = json.loads(Path("data/catalogo_completo.json").read_text(encoding="utf-8"))

# Lista final, elegida a mano. Si quieres agregar o quitar, edita aquí.
WHITELIST = [
    # --- llaves y geografía ---
    "conglome", "vivienda", "hogar", "ubigeo", "dominio", "estrato",
    # --- demografía del hogar ---
    "mieperho",   # total de miembros del hogar
    "percepho",   # perceptores de ingresos
    # --- ingreso y gasto TOTAL del hogar (los consolidados, no los desagregados) ---
    "inghog1d",   # ingreso bruto
    "inghog2d",   # ingreso neto total
    "gashog1d",   # gasto monetario
    "gashog2d",   # gasto total bruto
    # --- pobreza ---
    "pobreza",    # 1=pobre extremo, 2=pobre no extremo, 3=no pobre
    "pobrezav",   # pobre y vulnerable
    "linea",      # linea de pobreza total
    "linpe",      # linea de pobreza extrema (alimentaria)
    # --- factor de expansion ---
    "factor07",
    # --- servicios basicos (versiones limpias, no los montos/deflactados) ---
    "t110",       # abastecimiento de agua (recodificada)
    "p110",       # procedencia del agua
    "p110a1",     # el agua es potable
    "p110c",      # acceso al agua todos los dias
    "t111a",      # servicio higienico / bano (recodificada)
    "p1121",      # alumbrado por electricidad
    "p1131",      # combustible para cocinar
]

mini = {col: catalogo[col] for col in WHITELIST if col in catalogo}

faltantes = [c for c in WHITELIST if c not in catalogo]
if faltantes:
    print(f"(aviso: no encontre estas en tu base: {faltantes})\n")

Path("data/catalogo_mini.json").write_text(
    json.dumps(mini, ensure_ascii=False, indent=2), encoding="utf-8"
)

print(f"Catalogo mini: {len(mini)} variables (de {len(catalogo)})\n")
for col, info in mini.items():
    print(f"  {col:12s} | {(info.get('etiqueta') or '')[:55]}")
print("\nGuardado en data/catalogo_mini.json")
