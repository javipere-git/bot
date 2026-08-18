"""
Escribir una planilla que Excel abra bien.

Lo usan todos los informes de la app (catalogo del broker, ejecuciones, ordenes,
trades cerrados). Esta separado para que la regla de "como se escribe una celda"
sea UNA sola y no tres parecidas.

Dos detalles que parecen chicos y no lo son:
  - Punto y coma y BOM: asi Excel en español lo abre en columnas de una, sin el
    asistente de importacion.
  - Lo que el broker NO informa queda VACIO, nunca en cero ni en "NO". "No me dijo
    cuanta comision cobro" no es lo mismo que "no cobro comision".
"""
from __future__ import annotations

import csv


def celda(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "SI" if valor else "NO"
    return str(valor)


def guardar(filas, columnas, ruta: str) -> str:
    """`columnas` es una lista de (clave interna, titulo que se ve). Devuelve la ruta."""
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([titulo for _, titulo in columnas])
        for fila in filas:
            w.writerow([celda(fila.get(clave)) for clave, _ in columnas])
    return ruta
