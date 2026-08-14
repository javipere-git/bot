"""
Modo claro / modo oscuro, y memoria de la eleccion.

Se cambia la PALETA de la aplicacion (no hojas de estilo), asi todos los paneles
se adaptan solos. La eleccion se guarda y se restaura al abrir.

OJO, leccion aprendida: poner una hoja de estilo en un widget (aunque sea solo
"font-size: 11px") hace que Qt DESCARTE la paleta para ese widget y use sus colores
por defecto -> titulos en negro y tablas en blanco aunque el tema sea oscuro. Por eso
en el resto de la app el tamano/negrita de las letras se cambia con QFont, NO con
setStyleSheet. Si hace falta una hoja de estilo si o si, hay que escribirle el color
con palette(...) explicitamente.

Aca tambien viven los colores del ladder y de la cinta, que dependen del tema:
en claro son pasteles con letra oscura; en oscuro, tonos saturados con letra clara
(estilo ThinkorSwim).
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

_AJUSTES = QSettings("BotTrading", "tema")
_PALETA_CLARA: QPalette | None = None


def _paleta_oscura() -> QPalette:
    p = QPalette()
    # Gris medio (no negro): con el fondo demasiado oscuro los campos para rellenar
    # se confundian con el fondo. Ahora el fondo es mas claro que las cajas de texto,
    # asi cada campo se ve hundido y se distingue.
    fondo = QColor(60, 63, 65)
    texto = QColor(228, 228, 228)
    campos = QColor(43, 43, 45)        # tablas y cajas de texto: mas oscuras que el fondo
    p.setColor(QPalette.Window, fondo)
    p.setColor(QPalette.WindowText, texto)
    p.setColor(QPalette.Base, campos)
    p.setColor(QPalette.AlternateBase, QColor(52, 54, 56))
    p.setColor(QPalette.Text, texto)
    p.setColor(QPalette.Button, QColor(76, 80, 82))
    p.setColor(QPalette.ButtonText, texto)
    p.setColor(QPalette.ToolTipBase, QColor(52, 54, 56))
    p.setColor(QPalette.ToolTipText, texto)
    p.setColor(QPalette.PlaceholderText, QColor(150, 150, 150))
    p.setColor(QPalette.Highlight, QColor(52, 101, 148))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    # bordes y lineas divisorias: con estos tonos se ven las separaciones de las tablas
    p.setColor(QPalette.Mid, QColor(120, 124, 128))        # textos de ayuda
    p.setColor(QPalette.Midlight, QColor(96, 100, 104))
    p.setColor(QPalette.Dark, QColor(32, 33, 35))
    p.setColor(QPalette.Light, QColor(96, 100, 104))
    p.setColor(QPalette.Shadow, QColor(20, 20, 22))
    for grupo in (QPalette.Disabled,):
        p.setColor(grupo, QPalette.Text, QColor(130, 130, 130))
        p.setColor(grupo, QPalette.ButtonText, QColor(130, 130, 130))
        p.setColor(grupo, QPalette.WindowText, QColor(130, 130, 130))
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


# --------------------------------------------------------------------------
# Colores que dependen del tema (ladder y cinta)
# --------------------------------------------------------------------------
_CLAROS = {
    "verde": QColor("#8fd69a"),      # BEST bid (resaltado)
    "rojo": QColor("#f0a0a4"),       # BEST ask (resaltado)
    "verde_col": QColor("#eaf6ea"),  # resto de la columna de compra (sombreado suave)
    "rojo_col": QColor("#fbeceb"),   # resto de la columna de venta
    "fondo_ladder": QColor("#ffffff"),
    "azul": QColor("#cfe0f5"),       # mis ordenes (en desuso: ahora van por lado)
    # Mis ordenes en el ladder, POR ESTADO. La regla que no se negocia: lo que el
    # broker todavia no confirmo NUNCA se ve igual que lo confirmado.
    "orden_buy": QColor("#2e8b57"),        # confirmada, compra
    "orden_sell": QColor("#c0392b"),       # confirmada, venta / venta en corto
    "orden_pendiente": QColor("#9aa0a6"),  # enviada, sin confirmar todavia
    "orden_moviendo": QColor("#e8820c"),   # arrastrada, esperando confirmacion
    "orden_rechazada": QColor("#ff1744"),  # el broker la rechazo (destello)
    "orden_texto": QColor("#ffffff"),      # sobre esos tonos saturados, letra blanca
    "amarillo": QColor("#ffe08a"),   # precio promedio
    "texto": QColor("#111111"),      # sobre esos pasteles, letra oscura
    "texto_best": QColor("#111111"),
    # el mismo tono que usaba Fusion por su cuenta: el modo claro ya se veia bien
    "borde": QColor("#c7c7c7"),      # lineas divisorias (modo claro)
    "borde_suave": QColor("#c7c7c7"),
    "tape_verde": QColor("#1e7d34"),
    "tape_rojo": QColor("#b00020"),
    "tape_gris": QColor("#666666"),
    "boton_compra": QColor("#1e7d34"),
    "boton_compra_hover": QColor("#25994080"[:7]),
    "boton_venta": QColor("#b00020"),
    "boton_venta_hover": QColor("#d0142c"),
    "boton_texto": QColor("#ffffff"),
}

_OSCUROS = {
    "verde": QColor("#25c65c"),      # BEST bid: verde chillon (estilo ThinkorSwim)
    "rojo": QColor("#e03e4e"),       # BEST ask: rojo chillon
    "verde_col": QColor("#183a26"),  # resto de la columna: sombreado tenue
    "rojo_col": QColor("#3a1d22"),
    "fondo_ladder": QColor("#33363a"),   # menos negro que el resto de la app
    "azul": QColor("#2b5f96"),       # (en desuso: ahora las ordenes van por lado)
    "orden_buy": QColor("#1f8a45"),        # confirmada, compra
    "orden_sell": QColor("#b52b39"),       # confirmada, venta / venta en corto
    "orden_pendiente": QColor("#5f666e"),  # enviada, sin confirmar todavia
    "orden_moviendo": QColor("#c8760f"),   # arrastrada, esperando confirmacion
    "orden_rechazada": QColor("#ff2d4a"),  # el broker la rechazo (destello)
    "orden_texto": QColor("#ffffff"),
    "amarillo": QColor("#8a6b1e"),
    "texto": QColor("#f2f2f2"),      # sobre esos tonos, letra clara
    "texto_best": QColor("#0e1a12"),  # sobre el verde/rojo chillon, letra oscura
    "borde": QColor("#848b93"),      # lineas divisorias de las tablas de ordenes
    # El ladder y la cinta tienen el fondo mas claro y ademas celdas de color: ahi el
    # mismo gris se ve casi blanco. Con este tono se distingue sin ser chocante.
    "borde_suave": QColor("#666d75"),
    "tape_verde": QColor("#4cd07a"),
    "tape_rojo": QColor("#ff6b7a"),
    "tape_gris": QColor("#a0a0a0"),
    "boton_compra": QColor("#1f8a45"),
    "boton_compra_hover": QColor("#28a353"),
    "boton_venta": QColor("#b52b39"),
    "boton_venta_hover": QColor("#d13443"),
    "boton_texto": QColor("#ffffff"),
}


def colores(clave: str) -> QColor:
    """El color que corresponde al tema activo (ver _CLAROS / _OSCUROS)."""
    tabla = _OSCUROS if es_oscuro() else _CLAROS
    return tabla.get(clave, _CLAROS.get(clave, QColor("#000000")))
