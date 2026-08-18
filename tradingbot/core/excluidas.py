"""
Simbolos que el bot NO tiene que operar.

Son VARIAS listas separadas a proposito, y esa separacion es el punto:

  LAS TUYAS  - varias, cada una con su nombre, para que se sepa POR QUE esta
               excluido cada simbolo: impuestos, sin liquidez, siempre pierdo...
               Sin el motivo, en un mes la lista es una bolsa de simbolos sueltos
               que despues nadie se anima a tocar.
  DEL BROKER - las que el broker tiene bloqueadas para abrir posicion. Cambian
               solas y son cientos (medido el 15/08/2026: 394 en Tastytrade,
               863 en Alpaca).

Si estuvieran todas juntas, cada vez que quisieras actualizar la del broker
tendrias que volver a cargar las tuyas, y no sabrias cual sacar cuando cambia el
motivo. Separadas, cada una se renueva sin tocar las otras.

SON DOS ARCHIVOS, y esto tambien tiene su porque (aprendido a los golpes el
18/08/2026, cuando la actualizacion se trabo en la PC de Tasty):

  config/excluidas.txt         LAS TUYAS. Va al repo y te sigue a las tres PCs.
                               Son tus criterios: no dependen del broker.
  config/excluidas_broker.txt  LA DEL BROKER. NO va al repo, es de cada PC.

La del broker no puede viajar: es DISTINTA en cada broker. Medido el 15/08/2026,
Alpaca bloquea 863 simbolos y Tastytrade 394, y no son los mismos. Mandarle a la
PC de Tasty la lista de Alpaca no solo no sirve: excluye simbolos que Tasty si
opera. Ademas la reescribe cada vez que apretas "Traer del broker", asi que si
viajara chocaria con el repo en cada actualizacion (fue exactamente lo que paso).
"""
from __future__ import annotations

import os
import re

_MARCA_MIA = "# === MIAS: "
_FIN = " ==="
_SEP_BROKER = "# === DEL BROKER (bloqueadas para abrir) ==="

# Con que nombres arranca el cuadro la primera vez. Son EDITABLES: lo unico fijo
# es cuantas listas hay.
NOMBRES_POR_DEFECTO = ["Impuestos", "Sin liquidez", "Siempre pierdo", "Otras"]
CUANTAS_MIAS = len(NOMBRES_POR_DEFECTO)

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUTA = os.path.join(_RAIZ, "config", "excluidas.txt")


def _ruta_broker(ruta: str | None) -> str:
    """El archivo de la lista del broker, al lado del de las tuyas."""
    base = ruta or RUTA
    raiz, ext = os.path.splitext(base)
    return f"{raiz}_broker{ext or '.txt'}"


def _limpiar(texto: str) -> list[str]:
    """Saca comentarios y separadores, y normaliza los simbolos.
    Acepta lo mismo que la watchlist: comas, espacios, saltos, punto y coma."""
    sin_comentarios = "\n".join(
        l for l in str(texto or "").splitlines() if not l.strip().startswith("#")
    )
    crudos = re.split(r"[\s,;]+", sin_comentarios)
    vistos, out = set(), []
    for s in crudos:
        s = s.strip().upper().lstrip("$")
        if s and s not in vistos:
            vistos.add(s)
            out.append(s)
    return out


def _nombre_limpio(nombre: str, i: int) -> str:
    """El nombre viaja dentro de una linea de comentario, asi que no puede llevar
    saltos ni el cierre del separador. Si queda vacio, se le pone uno."""
    limpio = " ".join(str(nombre or "").split()).replace("=", "-")
    return limpio or f"Lista {i + 1}"


def leer(ruta: str | None = None) -> tuple[list[tuple[str, list[str]]], list[str]]:
    """Devuelve (mias, del_broker).

    `mias` es una lista de (nombre, simbolos), siempre de CUANTAS_MIAS elementos:
    la pantalla tiene esa cantidad de cuadros fijos, asi que se completa con las
    que falten. Si el archivo no existe, todas vacias."""
    vacias = [(n, []) for n in NOMBRES_POR_DEFECTO]
    try:
        with open(ruta or RUTA, encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        texto = ""

    arriba, _, abajo = texto.partition(_SEP_BROKER)
    try:
        with open(_ruta_broker(ruta), encoding="utf-8") as f:
            del_broker = _limpiar(f.read())
    except OSError:
        # Todavia no existe el archivo aparte: se toma la seccion que quedo dentro
        # del archivo viejo, asi la primera actualizacion no te borra la lista.
        del_broker = _limpiar(abajo)
    if not texto:
        return (vacias, del_broker)

    mias: list[tuple[str, list[str]]] = []
    bloque: list[str] = []
    nombre: str | None = None
    for linea in arriba.splitlines():
        if linea.startswith(_MARCA_MIA):
            if nombre is not None:
                mias.append((nombre, _limpiar("\n".join(bloque))))
            nombre = linea[len(_MARCA_MIA):].removesuffix(_FIN).strip()
            bloque = []
        elif nombre is not None:
            bloque.append(linea)
    if nombre is not None:
        mias.append((nombre, _limpiar("\n".join(bloque))))

    if not mias:
        # Archivo del formato viejo (una sola lista "mias", sin nombre). Se lee igual
        # y cae en el primer cuadro: no se pierde nada de lo que ya habias cargado.
        sueltos = _limpiar(arriba)
        if sueltos:
            mias = [(NOMBRES_POR_DEFECTO[0], sueltos)]

    while len(mias) < CUANTAS_MIAS:
        usados = {n for n, _ in mias}
        libre = next((n for n in NOMBRES_POR_DEFECTO if n not in usados),
                     f"Lista {len(mias) + 1}")
        mias.append((libre, []))
    return (mias, del_broker)


def guardar(mias, del_broker, ruta: str | None = None) -> str:
    """Escribe las listas en SUS DOS archivos. Devuelve la ruta de las tuyas.

    `mias` es una lista de (nombre, simbolos). Se guardan TODAS, incluso las
    vacias: el cuadro tiene que volver a abrirse con los mismos nombres."""
    ruta = ruta or RUTA
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    partes = [
        "# Simbolos que VOS decidiste no operar. Este archivo SI va al repositorio:",
        "# son tus criterios, no dependen del broker, y te siguen a las tres PCs.",
        "# La lista de bloqueadas del broker va aparte, en excluidas_broker.txt,",
        "# porque es distinta en cada broker y se rehace con un boton.",
        "# Cada lista tiene su nombre para saber POR QUE esta excluido cada uno.",
        "",
    ]
    for i, (nombre, simbolos) in enumerate(mias):
        partes.append(f"{_MARCA_MIA}{_nombre_limpio(nombre, i)}{_FIN}")
        partes += _limpiar("\n".join(simbolos) if not isinstance(simbolos, str)
                           else simbolos)
        partes.append("")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(partes))

    del_broker = _limpiar("\n".join(del_broker) if not isinstance(del_broker, str)
                          else del_broker)
    cabecera = [
        "# Simbolos que EL BROKER tiene bloqueados para abrir posicion.",
        "# Este archivo NO va al repositorio: es distinto en cada broker (medido el",
        "# 15/08/2026: Alpaca 863, Tastytrade 394) y lo rehace el boton",
        "# 'Traer del broker'. Cada PC tiene el suyo.",
        "",
    ]
    with open(_ruta_broker(ruta), "w", encoding="utf-8") as f:
        f.write("\n".join(cabecera + del_broker + [""]))
    return ruta


def todas(ruta: str | None = None) -> dict[str, str]:
    """Todos los simbolos excluidos -> el nombre de la lista de donde salen.

    Es un diccionario y no un conjunto para que el bot pueda decir POR QUE saltea
    cada simbolo. Se usa igual (`simbolo in excluidas`), asi que el motor sirve
    con las dos cosas y los tests viejos que pasan un conjunto siguen andando."""
    mias, broker = leer(ruta)
    fuera: dict[str, str] = {}
    for nombre, simbolos in mias:
        for s in simbolos:
            fuera.setdefault(s, nombre)
    for s in broker:
        fuera.setdefault(s, "bloqueadas por el broker")
    return fuera
