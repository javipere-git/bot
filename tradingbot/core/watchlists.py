"""
Watchlists guardadas: listas de simbolos con nombre, a un click.

PARA QUE: la watchlist se arma a mano o con el boton de ETB (que trae miles de
simbolos). Volver a armarla cada vez es tedioso, y peor todavia si tenes varias
que usas segun el dia. Aca se guardan y se cargan apretando un boton.

El campo de la pantalla SIGUE SIENDO EL QUE MANDA: estos botones solo lo llenan.
El bot lee lo que hay en el campo, igual que siempre, asi que esto no agrega ni
una llamada ni un riesgo al bot corriendo.

SON DOS ARCHIVOS, por la misma regla que las excluidas (ver core/excluidas.py):
un archivo que la app reescribe sola NO puede vivir en el repositorio, porque
choca en cada actualizacion y te deja sin poder actualizar.

  config/watchlists.txt              Las de ESTA PC. Las escribe la app.
  config/watchlists_compartidas.txt  El punto de partida, el unico que va al
                                     repositorio. La app nunca lo escribe.
"""
from __future__ import annotations

import os
import re

_MARCA = "# === WL "
_FIN = " ==="

# Cuantos botones hay en la pantalla. Cambiar este numero alcanza: los botones,
# el cuadro de configuracion y el archivo se acomodan solos.
CUANTAS = 3

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUTA = os.path.join(_RAIZ, "config", "watchlists.txt")


def _compartida(ruta: str | None) -> str:
    raiz, ext = os.path.splitext(ruta or RUTA)
    return f"{raiz}_compartidas{ext or '.txt'}"


def _limpiar(texto: str) -> list[str]:
    """Mismo criterio que la watchlist de la pantalla: comas, espacios, saltos."""
    sin_comentarios = "\n".join(
        l for l in str(texto or "").splitlines() if not l.strip().startswith("#")
    )
    vistos, out = set(), []
    for s in re.split(r"[\s,;]+", sin_comentarios):
        s = s.strip().upper().lstrip("$")
        if s and s not in vistos:
            vistos.add(s)
            out.append(s)
    return out


def _nombre_limpio(nombre: str, i: int) -> str:
    """El nombre va dentro de una linea de comentario: sin saltos ni '='."""
    limpio = " ".join(str(nombre or "").split()).replace("=", "-")
    return limpio or f"WL {i + 1}"


def leer(ruta: str | None = None) -> list[tuple[str, list[str]]]:
    """Devuelve [(nombre, simbolos)], siempre CUANTAS elementos.

    Si esta PC todavia no tiene las suyas, arranca con las compartidas."""
    texto = ""
    for candidata in (ruta or RUTA, _compartida(ruta)):
        try:
            with open(candidata, encoding="utf-8") as f:
                texto = f.read()
            break
        except OSError:
            continue

    listas: list[tuple[str, list[str]]] = []
    nombre, bloque = None, []
    for linea in texto.splitlines():
        if linea.startswith(_MARCA):
            if nombre is not None:
                listas.append((nombre, _limpiar("\n".join(bloque))))
            nombre = linea[len(_MARCA):].removesuffix(_FIN).strip()
            bloque = []
        elif nombre is not None:
            bloque.append(linea)
    if nombre is not None:
        listas.append((nombre, _limpiar("\n".join(bloque))))

    while len(listas) < CUANTAS:
        listas.append((f"WL {len(listas) + 1}", []))
    return listas[:CUANTAS]


def guardar(listas, ruta: str | None = None) -> str:
    """Escribe las listas de ESTA PC. Nunca toca la compartida."""
    ruta = ruta or RUTA
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    partes = [
        "# Watchlists guardadas de esta PC. Las escribe la app (boton de la",
        "# ruedita, al lado de la watchlist), asi que NO va al repositorio.",
        "# La que viaja es watchlists_compartidas.txt, que solo se toca a mano.",
        "",
    ]
    for i, (nombre, simbolos) in enumerate(listas):
        partes.append(f"{_MARCA}{_nombre_limpio(nombre, i)}{_FIN}")
        partes += _limpiar("\n".join(simbolos) if not isinstance(simbolos, str)
                           else simbolos)
        partes.append("")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(partes))
    return ruta
