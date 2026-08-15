"""
Simbolos que el bot NO tiene que operar.

Son DOS listas separadas a proposito, y esa separacion es el punto:

  MIAS       - las que vos decidis excluir, por el motivo que sea (te fue mal,
               la ves rara, tiene resultados esa semana). El broker no las conoce
               ni las va a conocer nunca.
  DEL BROKER - las que el broker tiene bloqueadas para abrir posicion. Cambian
               solas y son cientos (medido el 15/08/2026: 394 en Tastytrade,
               863 en Alpaca).

Si estuvieran juntas, cada vez que quisieras actualizar la lista del broker
tendrias que volver a cargar las tuyas. Separadas, cada una se renueva sin tocar
la otra.

El archivo es de texto y vive en config/excluidas.txt, que SI se sube al repo
(no tiene nada sensible): asi la lista te sigue a las tres PCs sola.
"""
from __future__ import annotations

import os
import re

_SEP_MIAS = "# === MIAS (las excluis vos) ==="
_SEP_BROKER = "# === DEL BROKER (bloqueadas para abrir) ==="

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUTA = os.path.join(_RAIZ, "config", "excluidas.txt")


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


def leer(ruta: str | None = None) -> tuple[list[str], list[str]]:
    """Devuelve (mias, del_broker). Si el archivo no existe, dos listas vacias."""
    ruta = ruta or RUTA
    try:
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        return ([], [])
    if _SEP_BROKER in texto:
        arriba, abajo = texto.split(_SEP_BROKER, 1)
    else:
        arriba, abajo = texto, ""
    return (_limpiar(arriba), _limpiar(abajo))


def guardar(mias, del_broker, ruta: str | None = None) -> str:
    """Escribe las dos listas, cada una en su seccion. Devuelve la ruta."""
    ruta = ruta or RUTA
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    partes = [
        "# Simbolos que el bot NO va a operar.",
        "# Las dos listas se guardan por separado para que puedas renovar la del",
        "# broker sin perder las tuyas. Se edita desde la app (boton 'Excluidas').",
        "",
        _SEP_MIAS,
        *_limpiar("\n".join(mias) if not isinstance(mias, str) else mias),
        "",
        _SEP_BROKER,
        *_limpiar("\n".join(del_broker) if not isinstance(del_broker, str) else del_broker),
        "",
    ]
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(partes))
    return ruta


def todas(ruta: str | None = None) -> set[str]:
    """Las dos listas juntas, que es lo que el bot necesita para saltear."""
    mias, broker = leer(ruta)
    return set(mias) | set(broker)
