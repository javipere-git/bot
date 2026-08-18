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

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .planilla import guardar as _guardar_planilla

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

# El otro informe: las ORDENES. Aca esta lo que pediste, se haya hecho o no.
COLUMNAS_ORDENES = [
    ("fecha_hora", "Fecha y hora (NY)"),
    ("symbol", "Simbolo"),
    ("lado", "Lado"),
    ("estado", "Estado"),
    ("cantidad", "Cantidad"),
    ("cantidad_ejecutada", "Cantidad ejecutada"),
    ("precio_limite", "Precio limite"),
    ("precio_promedio", "Precio promedio"),
    ("motivo_rechazo", "Motivo del rechazo"),
    ("duracion", "Duracion"),
    ("order_id", "ID de la orden"),
    ("notas", "Notas"),
]

# Los estados que puede tener una orden, ya traducidos por el conector. El orden
# es el que se ve en la pantalla, de lo mas frecuente a lo menos.
ESTADOS = ["Ejecutada", "Ejecutada en parte", "Cancelada", "Rechazada",
           "Reemplazada", "Vencida", "Viva"]


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


def _por_fecha(filas):
    return sorted(filas, key=lambda f: str(f.get("fecha_hora") or ""))


def guardar_operaciones(filas, ruta: str) -> str:
    """Escribe las ejecuciones, de la mas vieja a la mas nueva. Devuelve la ruta."""
    return _guardar_planilla(_por_fecha(filas), COLUMNAS, ruta)


def guardar_ordenes(filas, ruta: str) -> str:
    """Escribe las ordenes, de la mas vieja a la mas nueva. Devuelve la ruta."""
    return _guardar_planilla(_por_fecha(filas), COLUMNAS_ORDENES, ruta)


def filtrar_por_estado(filas, estados) -> list[dict]:
    """Deja solo las ordenes con alguno de esos estados. Sin estados = todas.

    Compara contra la lista pedida y no al reves: si el broker devuelve un estado
    que no conociamos, no se cuela por accidente en un filtro."""
    if not estados:
        return list(filas)
    pedidos = {str(e) for e in estados}
    return [f for f in filas if str(f.get("estado")) in pedidos]


def resumen_ordenes(filas) -> str:
    """Una linea para el registro: cuantas de cada estado."""
    if not filas:
        return "no hay ordenes en esas fechas"
    cuenta: dict[str, int] = {}
    for f in filas:
        clave = str(f.get("estado") or "?")
        cuenta[clave] = cuenta.get(clave, 0) + 1
    detalle = ", ".join(f"{n:,} {e.lower()}(s)"
                        for e, n in sorted(cuenta.items(), key=lambda x: -x[1]))
    return f"{len(filas):,} orden(es): {detalle}"


def resumen(filas) -> str:
    """Una linea para el registro: cuantas, de cuando a cuando, cuantos simbolos."""
    if not filas:
        return "no hay operaciones en esas fechas"
    fechas = sorted(str(f.get("fecha_hora") or "") for f in filas)
    simbolos = {f.get("symbol") for f in filas if f.get("symbol")}
    return (f"{len(filas):,} operacion(es) de {len(simbolos):,} simbolo(s), "
            f"del {fechas[0][:10]} al {fechas[-1][:10]}")
