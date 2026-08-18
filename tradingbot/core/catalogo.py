"""
Guardar el catalogo del broker en un archivo que abra Excel.

El catalogo es lo que el broker sabe de cada simbolo que lista (ver
Broker.catalogo()). Se baja para mirarlo con calma y decidir a mano que poner en
las excluidas, no para que el bot lo use.

Se escribe CSV con punto y coma y con BOM: asi Excel en español lo abre en
columnas de una, sin el asistente de importacion.
"""
from __future__ import annotations

from .planilla import guardar as _guardar_planilla

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


def guardar_catalogo(filas, ruta: str) -> str:
    """Escribe las filas del catalogo. Devuelve la ruta.

    Lo que este broker no informa queda en blanco a proposito: un 'NO' ahi seria
    mentira (Alpaca no dice que una accion NO sea iliquida; no dice nada)."""
    return _guardar_planilla(filas, COLUMNAS, ruta)
