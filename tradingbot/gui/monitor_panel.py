"""
Panel de Monitoreo (zona central): Posiciones, Ordenes abiertas, Ejecutadas y
Canceladas, en vivo, con secciones colapsables.

Las tablas de ordenes tienen columna Hora (hh:mm:ss, hora local) y se pueden
ordenar por cualquier columna con un click en el encabezado. Por defecto se
ordenan por hora, con la mas reciente arriba.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.models import OrderStatus
from .widgets import CollapsibleSection


def _fmt_hora(iso: str) -> str:
    """ISO de Tradier (UTC) -> 'hh:mm:ss' en hora local."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return dt.astimezone().strftime("%H:%M:%S")
    except Exception:
        return str(iso)[:8]


class _NumItem(QTableWidgetItem):
    """Celda que ORDENA por valor numerico (no alfabetico)."""

    def __init__(self, value, text=None) -> None:
        super().__init__(text if text is not None else str(value))
        self.setTextAlignment(Qt.AlignCenter)
        try:
            self._v = float(value)
        except (TypeError, ValueError):
            self._v = 0.0

    def __lt__(self, other):
        if isinstance(other, _NumItem):
            return self._v < other._v
        return super().__lt__(other)


class MonitorPanel(QWidget):
    # Tope de filas visibles en Ejecutadas/Canceladas. Con dias de 1500+ ordenes,
    # redibujar TODAS las filas cada 4s ahoga la pantalla (lag / riesgo de cierre).
    # Los conteos de abajo siguen mostrando los totales REALES del dia.
    MAX_FILAS_CERRADAS = 300

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # que el divisor pueda angostar este panel todo lo que el usuario quiera
        self.setMinimumWidth(180)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        titulo = QLabel("Monitoreo")
        titulo.setStyleSheet("font-weight: bold; font-size: 13px;")
        lay.addWidget(titulo)

        self.lbl_pnl = QLabel("P/L del dia: --")
        self.lbl_pnl.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.lbl_pnl.setWordWrap(True)
        lay.addWidget(self.lbl_pnl)
        self.lbl_pnl_detalle = QLabel("")
        self.lbl_pnl_detalle.setWordWrap(True)
        self.lbl_pnl_detalle.setStyleSheet("color: palette(mid);")
        lay.addWidget(self.lbl_pnl_detalle)

        sec_pos = CollapsibleSection("Posiciones")
        self.tbl_pos = self._tabla(["Simbolo", "Lado", "Cant", "Prom"])
        sec_pos.add_widget(self.tbl_pos)
        lay.addWidget(sec_pos, 1)

        sec_ord = CollapsibleSection("Ordenes abiertas")
        self.tbl_ord = self._tabla(["Hora", "Simbolo", "Lado", "Cant", "Tipo", "Limite", "Estado"])
        sec_ord.add_widget(self.tbl_ord)
        lay.addWidget(sec_ord, 1)

        self.lbl_counts = QLabel("Ejecutadas: 0   |   Canceladas: 0   |   ratio C/E: --")
        # Sin wordWrap, esta linea larga exige ~880px de ancho minimo y bloquea el
        # divisor (no se podia angostar el monitoreo). Con wrap, se parte en varias
        # lineas y el panel se puede achicar todo lo que quieras.
        self.lbl_counts.setWordWrap(True)
        lay.addWidget(self.lbl_counts)

        sec_exec = CollapsibleSection("Ejecutadas")
        self.tbl_exec = self._tabla(["Hora", "Simbolo", "Lado", "Cant", "Prom"])
        sec_exec.add_widget(self.tbl_exec)
        lay.addWidget(sec_exec, 1)

        sec_canc = CollapsibleSection("Canceladas")
        self.tbl_canc = self._tabla(["Hora", "Simbolo", "Lado", "Cant", "Limite", "Estado"])
        sec_canc.add_widget(self.tbl_canc)
        lay.addWidget(sec_canc, 1)

        # orden por defecto: por Hora, mas reciente arriba
        for t in (self.tbl_ord, self.tbl_exec, self.tbl_canc):
            t.sortItems(0, Qt.DescendingOrder)

    @staticmethod
    def _tabla(headers: list[str]) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Interactive + ultima columna elastica: el usuario puede ajustar el ancho
        # de cada columna a mano, y arrastrarlas para cambiarlas de lugar.
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        t.horizontalHeader().setStretchLastSection(True)
        t.horizontalHeader().setSectionsMovable(True)
        t.horizontalHeader().setMinimumSectionSize(24)
        # Sin esto, al llenarse de ordenes la tabla exige cada vez mas ancho y el
        # divisor no se puede angostar (le come el espacio al Time & Sales).
        t.setMinimumWidth(0)
        t.setSortingEnabled(True)  # click en el encabezado = ordenar
        return t

    @staticmethod
    def _txt(text: str) -> QTableWidgetItem:
        it = QTableWidgetItem(str(text))
        it.setTextAlignment(Qt.AlignCenter)
        return it

    # ---------- actualizacion (desde el MarketWorker) ----------
    def set_positions(self, positions) -> None:
        t = self.tbl_pos
        t.setSortingEnabled(False)
        t.setRowCount(len(positions))
        for r, p in enumerate(positions):
            lado = "LARGO" if p.quantity > 0 else "CORTO"
            t.setItem(r, 0, self._txt(p.symbol))
            t.setItem(r, 1, self._txt(lado))
            t.setItem(r, 2, _NumItem(abs(p.quantity)))
            t.setItem(r, 3, _NumItem(p.avg_price, f"{p.avg_price:.2f}"))
        t.setSortingEnabled(True)

    def set_day_pnl(self, dia) -> None:
        """Muestra el resultado del DIA: total grande + desglose (realizado/abierto).
        Acepta un DayPnL o, por compatibilidad, un numero suelto (solo abierto)."""
        if isinstance(dia, (int, float)):
            realizado, no_realizado = 0.0, float(dia)
        else:
            realizado, no_realizado = dia.realizado, dia.no_realizado
        total = realizado + no_realizado

        color = "#1e7d34" if total >= 0 else "#b00020"
        signo = "+" if total >= 0 else ""
        self.lbl_pnl.setText(f"P/L del dia: {signo}{total:.2f}")
        self.lbl_pnl.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 14px;"
        )
        sr = "+" if realizado >= 0 else ""
        sn = "+" if no_realizado >= 0 else ""
        self.lbl_pnl_detalle.setText(
            f"cerrado hoy: {sr}{realizado:.2f}   |   abierto: {sn}{no_realizado:.2f}"
        )

    def set_orders(self, orders) -> None:
        t = self.tbl_ord
        t.setSortingEnabled(False)
        t.setRowCount(len(orders))
        for r, o in enumerate(orders):
            t.setItem(r, 0, self._txt(_fmt_hora(o.create_date)))
            t.setItem(r, 1, self._txt(o.symbol))
            t.setItem(r, 2, self._txt(o.side.value))
            t.setItem(r, 3, _NumItem(o.quantity))
            t.setItem(r, 4, self._txt(o.type.value))
            t.setItem(r, 5, _NumItem(o.price, f"{o.price:.2f}"))
            t.setItem(r, 6, self._txt(o.status.value))
        t.setSortingEnabled(True)

    def set_closed_orders(self, closed) -> None:
        ejecutadas = [o for o in closed if o.status == OrderStatus.FILLED]
        canceladas = [o for o in closed
                      if o.status in (OrderStatus.CANCELED, OrderStatus.REJECTED)]
        ne, nc = len(ejecutadas), len(canceladas)  # totales REALES del dia

        # en la tabla solo las mas recientes (ver MAX_FILAS_CERRADAS)
        tope = self.MAX_FILAS_CERRADAS
        if len(ejecutadas) > tope:
            ejecutadas = sorted(ejecutadas, key=lambda o: o.transaction_date)[-tope:]
        if len(canceladas) > tope:
            canceladas = sorted(canceladas, key=lambda o: o.transaction_date)[-tope:]

        te = self.tbl_exec
        te.setSortingEnabled(False)
        te.setRowCount(len(ejecutadas))
        for r, o in enumerate(ejecutadas):
            prom = o.avg_fill_price if o.avg_fill_price else o.price
            cant = o.filled_quantity if o.filled_quantity else o.quantity
            te.setItem(r, 0, self._txt(_fmt_hora(o.transaction_date)))
            te.setItem(r, 1, self._txt(o.symbol))
            te.setItem(r, 2, self._txt(o.side.value))
            te.setItem(r, 3, _NumItem(cant))
            te.setItem(r, 4, _NumItem(prom, f"{prom:.2f}"))
        te.setSortingEnabled(True)

        tc = self.tbl_canc
        tc.setSortingEnabled(False)
        tc.setRowCount(len(canceladas))
        for r, o in enumerate(canceladas):
            tc.setItem(r, 0, self._txt(_fmt_hora(o.transaction_date)))
            tc.setItem(r, 1, self._txt(o.symbol))
            tc.setItem(r, 2, self._txt(o.side.value))
            tc.setItem(r, 3, _NumItem(o.quantity))
            tc.setItem(r, 4, _NumItem(o.price, f"{o.price:.2f}"))
            tc.setItem(r, 5, self._txt(o.status.value))
        tc.setSortingEnabled(True)

        total = ne + nc
        ratio = f"{nc / ne:.2f}" if ne > 0 else "--"
        pct = f"  ({nc / total * 100:.0f}% del total)" if total > 0 else ""
        nota = (f"   [muestro las ultimas {self.MAX_FILAS_CERRADAS}]"
                if total > self.MAX_FILAS_CERRADAS else "")
        self.lbl_counts.setText(
            f"Ejecutadas: {ne}   |   Canceladas: {nc}   |   ratio C/E: {ratio}{pct}{nota}"
        )
