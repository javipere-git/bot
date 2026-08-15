"""
Guardar el catalogo del broker en un archivo que abra Excel.

El catalogo es lo que el broker sabe de cada simbolo que lista (ver
Broker.catalogo()). Se baja para mirarlo con calma y decidir a mano que poner en
las excluidas, no para que el bot lo use.

Se escribe CSV con punto y coma y con BOM: asi Excel en español lo abre en
columnas de una, sin el asistente de importacion.
"""
from __future__ import annotations

import csv

# (clave interna, encabezado que se ve en Excel)
COLUMNAS = [
    ("symbol", "Simbolo"),
    ("bloqueada", "Bloqueada para abrir"),
    ("operable", "Operable"),
    ("prestable", "Prestable (ETB)"),
    ("costo_prestamo", "Costo prestamo %"),
    ("iliquida", "Iliquida"),
    ("marca_fraude", "Marca de fraude"),
    ("overnight_bloqueada", "Bloqueada overnight"),
    ("mercado", "Mercado"),
]


def _celda(valor) -> str:
    """None = este broker no informa el dato, y se deja la celda VACIA a proposito:
    un 'NO' ahi seria mentira (Alpaca no dice si una accion es iliquida, no dice
    que no lo sea)."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "SI" if valor else "NO"
    return str(valor)


def guardar_catalogo(filas, ruta: str) -> str:
    """Escribe las filas del catalogo. Devuelve la ruta."""
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([titulo for _, titulo in COLUMNAS])
        for fila in filas:
            w.writerow([_celda(fila.get(clave)) for clave, _ in COLUMNAS])
    return ruta
