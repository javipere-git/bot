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

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QPalette, QPen
from PySide6.QtWidgets import QHeaderView, QStyledItemDelegate

_AJUSTES = QSettings("BotTrading", "columnas")


def preparar_columnas(tabla, clave: str) -> None:
    """Deja la tabla lista: entra todo, es ajustable, movible y con memoria."""
    cab = tabla.horizontalHeader()
    cab.setSectionResizeMode(QHeaderView.Stretch)   # que entren todas de entrada
    cab.setMinimumSectionSize(16)   # con 7 columnas en un panel angosto, 24 no entraba
    cab.setSectionsMovable(True)                    # arrastrar para reordenar
    tabla.setShowGrid(True)
    tabla.setGridStyle(Qt.SolidLine)
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


def guardar_splitter(splitter, clave: str = "principal") -> None:
    """Guarda el ancho que le diste a cada seccion (bot / monitor / ladder / TAS)."""
    try:
        _AJUSTES.setValue(f"splitter/{clave}", splitter.saveState())
    except Exception:  # noqa: BLE001
        pass


def restaurar_splitter(splitter, clave: str = "principal") -> bool:
    """Devuelve los anchos de secciones de la vez pasada. True si habia guardados."""
    estado = _AJUSTES.value(f"splitter/{clave}")
    if estado is None:
        return False
    try:
        return bool(splitter.restoreState(estado))
    except Exception:  # noqa: BLE001
        return False


def olvidar_columnas() -> None:
    """Borra la disposicion guardada (por si quedo rara y se quiere empezar de cero)."""
    _AJUSTES.clear()


CANTIDADES_POR_DEFECTO = [10, 25, 50, 100]


def cantidades_botones() -> list:
    """Las cantidades de los 4 botones del ladder, como las dejaste la vez pasada."""
    guardado = _AJUSTES.value("ladder/cantidades")
    if not guardado:
        return list(CANTIDADES_POR_DEFECTO)
    try:
        vals = [int(v) for v in guardado]
    except (TypeError, ValueError):
        return list(CANTIDADES_POR_DEFECTO)
    vals = [v for v in vals if v > 0][:4]
    # si quedaron menos de 4 (archivo viejo o corrupto), se completa con las de fabrica
    while len(vals) < 4:
        vals.append(CANTIDADES_POR_DEFECTO[len(vals)])
    return vals


def guardar_cantidades_botones(valores) -> None:
    """Guarda las cantidades de los 4 botones del ladder."""
    limpias = [int(v) for v in valores if int(v) > 0][:4]
    if limpias:
        _AJUSTES.setValue("ladder/cantidades", [str(v) for v in limpias])


def poner_titulo(label, tamano_px: int = 13) -> None:
    """Deja una etiqueta en negrita y del tamano pedido SIN hoja de estilo.

    Importante para el modo oscuro: si se usa setStyleSheet, Qt descarta la paleta
    para ese widget y el texto sale NEGRO (ilegible sobre fondo oscuro).

    El tamano va en PIXELES, igual que las hojas de estilo que habia antes
    ("font-size: 13px"). Usar puntos agranda todo (13pt son ~17px).
    """
    f = label.font()
    f.setBold(True)
    f.setPixelSize(tamano_px)
    label.setFont(f)


def poner_fuente(widget, tamano_px: int) -> None:
    """Cambia el tamano de letra de un widget SIN hoja de estilo (ver poner_titulo).
    Con setStyleSheet, una tabla queda con fondo BLANCO aunque el tema sea oscuro."""
    f = widget.font()
    f.setPixelSize(tamano_px)
    widget.setFont(f)


class _LineasDelegate(QStyledItemDelegate):
    """Dibuja los bordes de cada celda con un color propio.

    Hace falta porque el estilo Fusion IGNORA la paleta para la grilla: calcula su
    propio color a partir del fondo (medido: sobre el fondo oscuro #33363a usaba
    #323436, practicamente invisible). Con esto elegimos el color de verdad.

    Solo AGREGA las lineas: primero deja que se dibuje la celda normal (con su color
    de fondo y su texto, que en el ladder es lo que da el sombreado de las columnas)
    y despues pinta el borde encima.
    """

    def __init__(self, color, parent=None) -> None:
        super().__init__(parent)
        self._pluma = QPen(color, 1)

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)    # la celda de siempre, intacta
        painter.save()
        painter.setPen(self._pluma)
        r = option.rect
        painter.drawLine(r.bottomLeft(), r.bottomRight())   # separacion de filas
        painter.drawLine(r.topRight(), r.bottomRight())     # separacion de columnas
        painter.restore()


def estilo_tabla(tabla, fondo_propio=None) -> None:
    """Fondo propio y lineas divisorias visibles, SIN hojas de estilo.

    Por que sin hojas de estilo (se probo y salio mal): al estilar QTableView::item,
    Qt IGNORA el color que cada celda se puso a si misma -> se perdia el sombreado de
    las columnas del ladder. Y ademas las barras de desplazamiento pasaban a dibujarse
    con el estilo por defecto (blancas) y el texto se veia como en negrita.

    El fondo va por la PALETA del widget. Las lineas, por un dibujante propio: el
    estilo Fusion ignora la paleta para la grilla y usa un color casi igual al fondo.
    """
    from .tema import colores          # import tardio (evita ciclo)

    if fondo_propio is not None:
        pal = QPalette(tabla.palette())
        pal.setColor(QPalette.Base, fondo_propio)
        pal.setColor(QPalette.AlternateBase, fondo_propio)
        tabla.setPalette(pal)
    # la grilla nativa se apaga: la dibuja el delegado, con el color que elegimos
    tabla.setShowGrid(False)
    delegado = _LineasDelegate(colores("borde"), tabla)
    tabla.setItemDelegate(delegado)
    tabla._delegado_lineas = delegado      # guardar la referencia (si no, se descarta)
