"""
cargar_enaho.py
-------------------------------------------------------------
Pregúntale a la ENAHO - Paso 1: preparación de datos.

Qué hace:
  1. Lee los .sav de la ENAHO 2024 con pyreadstat (conservando las
     ETIQUETAS de variables y de valores, que es lo que el .sav tiene y
     el .csv pierde).
  2. Mergea Módulo 100 (vivienda/hogar) + Sumaria (módulo 34) a nivel HOGAR.
  3. Guarda la tabla en parquet (data/enaho_hogar.parquet).
  4. Genera dos catálogos de variables a partir de las etiquetas REALES
     del archivo (no de memoria): el completo y uno curado por palabras
     clave. El curado es lo que luego le pasas al LLM para que NO alucine
     códigos de variable.

Requisitos:  pip install pyreadstat pandas pyarrow
Uso:         python cargar_enaho.py
-------------------------------------------------------------
"""

import json
from pathlib import Path

import pyreadstat

# =====================================================================
# CONFIG  -- ajusta BASE a tu carpeta de Descargas si hace falta.
# El script busca los .sav de forma recursiva, así que no importa el
# anidamiento "966-Modulo01/966-Modulo01/...".
# =====================================================================
BASE = Path(__file__).resolve().parent
SALIDA = Path("data")
SALIDA.mkdir(exist_ok=True)

# Archivos a nivel HOGAR (los del MVP). Se identifican por nombre de archivo.
ARCHIVOS_HOGAR = {
    "vivienda": "Enaho01-2024-100.sav",   # Módulo 100
    "sumaria":  "Sumaria-2024.sav",       # Módulo 34  (NO el -12g)
}
LLAVES = ["conglome", "vivienda", "hogar"]

# Palabras clave para el catálogo curado (se buscan dentro de las
# etiquetas reales del archivo, en minúsculas).
CLAVES_INTERES = {
    "pobreza":       ["pobreza", "pobre"],
    "ingreso":       ["ingreso"],
    "gasto":         ["gasto"],
    "agua":          ["agua"],
    "saneamiento":   ["servicio higi", "desague", "desagüe", "higiénico", "higienico"],
    "electricidad":  ["electric", "alumbrado"],
    "factor":        ["factor"],
    "geografia":     ["ubigeo", "dominio", "estrato", "departamento", "area", "área", "región", "region"],
    "miembros":      ["miembros", "perceptores", "personas"],
}


# =====================================================================
# Funciones
# =====================================================================
def encontrar(nombre_archivo: str) -> Path:
    """Busca un .sav por nombre dentro de BASE (recursivo)."""
    candidatos = list(BASE.rglob(nombre_archivo))
    if not candidatos:
        raise FileNotFoundError(
            f"No encontré '{nombre_archivo}' dentro de {BASE}.\n"
            f"   Revisa la ruta BASE arriba o mueve los .sav a esa carpeta."
        )
    return candidatos[0]


def cargar_sav(ruta: Path):
    """Lee un .sav devolviendo (df, etiquetas_vars, etiquetas_valores)."""
    try:
        df, meta = pyreadstat.read_sav(str(ruta))
    except Exception:
        # algunos .sav del INEI vienen en latin-1
        df, meta = pyreadstat.read_sav(str(ruta), encoding="latin1")

    df.columns = [c.lower() for c in df.columns]
    etiquetas = {k.lower(): v for k, v in meta.column_names_to_labels.items()}
    valores = {
        k.lower(): {str(val): lab for val, lab in d.items()}
        for k, d in meta.variable_value_labels.items()
    }
    print(f"   {ruta.name}: {df.shape[0]:,} filas x {df.shape[1]} columnas")
    return df, etiquetas, valores


def normalizar_llaves(df):
    """Las llaves a veces vienen como float/str; las dejamos como texto limpio."""
    for k in LLAVES:
        if k in df.columns:
            df[k] = df[k].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    return df


# =====================================================================
# 1) Cargar módulos a nivel hogar
# =====================================================================
print("Cargando módulos (nivel hogar)...")
df_viv, et_viv, val_viv = cargar_sav(encontrar(ARCHIVOS_HOGAR["vivienda"]))
df_sum, et_sum, val_sum = cargar_sav(encontrar(ARCHIVOS_HOGAR["sumaria"]))

df_viv = normalizar_llaves(df_viv)
df_sum = normalizar_llaves(df_sum)

# =====================================================================
# 2) Merge a nivel hogar  (Sumaria como base; trae pobreza/ingreso/factor)
# =====================================================================
print("\nUniendo Sumaria + Vivienda por", LLAVES, "...")
nuevas_de_viv = [c for c in df_viv.columns if c not in df_sum.columns or c in LLAVES]
# Seguro: cada hogar debe ser una fila única en el módulo de vivienda
dups = df_viv.duplicated(subset=LLAVES).sum()
if dups:
    print(f"   (aviso: {dups} llaves duplicadas en Vivienda; me quedo con la primera)")
    df_viv = df_viv.drop_duplicates(subset=LLAVES, keep="first")
hogar = df_sum.merge(
    df_viv[nuevas_de_viv], on=LLAVES, how="left", indicator=True
)

emparejados = (hogar["_merge"] == "both").mean()
print(f"   Hogares en Sumaria : {len(df_sum):,}")
print(f"   % emparejados c/Viv: {emparejados:0.1%}")
hogar = hogar.drop(columns="_merge")

# Diagnóstico clave: ¿cómo se llama el factor de expansión?
cols_factor = [c for c in hogar.columns if c.startswith("factor")]
print(f"\n   >>> COLUMNAS DE FACTOR DETECTADAS: {cols_factor}")
print("       (confírmalo contra el Diccionario; suele ser 'factor07' o 'factora07')")

# =====================================================================
# 3) Guardar parquet
# =====================================================================
ruta_parquet = SALIDA / "enaho_hogar.parquet"
hogar.to_parquet(ruta_parquet, index=False)
print(f"\nGuardado: {ruta_parquet}  ({len(hogar):,} hogares, {hogar.shape[1]} columnas)")

# =====================================================================
# 4) Catálogos de variables (desde las etiquetas REALES del archivo)
# =====================================================================
etiquetas = {**et_viv, **et_sum}
valores = {**val_viv, **val_sum}

catalogo = {}
for col in hogar.columns:
    catalogo[col] = {
        "etiqueta": etiquetas.get(col) or "",
        "valores": valores.get(col, {}),
    }

(SALIDA / "catalogo_completo.json").write_text(
    json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8"
)

# Catálogo curado: variables cuya etiqueta contiene alguna palabra clave
curado = {}
for tema, terminos in CLAVES_INTERES.items():
    for col, info in catalogo.items():
        etq = (info["etiqueta"] or "").lower()
        if any(t in etq or t in col for t in terminos):
            curado[col] = {"tema": tema, **info}

# Asegura que las llaves siempre estén en el catálogo curado
for k in LLAVES:
    if k in catalogo:
        curado.setdefault(k, {"tema": "llave", **catalogo[k]})

(SALIDA / "catalogo_curado.json").write_text(
    json.dumps(curado, ensure_ascii=False, indent=2), encoding="utf-8"
)

print(f"\nCatálogo completo: {len(catalogo)} variables -> data/catalogo_completo.json")
print(f"Catálogo curado  : {len(curado)} variables -> data/catalogo_curado.json")
print("\nVista rápida del catálogo curado:")
for col, info in list(curado.items())[:25]:
    print(f"   {col:14s} | {info.get('tema',''):12s} | {(info['etiqueta'] or '')[:50]}")

print("\nListo. Siguiente paso: el agente text-to-SQL sobre data/enaho_hogar.parquet")
