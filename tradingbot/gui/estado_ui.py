"""
Columnas de las tablas: que entren solas, se puedan ajustar, y se RECUERDEN.

Problema que resuelve: si las columnas arrancan en modo "ajustable", Qt les pone
un ancho fijo por defecto y muchas quedan fuera de la vista. Y si ademas no se
guardan, hay que reacomodarlas en cada arranque.

Como funciona:
  1. La tabla arranca en modo "Stretch": las columnas se reparten el ancho
     disponible, asi que TODAS entran (nada queda cortado).
  2. Apenas la ventana termina de dibujarse, se pasa a modo "ajustable"
     CONSERVANDO esos anchos. Desde ahi el usuario los cambia a gusto y puede
     arrastrar las columnas para reordenarlas.
  3. Al cerrar la app se guarda el estado (anchos + orden) y al abrir se restaura.

El estado se guarda por maquina y por usuario (QSettings), no en el repo.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QHeaderView

_AJUSTES = QSettings("BotTrading", "columnas")


def preparar_columnas(tabla, clave: str) -> None:
    """Deja la tabla lista: entra todo, es ajustable, movible y con memoria."""
    cab = tabla.horizontalHeader()
    cab.setSectionResizeMode(QHeaderView.Stretch)   # que entren todas de entrada
    cab.setMinimumSectionSize(16)   # con 7 columnas en un panel angosto, 24 no entraba
    cab.setSectionsMovable(True)                    # arrastrar para reordenar
    tabla.setMinimumWidth(0)
    tabla._clave_columnas = clave

    def _al_terminar_de_dibujar() -> None:
        guardado = _AJUSTES.value(f"{clave}/estado")
        anchos = [cab.sectionSize(i) for i in range(cab.count())]
        cab.setSectionResizeMode(QHeaderView.Interactive)   # ahora si, ajustable
        if guardado is not None:
            try:
                cab.restoreState(guardado)          # anchos y orden de la vez pasada
                return
            except Exception:  # noqa: BLE001
                pass
        for i, ancho in enumerate(anchos):          # sin memoria: los del Stretch
            if ancho > 0:
                cab.resizeSection(i, ancho)

    QTimer.singleShot(0, _al_terminar_de_dibujar)


def guardar_columnas(*tablas) -> None:
    """Guarda anchos y orden de las tablas (llamar al cerrar la app)."""
    for t in tablas:
        clave = getattr(t, "_clave_columnas", None)
        if not clave:
            continue
        try:
            _AJUSTES.setValue(f"{clave}/estado", t.horizontalHeader().saveState())
        except Exception:  # noqa: BLE001
            pass


def olvidar_columnas() -> None:
    """Borra la disposicion guardada (por si quedo rara y se quiere empezar de cero)."""
    _AJUSTES.clear()
