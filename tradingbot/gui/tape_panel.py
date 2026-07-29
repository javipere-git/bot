"""
Time & Sales: la "cinta" de operaciones ejecutadas, en vivo.

Muestra CADA operacion por separado (hora, precio, cantidad, exchange), la mas
reciente arriba. NO agrupa prints: si salen 10 operaciones de 10 acciones, se ven
las 10 -esa es justamente la informacion que se lee en la cinta-.

Color segun quien fue el agresivo:
  - VERDE: la operacion se dio en el ask o mas arriba -> compro el agresivo.
  - ROJO : se dio en el bid o mas abajo -> vendio el agresivo.
  - gris : quedo dentro del spread (no se sabe).

Rendimiento: una accion movida hace decenas de operaciones por segundo. Por eso
las operaciones se acumulan y se vuelcan a la tabla en lotes (cada 150 ms), y la
tabla guarda como maximo MAX_FILAS (las mas viejas se descartan). El detalle de
cada print se respeta: lo unico que se limita es cuanto historial queda a la vista.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

C_HORA, C_PRECIO, C_CANT, C_EXCH = range(4)
VERDE = QColor("#1e7d34")
ROJO = QColor("#b00020")
GRIS = QColor("#666666")

# Codigos de exchange (una letra) -> nombre, para el cartelito de ayuda.
# Ojo: el codigo depende del feed. En el feed de Blue Ocean (overnight) la "B"
# es Blue Ocean; en el consolidado (SIP) la "B" es Nasdaq BX.
EXCHANGES = {
    "A": "NYSE American", "B": "Nasdaq BX / Blue Ocean", "C": "NYSE National",
    "D": "FINRA ADF", "H": "MIAX", "I": "ISE", "J": "Cboe EDGA", "K": "Cboe EDGX",
    "L": "LTSE", "M": "NYSE Chicago", "N": "NYSE", "P": "NYSE Arca", "Q": "Nasdaq",
    "S": "Consolidada", "T": "Nasdaq TRF", "U": "MEMX", "V": "IEX", "W": "CBSX",
    "X": "Nasdaq PSX", "Y": "Cboe BYX", "Z": "Cboe BZX",
}


class TapePanel(QWidget):
    MAX_FILAS = 500      # cuantas operaciones quedan a la vista
    INTERVALO_MS = 150   # cada cuanto se vuelcan a la tabla (en lote)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._symbol = ""
        self._nbbo = None            # (bid, ask) para saber quien fue el agresivo
        self._pendientes = deque()   # operaciones sin volcar todavia

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        titulo = QLabel("Time & Sales")
        titulo.setStyleSheet("font-weight: bold; font-size: 13px;")
        lay.addWidget(titulo)

        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["Hora", "Precio", "Cant", "Exch"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.setStyleSheet("font-size: 11px;")
        self.tabla.verticalHeader().setDefaultSectionSize(18)
        lay.addWidget(self.tabla, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(self.INTERVALO_MS)
        self._timer.timeout.connect(self._volcar)
        self._timer.start()

    # ---------- entradas ----------
    def set_symbol(self, sym: str) -> None:
        """Cambia el simbolo que se sigue y limpia la cinta."""
        self._symbol = (sym or "").strip().upper()
        self._pendientes.clear()
        self._nbbo = None
        self.tabla.setRowCount(0)

    def actualizar_quote(self, symbol, bid, ask, bidsize=0, asksize=0) -> None:
        """El NBBO del momento, para saber si cada operacion fue compra o venta."""
        if symbol == self._symbol and bid > 0 and ask > 0:
            self._nbbo = (bid, ask)

    def agregar_trade(self, symbol, precio, cantidad, exch, epoch) -> None:
        """Una operacion ejecutada. Se guarda y se vuelca en el proximo lote."""
        if symbol != self._symbol or precio <= 0:
            return
        color = GRIS
        if self._nbbo:
            bid, ask = self._nbbo
            if precio >= ask:
                color = VERDE
            elif precio <= bid:
                color = ROJO
        self._pendientes.append((epoch, precio, cantidad, exch, color))

    # ---------- volcado en lote ----------
    def _volcar(self) -> None:
        if not self._pendientes:
            return
        lote = list(self._pendientes)
        self._pendientes.clear()
        # Cada una se inserta en la fila 0, empujando las anteriores hacia abajo.
        # Se recorre en el ORDEN QUE LLEGARON: asi la ultima insertada -la mas
        # nueva- termina arriba de todo.
        for epoch, precio, cant, exch, color in lote:
            self.tabla.insertRow(0)
            self._set(0, C_HORA, self._hora(epoch), color)
            self._set(0, C_PRECIO, f"{precio:.2f}", color)
            self._set(0, C_CANT, f"{int(cant)}", color)
            it = self._set(0, C_EXCH, str(exch), color)
            if exch in EXCHANGES:
                it.setToolTip(EXCHANGES[exch])
        # recortar las mas viejas (que ya scrolleaste) para no crecer sin fin
        while self.tabla.rowCount() > self.MAX_FILAS:
            self.tabla.removeRow(self.tabla.rowCount() - 1)

    def _set(self, row, col, texto, color) -> QTableWidgetItem:
        it = QTableWidgetItem(texto)
        it.setTextAlignment(Qt.AlignCenter)
        it.setForeground(QBrush(color))
        self.tabla.setItem(row, col, it)
        return it

    @staticmethod
    def _hora(epoch) -> str:
        try:
            return datetime.fromtimestamp(float(epoch)).strftime("%H:%M:%S")
        except Exception:  # noqa: BLE001
            return ""
