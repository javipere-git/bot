"""
El historial de operaciones de la cuenta, guardado en un archivo que abre Excel.

PARA QUE: las paginas de los brokers son un espanto para esto. En Alpaca no hay
boton de descargar: hay que seleccionar la tabla a mano, pagina por pagina, o
bajar un PDF por dia. La API, en cambio, lo entrega entero en segundos.

Son EJECUCIONES, no ordenes. Una orden puede llenarse en varios pedazos y a
precios distintos; lo que importa para revisar como te fue es lo que de verdad
se hizo, que es esto.

Igual que el catalogo: CSV con punto y coma y con BOM, para que Excel en español
lo abra en columnas de una.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

# (clave interna, encabezado que se ve en Excel)
COLUMNAS = [
    ("fecha_hora", "Fecha y hora (NY)"),
    ("symbol", "Simbolo"),
    ("lado", "Lado"),
    ("cantidad", "Cantidad"),
    ("precio", "Precio"),
    ("importe", "Importe"),
    ("comision", "Comision"),
    ("tasas", "Tasas"),
    ("neto", "Neto"),
    ("order_id", "ID de la orden"),
    ("id_ejecucion", "ID de la ejecucion"),
    ("notas", "Notas"),
]


def a_hora_ny(iso: str | None) -> str:
    """Pasa una marca de tiempo del broker a la hora de NUEVA YORK.

    Todos mandan UTC, que a la vista es confuso: un fill de las 10:44 de la mañana
    figura como 14:44. Se convierte a la hora del mercado, que es la que ves en la
    pantalla del broker.

    Si el broker solo informa la fecha (Tradier: su historial no trae hora), se
    devuelve la fecha sola en vez de inventar un horario."""
    if not iso:
        return ""
    txt = str(iso).strip().replace("Z", "+00:00")
    try:
        t = datetime.fromisoformat(txt)
    except ValueError:
        return str(iso)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    if t.hour == 0 and t.minute == 0 and t.second == 0:
        return t.date().isoformat()      # el broker no informo la hora
    return t.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S")


def _celda(valor) -> str:
    """None = el broker no informa el dato; celda VACIA, no un cero (un cero seria
    mentira: 'no me dijo cuanta comision cobro' no es 'no cobro comision')."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "SI" if valor else "NO"
    return str(valor)


def guardar_operaciones(filas, ruta: str) -> str:
    """Escribe las operaciones, de la mas vieja a la mas nueva. Devuelve la ruta."""
    ordenadas = sorted(filas, key=lambda f: str(f.get("fecha_hora") or ""))
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([titulo for _, titulo in COLUMNAS])
        for fila in ordenadas:
            w.writerow([_celda(fila.get(clave)) for clave, _ in COLUMNAS])
    return ruta


def resumen(filas) -> str:
    """Una linea para el registro: cuantas, de cuando a cuando, cuantos simbolos."""
    if not filas:
        return "no hay operaciones en esas fechas"
    fechas = sorted(str(f.get("fecha_hora") or "") for f in filas)
    simbolos = {f.get("symbol") for f in filas if f.get("symbol")}
    return (f"{len(filas):,} operacion(es) de {len(simbolos):,} simbolo(s), "
            f"del {fechas[0][:10]} al {fechas[-1][:10]}")
