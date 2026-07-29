"""
Modo claro / modo oscuro, y memoria de la eleccion.

Se cambia la PALETA de la aplicacion (no hojas de estilo), asi todos los paneles
se adaptan solos. La eleccion se guarda y se restaura al abrir.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

_AJUSTES = QSettings("BotTrading", "tema")
_PALETA_CLARA: QPalette | None = None


def _paleta_oscura() -> QPalette:
    p = QPalette()
    fondo = QColor(45, 45, 48)
    texto = QColor(222, 222, 222)
    p.setColor(QPalette.Window, fondo)
    p.setColor(QPalette.WindowText, texto)
    p.setColor(QPalette.Base, QColor(30, 30, 32))          # fondo de tablas/campos
    p.setColor(QPalette.AlternateBase, fondo)
    p.setColor(QPalette.Text, texto)
    p.setColor(QPalette.Button, QColor(62, 62, 66))
    p.setColor(QPalette.ButtonText, texto)
    p.setColor(QPalette.ToolTipBase, fondo)
    p.setColor(QPalette.ToolTipText, texto)
    p.setColor(QPalette.PlaceholderText, QColor(140, 140, 140))
    p.setColor(QPalette.Highlight, QColor(38, 79, 120))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.Mid, QColor(150, 150, 150))        # textos de ayuda
    for grupo in (QPalette.Disabled,):
        p.setColor(grupo, QPalette.Text, QColor(120, 120, 120))
        p.setColor(grupo, QPalette.ButtonText, QColor(120, 120, 120))
        p.setColor(grupo, QPalette.WindowText, QColor(120, 120, 120))
    return p


def aplicar_tema(oscuro: bool) -> None:
    """Cambia el tema de toda la app y recuerda la eleccion."""
    global _PALETA_CLARA
    app = QApplication.instance()
    if app is None:
        return
    if _PALETA_CLARA is None:                 # guardar el claro la primera vez
        _PALETA_CLARA = QPalette(app.palette())
    app.setPalette(_paleta_oscura() if oscuro else _PALETA_CLARA)
    _AJUSTES.setValue("oscuro", bool(oscuro))


def es_oscuro() -> bool:
    """Que tema eligio el usuario la ultima vez (por defecto, claro)."""
    v = _AJUSTES.value("oscuro", False)
    return str(v).lower() in ("true", "1", "yes")
