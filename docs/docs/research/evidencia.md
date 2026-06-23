# Evidencia de validación del problema

Este documento resume la evidencia que sustenta el problema que resuelve
**Pregúntale a la ENAHO**: que los microdatos de la ENAHO son públicos pero
inusables para quien no programa. Toda la evidencia es **pública y verificable**
(no opinión).

## 1. Tutoriales de YouTube: la barrera técnica es real y masiva

Una búsqueda de "ENAHO Stata tutorial" en YouTube devuelve múltiples videos
dedicados *solo a preparar* la ENAHO antes de poder analizarla (descargar, leer el
diccionario y unir módulos). Que existan tutoriales largos y con miles de vistas
demuestra que la barrera técnica es real y extendida.

| Captura | Video | Qué demuestra |
|---|---|---|
| `enaho youtube.png` | "Stata: Compilando información de la ENAHO INEI Perú 2011-2022" (~1.5K vistas, 57 min) | Se necesita casi una hora solo para **unir los módulos** |
| `enaho youtube 2.png` | "Midiendo la Pobreza con Enaho 2020" (~2.8K vistas) | Hay videos solo para explicar cómo aplicar el **factor de expansión (`factor07`)** |
| `enaho youtube 3.png` | "Medición del Empleo con Enaho" (~1K vistas) | Cada módulo requiere su propio tutorial |


## 2. Demostración del error silencioso del factor de expansión

El script `scripts/validar_pobreza.py` muestra que, ponderando correctamente por
`factor07 * mieperho`, la tasa de pobreza 2024 da **27.6%** — idéntica a la cifra
oficial del INEI. Sin el factor (o contando hogares en vez de personas), el número
sale equivocado. Esa diferencia cuantifica el riesgo de error que nuestra
herramienta elimina.

## 3. Estructura de la ENAHO (barrera documentada por el propio INEI)

Los microdatos vienen en 30+ módulos separados, con códigos crípticos y un
diccionario oficial de ~3,800 KB, y requieren software estadístico (Stata/R/Python).
Fuente: portal de microdatos del INEI (ENAHO 2024).

## 4. Pruebas de usuario 

`pruebas_usuarios.png` — capturas de personas reales usando el demo y su feedback.
*(Evidencia complementaria; la validación principal está en los puntos 1-3.)*
