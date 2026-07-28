"""
Lector de watchlist: convierte un texto pegado en una lista de simbolos.

Acepta como separadores: coma, punto y coma, tabulacion, espacio y salto de
linea (cualquier combinacion). Pasa todo a mayusculas, saca el '$' inicial
(ej. '$SPY' -> 'SPY') y elimina duplicados conservando el orden.

(Leer desde archivos Excel/CSV y desde el portapapeles es de la interfaz;
queda para la Fase 5. Ver LISTA_DE_DESEOS.md.)
"""
from __future__ import annotations

import re

_SEPARADORES = re.compile(r"[\s,;]+")


def parse_watchlist(texto: str) -> list[str]:
    simbolos: list[str] = []
    vistos: set[str] = set()
    for crudo in _SEPARADORES.split(texto.strip()):
        s = crudo.strip().upper().lstrip("$")
        if s and s not in vistos:
            vistos.add(s)
            simbolos.append(s)
    return simbolos
