"""
validar_pobreza.py
-------------------------------------------------------------
Comprueba que el factor de expansión esté bien aplicado, replicando
la cifra OFICIAL de pobreza monetaria del INEI para 2024.

Clave metodológica: la pobreza oficial es el % de la POBLACIÓN (personas),
no de los hogares. Por eso se pondera por  factor07 * mieperho
(cada hogar "pesa" factor07 y contiene mieperho personas).

Objetivo INEI 2024:  pobreza total = 27.6 %   |   pobreza extrema = 5.5 %
                     población ≈ 34 millones  |   pobres ≈ 9.4 millones
-------------------------------------------------------------
"""
import duckdb

PARQUET = "data/enaho_hogar.parquet"
# pobreza: 1 = pobre extremo, 2 = pobre no extremo, 3 = no pobre
con = duckdb.connect()

# --- 1) Cifra nacional ------------------------------------------------
nacional = con.execute(f"""
    SELECT
        SUM(factor07 * mieperho)                                   AS poblacion,
        SUM(factor07 * mieperho) FILTER (WHERE pobreza IN (1, 2))  AS pobres,
        100.0 * SUM(factor07 * mieperho) FILTER (WHERE pobreza IN (1, 2))
              / SUM(factor07 * mieperho)                           AS tasa_pobreza,
        100.0 * SUM(factor07 * mieperho) FILTER (WHERE pobreza = 1)
              / SUM(factor07 * mieperho)                           AS tasa_pobreza_extrema
    FROM '{PARQUET}'
    WHERE pobreza IS NOT NULL AND mieperho IS NOT NULL AND factor07 IS NOT NULL
""").fetchone()

poblacion, pobres, tasa, tasa_ext = nacional
print("=" * 55)
print("VALIDACIÓN NACIONAL  (ENAHO 2024)")
print("=" * 55)
print(f"Población estimada : {poblacion:,.0f}   (INEI ≈ 34 millones)")
print(f"Personas en pobreza: {pobres:,.0f}   (INEI ≈ 9.4 millones)")
print(f"Tasa de pobreza    : {tasa:0.1f} %   (INEI oficial = 27.6 %)")
print(f"Pobreza extrema    : {tasa_ext:0.1f} %   (INEI oficial = 5.5 %)")

ok = abs(tasa - 27.6) < 1.0
print("\n", "✅ CUADRA: el factor está bien aplicado." if ok
      else "⚠️  No cuadra; revisa el factor o la variable pobreza.")

# --- 2) Por departamento (bonus para tu demo) -------------------------
# El departamento son los 2 primeros dígitos del ubigeo.
print("\n" + "=" * 55)
print("POBREZA POR DEPARTAMENTO (top y bottom 5)")
print("=" * 55)
dpto = con.execute(f"""
    SELECT
        SUBSTR(LPAD(CAST(ubigeo AS VARCHAR), 6, '0'), 1, 2)        AS cod_dpto,
        100.0 * SUM(factor07 * mieperho) FILTER (WHERE pobreza IN (1, 2))
              / SUM(factor07 * mieperho)                           AS tasa
    FROM '{PARQUET}'
    WHERE pobreza IS NOT NULL AND mieperho IS NOT NULL AND factor07 IS NOT NULL
    GROUP BY 1
    ORDER BY tasa DESC
""").df()
print("Más pobres:")
print(dpto.head(5).to_string(index=False))
print("\nMenos pobres:")
print(dpto.tail(5).to_string(index=False))
print("\n(Esperado: Cajamarca y Loreto arriba ~43%; Ica/Moquegua abajo ~5-8%)")
