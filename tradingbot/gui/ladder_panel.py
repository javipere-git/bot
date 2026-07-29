"""
Panel del Ladder (zona derecha) - DOM Level 1.

Funciones:
  - Escalera de precios (Compra | Bid | Precio | Ask | Venta), centrada en el
    bid/ask, con tamanos. Filas compactas.
  - Zoom: el paso de la escalera cambia (0.01 / 0.02 / 0.05 / 0.10 / 0.25) para
    abarcar mas rango en spreads amplios (estilo ThinkorSwim).
  - Botonera de sizes + botones marketables (Comprar al ask / Vender al bid).
  - Click-para-operar: click en Compra/Venta (celda vacia) manda orden limite.
  - Mis ordenes dibujadas en su nivel (col Compra/Venta); click sobre ellas las
    CANCELA.
  - Marca del precio promedio de la posicion (fila resaltada en la col Precio).

Pendiente (ver PENDIENTES.md): arrastrar una orden a otro nivel para modificar
su precio.

Opera contra el broker manual (sandbox) que le pasa la ventana.
"""
from __future__ import annotations

import time
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.models import OrderRequest, OrderType, Side

C_BUY, C_BID, C_PRICE, C_ASK, C_SELL = range(5)
VERDE = QColor("#cdeccd")
ROJO = QColor("#f2cccc")
AZUL = QColor("#cfe0f5")     # mis ordenes
AMARILLO = QColor("#ffe08a")  # marca del precio promedio
_BUY_SIDES = (Side.BUY, Side.BUY_TO_COVER)


class LadderTable(QTableWidget):
    """Tabla del ladder con arrastre de ordenes: si se arrastra una celda con una
    orden (col Compra/Venta) hacia otra fila, emite orderMoved(ids, fila_destino).
    Un click simple (sin arrastrar) sigue funcionando igual (cancelar / poner orden)."""

    orderMoved = Signal(object, int)   # (lista de ids, fila_destino)
    DRAG_THRESHOLD = 6

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._press_pos = None
        self._drag_ids = None
        self._dragging = False

    def _pt(self, e):
        try:
            return e.position().toPoint()
        except Exception:
            return e.pos()

    def mousePressEvent(self, e) -> None:
        self._press_pos = self._pt(e)
        self._drag_ids = None
        self._dragging = False
        if e.button() == Qt.LeftButton:
            idx = self.indexAt(self._press_pos)
            if idx.isValid() and idx.column() in (C_BUY, C_SELL):
                it = self.item(idx.row(), idx.column())
                ids = it.data(Qt.UserRole) if it is not None else None
                if ids:
                    self._drag_ids = ids
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        if self._drag_ids and (e.buttons() & Qt.LeftButton):
            p = self._pt(e)
            if (not self._dragging
                    and (p - self._press_pos).manhattanLength() >= self.DRAG_THRESHOLD):
                self._dragging = True
                self.setCursor(Qt.ClosedHandCursor)
            if self._dragging:
                e.accept()
                return  # sin super(): evita seleccion mientras arrastra
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if self._dragging and self._drag_ids is not None:
            idx = self.indexAt(self._pt(e))
            ids = self._drag_ids
            self.unsetCursor()
            self._dragging = False
            self._drag_ids = None
            if idx.isValid():
                self.orderMoved.emit(ids, idx.row())
            e.accept()
            return  # suprime el click -> no cancela
        self._dragging = False
        self._drag_ids = None
        super().mouseReleaseEvent(e)


class LadderPanel(QWidget):
    MARGEN_NIVELES = 14
    MAX_FILAS = 600
    STEPS = [0.01, 0.02, 0.05, 0.10, 0.25]
    AYUDA = "Click en Compra/Venta = orden; click en tu orden = cancelar."
    STALE_SECS = 8    # segundos sin quote nuevo -> aviso "datos viejos"

    def __init__(
        self,
        broker_provider: Callable[[], object] | None = None,
        on_symbol: Callable[[str], None] | None = None,
        log: Callable[[str], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._broker_provider = broker_provider
        self._on_symbol = on_symbol
        self._log = log or (lambda m: None)
        self._symbol = ""
        self._last = None       # (bid, ask, bidsize, asksize)
        self._step_idx = 0      # indice en STEPS
        self._orders = []       # ordenes abiertas del simbolo activo
        self._avg = None        # precio promedio de la posicion del simbolo activo
        self._last_nbbo = None  # (bid_lvl, ask_lvl, paso) del ultimo centrado
        self._pendiente = False # hay datos nuevos por repintar (repintado throttleado)
        self._ancla = None      # (top_lvl, bot_lvl, paso) fijado mientras esta congelada

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        titulo = QLabel("Ladder")
        titulo.setStyleSheet("font-weight: bold; font-size: 13px;")
        lay.addWidget(titulo)

        # --- simbolo ---
        fila_sym = QHBoxLayout()
        fila_sym.addWidget(QLabel("Simbolo:"))
        self.ed_symbol = QLineEdit()
        self.ed_symbol.setPlaceholderText("ej. SPY")
        self.ed_symbol.returnPressed.connect(self._cambiar_symbol)
        fila_sym.addWidget(self.ed_symbol)
        self.btn_set = QPushButton("Ver")
        self.btn_set.setMaximumWidth(50)
        self.btn_set.clicked.connect(self._cambiar_symbol)
        fila_sym.addWidget(self.btn_set)
        lay.addLayout(fila_sym)

        # --- NBBO grande (bid / ask bien visibles) ---
        fila_nbbo = QHBoxLayout()
        self.lbl_bid = QLabel("BID --")
        self.lbl_bid.setAlignment(Qt.AlignCenter)
        self.lbl_bid.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e7d34;")
        self.lbl_ask = QLabel("ASK --")
        self.lbl_ask.setAlignment(Qt.AlignCenter)
        self.lbl_ask.setStyleSheet("font-size: 18px; font-weight: bold; color: #b00020;")
        fila_nbbo.addWidget(self.lbl_bid)
        fila_nbbo.addWidget(self.lbl_ask)
        lay.addLayout(fila_nbbo)

        # --- cantidad (size) ---
        fila_size = QHBoxLayout()
        fila_size.addWidget(QLabel("Cant:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 1_000_000)
        self.spin_size.setValue(10)
        self.spin_size.setMaximumWidth(80)
        fila_size.addWidget(self.spin_size)
        for s in (10, 25, 50, 100):
            b = QPushButton(str(s))
            b.setMaximumWidth(38)
            b.clicked.connect(lambda _=False, v=s: self.spin_size.setValue(v))
            fila_size.addWidget(b)
        fila_size.addStretch()
        lay.addLayout(fila_size)

        # --- zoom (paso de la escalera) ---
        fila_zoom = QHBoxLayout()
        fila_zoom.addWidget(QLabel("Zoom:"))
        btn_out = QPushButton("-")
        btn_out.setMaximumWidth(30)
        btn_out.setToolTip("Alejar: mas rango, paso mas grande")
        btn_out.clicked.connect(self._zoom_out)
        self.lbl_step = QLabel()
        self.lbl_step.setMinimumWidth(48)
        self.lbl_step.setAlignment(Qt.AlignCenter)
        btn_in = QPushButton("+")
        btn_in.setMaximumWidth(30)
        btn_in.setToolTip("Acercar: menos rango, paso mas fino")
        btn_in.clicked.connect(self._zoom_in)
        fila_zoom.addWidget(btn_out)
        fila_zoom.addWidget(self.lbl_step)
        fila_zoom.addWidget(btn_in)
        self.btn_center = QPushButton("Centrar")
        self.btn_center.setToolTip("Volver a centrar la escalera en el bid/ask")
        self.btn_center.clicked.connect(self._centrar)
        fila_zoom.addWidget(self.btn_center)
        fila_zoom.addStretch()
        self.chk_ext = QCheckBox("Ext. hours")
        self.chk_ext.setToolTip(
            "TILDADO: la orden PUEDE ejecutarse fuera de la rueda regular\n"
            "(pre-market, post-market y overnight).\n"
            "DESTILDADO: si el mercado esta cerrado, la orden queda en cola y se\n"
            "ejecuta recien en la proxima apertura."
        )
        fila_zoom.addWidget(self.chk_ext)
        self.btn_cancel_all = QPushButton("Cancelar todo")
        self.btn_cancel_all.setToolTip("Cancela TODAS las ordenes abiertas de la cuenta")
        self.btn_cancel_all.clicked.connect(self._cancelar_todas)
        fila_zoom.addWidget(self.btn_cancel_all)
        lay.addLayout(fila_zoom)

        # --- botones marketables ---
        fila_mkt = QHBoxLayout()
        self.btn_buy_ask = QPushButton("Comprar al ask")
        self.btn_buy_ask.clicked.connect(self._comprar_al_ask)
        self.btn_sell_bid = QPushButton("Vender al bid")
        self.btn_sell_bid.clicked.connect(self._vender_al_bid)
        fila_mkt.addWidget(self.btn_buy_ask)
        fila_mkt.addWidget(self.btn_sell_bid)
        lay.addLayout(fila_mkt)

        # --- la escalera (filas compactas) ---
        self.tabla = LadderTable(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Compra", "Bid", "Precio", "Ask", "Venta"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(18)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionMode(QAbstractItemView.NoSelection)
        self.tabla.setStyleSheet("font-size: 11px;")
        cab = self.tabla.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.Interactive)   # ancho ajustable a mano
        cab.setStretchLastSection(True)
        cab.setSectionsMovable(True)                        # columnas arrastrables
        self.tabla.cellClicked.connect(self._click_celda)
        self.tabla.orderMoved.connect(self._mover_orden)
        lay.addWidget(self.tabla, 1)

        self._ayuda = QLabel(self.AYUDA)
        self._ayuda.setStyleSheet("color: palette(mid);")
        self._ayuda.setWordWrap(True)
        lay.addWidget(self._ayuda)

        self._actualizar_label_step()

        # Repintado THROTTLEADO: aunque lleguen decenas de quotes por segundo, la
        # escalera se redibuja a lo sumo cada 150 ms (junta todo lo pendiente). Asi
        # el hilo de la pantalla queda libre para responder clicks y ordenes al instante.
        self._repintar_timer = QTimer(self)
        self._repintar_timer.setInterval(150)
        self._repintar_timer.timeout.connect(self._repintar)
        self._repintar_timer.start()

    # ---------- simbolo ----------
    def _cambiar_symbol(self) -> None:
        sym = self.ed_symbol.text().strip().upper().lstrip("$")
        if not sym:
            return
        self._symbol = sym
        self.ed_symbol.setText(sym)
        self._orders = []
        self._avg = None
        self._last = None
        self._last_nbbo = None
        self._ancla = None
        self.tabla.setRowCount(0)
        self.lbl_bid.setText("BID --")
        self.lbl_ask.setText("ASK --")
        self.btn_buy_ask.setText("Comprar al ask")
        self.btn_sell_bid.setText("Vender al bid")
        if self._on_symbol:
            self._on_symbol(sym)
        self._log(f"Ladder: mostrando {sym}")

    def symbol(self) -> str:
        return self._symbol

    def cargar_symbol(self, sym: str) -> None:
        """Carga un simbolo desde afuera (ej. el bot pasa a manual y lo trae aca).
        Si ya es el simbolo activo no hace nada, para no perder lo que estas viendo."""
        sym = (sym or "").strip().upper().lstrip("$")
        if not sym or sym == self._symbol:
            return
        self.ed_symbol.setText(sym)
        self._cambiar_symbol()

    # ---------- zoom ----------
    def _zoom_out(self) -> None:
        if self._step_idx < len(self.STEPS) - 1:
            self._step_idx += 1
            self._actualizar_label_step()
            self._repoblar()

    def _zoom_in(self) -> None:
        if self._step_idx > 0:
            self._step_idx -= 1
            self._actualizar_label_step()
            self._repoblar()

    def _actualizar_label_step(self) -> None:
        self.lbl_step.setText(f"{self.STEPS[self._step_idx]:.2f}")

    # ---------- datos en vivo ----------
    def actualizar_quote(self, symbol, bid, ask, bidsize, asksize) -> None:
        if symbol != self._symbol:
            return
        if bid <= 0 or ask <= 0 or ask < bid:
            return
        self._last = (bid, ask, bidsize, asksize)
        self._pendiente = True  # se repinta en el proximo tick del timer (throttleado)

    def _repintar(self) -> None:
        """Repinta la escalera si hay datos nuevos. Lo llama el timer cada 150 ms."""
        if not self._pendiente:
            return
        self._pendiente = False
        if self._last:
            bid, ask, _bsz, _asz = self._last
            self.lbl_bid.setText(f"BID {bid:.2f}")
            self.lbl_ask.setText(f"ASK {ask:.2f}")
            self.btn_buy_ask.setText(f"Comprar al ask {ask:.2f}")
            self.btn_sell_bid.setText(f"Vender al bid {bid:.2f}")
        self._repoblar()

    def set_orders(self, orders) -> None:
        self._orders = [o for o in orders if o.symbol == self._symbol and o.is_active]
        self._pendiente = True

    def set_positions(self, positions) -> None:
        self._avg = next((p.avg_price for p in positions if p.symbol == self._symbol), None)
        self._pendiente = True

    # ---------- congelado con el mouse encima ----------
    def _mouse_sobre_escalera(self) -> bool:
        """True si el cursor esta sobre la escalera. Mientras lo este, los precios
        NO se mueven de fila (ver _repoblar). Se calcula por geometria, sin guardar
        estado, para que sea IMPOSIBLE que quede congelada por error."""
        try:
            vp = self.tabla.viewport()
            if not vp.isVisible():
                return False
            return vp.rect().contains(vp.mapFromGlobal(QCursor.pos()))
        except Exception:  # noqa: BLE001
            return False

    # ---------- dibujo de la escalera ----------
    def _repoblar(self) -> None:
        if not self._last:
            return
        bid, ask, bidsize, asksize = self._last
        step_c = round(self.STEPS[self._step_idx] * 100)
        bid_lvl = round(round(bid * 100) / step_c)
        ask_lvl = round(round(ask * 100) / step_c)
        nbbo = (bid_lvl, ask_lvl, step_c)

        # CONGELADO: con el mouse sobre la escalera, los precios quedan CLAVADOS en
        # su fila (se reusa el rango anterior). Sin esto, si el precio se mueve justo
        # cuando vas a hacer click, la fila cambia de precio abajo del cursor y la
        # orden sale a otro precio. Lo demas (tamanos, NBBO, tus ordenes) se sigue
        # actualizando: lo unico que se fija es QUE precio esta en QUE fila.
        congelada = self._mouse_sobre_escalera() and self._ancla is not None
        if congelada and self._ancla[2] == step_c:
            top_lvl, bot_lvl, _ = self._ancla
            recentrar = False           # tampoco se mueve el scroll
        else:
            # Re-centrar SOLO si cambio el primer nivel (bid o ask) o el paso del zoom.
            # Si el NBBO no cambio, las filas quedan identicas y el scroll del usuario
            # se respeta (puede explorar precios sin que se lo arranquen).
            recentrar = nbbo != self._last_nbbo
            self._last_nbbo = nbbo
            top_lvl = ask_lvl + self.MARGEN_NIVELES
            bot_lvl = bid_lvl - self.MARGEN_NIVELES
            self._ancla = (top_lvl, bot_lvl, step_c)
        filas = top_lvl - bot_lvl + 1
        if filas <= 0 or filas > self.MAX_FILAS:
            self.tabla.setRowCount(0)
            self._ayuda.setText("Spread muy grande: aleja con el zoom (-).")
            return

        # mapas nivel -> (ids, qty) de mis ordenes
        buy_lvl, sell_lvl = {}, {}
        for o in self._orders:
            if not o.price:
                continue
            lvl = round(round(o.price * 100) / step_c)
            destino = buy_lvl if o.side in _BUY_SIDES else sell_lvl
            ids, qty = destino.get(lvl, ([], 0))
            ids.append(o.id)
            destino[lvl] = (ids, qty + o.quantity)

        avg_lvl = round(round(self._avg * 100) / step_c) if self._avg else None

        self.tabla.setRowCount(filas)
        centro = None
        for i in range(filas):
            lvl = top_lvl - i
            precio = lvl * step_c / 100
            self._set(i, C_PRICE, f"{precio:.2f}", bold=True,
                      bg=AMARILLO if lvl == avg_lvl else None)
            self._set(i, C_BID, str(int(bidsize)) if lvl == bid_lvl else "",
                      bg=VERDE if lvl == bid_lvl else None)
            self._set(i, C_ASK, str(int(asksize)) if lvl == ask_lvl else "",
                      bg=ROJO if lvl == ask_lvl else None)
            self._set_orden(i, C_BUY, buy_lvl.get(lvl))
            self._set_orden(i, C_SELL, sell_lvl.get(lvl))
            if lvl == (bid_lvl + ask_lvl) // 2:
                centro = i

        if recentrar and centro is not None:
            self.tabla.scrollToItem(self.tabla.item(centro, C_PRICE),
                                    QAbstractItemView.PositionAtCenter)

        # Aviso SOLO cuando importa: congelada y ademas el mercado se fue de la vista
        # (si el NBBO sigue visible no molesto con mensajes).
        fuera = not (bot_lvl <= bid_lvl <= top_lvl or bot_lvl <= ask_lvl <= top_lvl)
        if congelada and fuera:
            self._ayuda.setText(
                f"CONGELADA (mouse encima). El precio se fue a {bid:.2f} x {ask:.2f}: "
                f"saca el mouse o apreta Centrar."
            )
        else:
            self._ayuda.setText(self.AYUDA)

    def _centrar(self) -> None:
        """Boton 'Centrar': fuerza el re-centrado en el bid/ask actual (aunque este
        congelada por tener el mouse encima)."""
        self._last_nbbo = None
        self._ancla = None
        self._repoblar()

    def _set(self, row, col, text, bold=False, bg=None) -> None:
        it = QTableWidgetItem(text)
        it.setTextAlignment(Qt.AlignCenter)
        if bold:
            f = it.font()
            f.setBold(True)
            it.setFont(f)
        if bg is not None:
            it.setBackground(QBrush(bg))
        self.tabla.setItem(row, col, it)

    def _set_orden(self, row, col, datos) -> None:
        if datos is None:
            self._set(row, col, "")
            return
        ids, qty = datos
        it = QTableWidgetItem(f"{qty}   [X]")
        it.setTextAlignment(Qt.AlignCenter)
        it.setToolTip("Click para cancelar esta orden")
        it.setBackground(QBrush(AZUL))
        it.setData(Qt.UserRole, ids)
        self.tabla.setItem(row, col, it)

    # ---------- operar ----------
    def _precio_de_fila(self, row):
        it = self.tabla.item(row, C_PRICE)
        if it is None:
            return None
        try:
            return float(it.text())
        except ValueError:
            return None

    def _click_celda(self, row, col) -> None:
        if col not in (C_BUY, C_SELL):
            return
        it = self.tabla.item(row, col)
        ids = it.data(Qt.UserRole) if it is not None else None
        if ids:
            self._cancelar(ids)
            return
        precio = self._precio_de_fila(row)
        if precio is not None:
            self._mandar(Side.BUY if col == C_BUY else Side.SELL, precio)

    def _comprar_al_ask(self) -> None:
        if self._last:
            self._mandar(Side.BUY, self._last[1])

    def _vender_al_bid(self) -> None:
        if self._last:
            self._mandar(Side.SELL, self._last[0])

    def _broker(self):
        return self._broker_provider() if self._broker_provider else None

    def _mandar(self, side, precio) -> None:
        if not self._symbol:
            self._log("Ladder: elegi un simbolo primero.")
            return
        broker = self._broker()
        if broker is None:
            self._log("Ladder: no hay conexion para operar.")
            return
        qty = self.spin_size.value()
        try:
            orden = broker.place_order(
                OrderRequest(self._symbol, side, qty, round(precio, 2), OrderType.LIMIT,
                             extended=self.chk_ext.isChecked())
            )
            self._log(f"Ladder: {side.value} {qty} {self._symbol} @ {precio:.2f} "
                      f"enviada (id {orden.id}).")
        except Exception as e:  # noqa: BLE001
            self._log(f"*** Ladder: no se pudo mandar la orden ({e}) ***")

    def _cancelar(self, ids) -> None:
        broker = self._broker()
        if broker is None:
            self._log("Ladder: no hay conexion para operar.")
            return
        for oid in ids:
            try:
                broker.cancel_order(oid)
                self._log(f"Ladder: orden {oid} cancelada.")
            except Exception as e:  # noqa: BLE001
                self._log(f"Ladder: error al cancelar ({e})")

    def _cancelar_todas(self) -> None:
        broker = self._broker()
        if broker is None:
            self._log("Ladder: no hay conexion para operar.")
            return
        try:
            abiertas = broker.get_open_orders()
        except Exception as e:  # noqa: BLE001
            self._log(f"Ladder: no pude leer las ordenes ({e})")
            return
        if not abiertas:
            self._log("Ladder: no hay ordenes abiertas para cancelar.")
            return
        n = 0
        for o in abiertas:
            try:
                broker.cancel_order(o.id)
                n += 1
            except Exception:  # noqa: BLE001
                pass
        self._log(f"Ladder: cancele {n} de {len(abiertas)} orden(es) abierta(s).")

    def _mover_orden(self, ids, dest_row) -> None:
        nuevo = self._precio_de_fila(dest_row)
        if nuevo is None:
            return
        broker = self._broker()
        if broker is None:
            self._log("Ladder: no hay conexion para operar.")
            return
        for oid in ids:
            try:
                broker.modify_order(oid, price=round(nuevo, 2))
                self._log(f"Ladder: orden {oid} movida a {nuevo:.2f}.")
            except Exception as e:  # noqa: BLE001
                self._log(f"Ladder: no se pudo mover ({e})")
