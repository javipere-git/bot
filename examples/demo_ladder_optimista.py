"""
Dibujo optimista del ladder: la orden aparece apenas haces click, sin esperar al
broker. Verifica LA REGLA QUE NO SE NEGOCIA: lo que el broker todavia no confirmo
se ve DISTINTO y NO se puede operar.

Casos:
 1. Mandar -> se dibuja al instante, en gris, sin esperar al broker.
 2. Confirmada -> pasa a color pleno: VERDE si es compra, ROJO si es venta.
 3. Rechazada -> destella en rojo y despues desaparece (reversion visible).
 4. Lo no confirmado NO es clickeable (no se puede cancelar ni arrastrar).
 5. Mover -> el marcador salta al precio nuevo en ambar y desaparece del viejo.
 6. Cancelar -> queda en gris "todavia viva", NO se borra de la escalera.
 7. Vencimiento: si el broker nunca contesta, el dibujo se borra solo.
 8. Cuando llega la orden REAL, el dibujo provisorio se retira sin parpadeo.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt                                     # noqa: E402
from PySide6.QtWidgets import QApplication                        # noqa: E402

from tradingbot.core.models import Order, OrderStatus, Side       # noqa: E402
from tradingbot.gui.ladder_panel import C_BUY, C_SELL, LadderPanel  # noqa: E402
from tradingbot.gui.tema import colores                           # noqa: E402

fallos = []


def check(ok: bool, titulo: str, detalle: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FALLO'}  {titulo}{'  ->  ' + detalle if detalle else ''}")
    if not ok:
        fallos.append(titulo)


def celda(panel, precio, col):
    """Devuelve el item de la escalera en ese precio y columna (o None)."""
    for fila in range(panel.tabla.rowCount()):
        it = panel.tabla.item(fila, 2)          # C_PRICE
        if it is not None and abs(float(it.text()) - precio) < 0.005:
            return panel.tabla.item(fila, col), fila
    return None, None


def fondo(item):
    return item.background().color().name() if item is not None else None


def orden(oid, side, precio, qty=10):
    return Order(id=str(oid), symbol="AAA", side=side, quantity=qty, price=precio,
                 status=OrderStatus.OPEN, filled_quantity=0)


app = QApplication.instance() or QApplication([])

# Panel SIN hilo del broker (broker_provider=None): asi el camino es sincronico y
# se puede controlar el resultado a mano, que es justo lo que hay que probar.
panel = LadderPanel(broker_provider=None)
panel.detener()                      # no queremos el hilo en la prueba
panel._worker = None
panel.ed_symbol.setText("AAA")
panel._cambiar_symbol()
panel.actualizar_quote("AAA", 100.00, 100.10, 300, 300)
panel._repintar()

print("\n=== 0. EL CAMINO REAL: un click, y la orden ya esta dibujada ===")
# Esta es la prueba que de verdad importa: no que el dibujo funcione si lo llamo a
# mano, sino que un CLICK lo produzca ANTES de que el broker conteste. El broker
# falso anota, en el momento exacto en que le piden la orden, si la escalera ya la
# estaba mostrando.


class BrokerLento:
    """Se comporta como un broker que tarda: lo unico que mira es si la pantalla
    ya habia dibujado la orden cuando le llego el pedido."""

    def __init__(self):
        self.ya_dibujada = None
        self.pedidos = 0

    def place_order(self, req):
        self.pedidos += 1
        it, _ = celda(panel, req.price, C_BUY if req.side is Side.BUY else C_SELL)
        self.ya_dibujada = it is not None and it.text().strip() != ""
        time.sleep(0.3)                      # el broker tarda
        return orden("real-1", req.side, req.price, req.quantity)

    def get_positions(self):
        return []


lento = BrokerLento()
panel._broker_provider = lambda: lento
panel.spin_size.setValue(25)
_, fila_bid = celda(panel, 100.02, 1)        # C_BID
t0 = time.monotonic()
panel._click_celda(fila_bid, 1)              # click REAL en la columna Bid = comprar
tardo = time.monotonic() - t0
check(lento.pedidos == 1, "el click mando la orden al broker")
check(lento.ya_dibujada is True,
      "la escalera YA la mostraba cuando el broker todavia no habia contestado")
check(tardo >= 0.3, "y el broker efectivamente tardo (no es que fue instantaneo)",
      f"{tardo*1000:.0f} ms")
panel._pend.clear()
panel._orders = []
panel._broker_provider = None
panel._repoblar()

print("\n=== 1. Mandar: se dibuja al instante, sin esperar al broker ===")
clave = panel._pend_agregar({"tipo": "nueva", "compra": True, "qty": 25,
                             "precio": 100.02, "ids": []})
it, _ = celda(panel, 100.02, C_BUY)
check(it is not None and it.text().strip() != "", "la orden aparece YA en la escalera",
      it.text() if it else "vacia")
check(fondo(it) == colores("orden_pendiente").name(),
      "en gris (sin confirmar), no del color de una confirmada", fondo(it))

print("\n=== 4. Lo no confirmado NO se puede operar ===")
check(not it.data(Qt.UserRole), "no tiene ids: un click no la cancela")
check(it.data(Qt.UserRole + 1) == "nueva", "queda marcada como provisoria")
antes = len(panel._pend)
panel._click_celda(_ if _ is not None else 0, C_BUY)
check(len(panel._pend) == antes, "clickearla no dispara ninguna cancelacion")

print("\n=== 2. Confirmada: verde la compra, rojo la venta ===")
panel._resultado_del_worker(clave, True, "id-1")
panel._orders = [orden("id-1", Side.BUY, 100.02, 25)]
panel._repoblar()
it, _ = celda(panel, 100.02, C_BUY)
check(fondo(it) == colores("orden_buy").name(), "compra confirmada en VERDE", fondo(it))
check(bool(it.data(Qt.UserRole)), "ya es clickeable (se puede cancelar y arrastrar)")

panel._orders.append(orden("id-2", Side.SELL_SHORT, 100.08, 30))
panel._repoblar()
it_v, _ = celda(panel, 100.08, C_SELL)
check(fondo(it_v) == colores("orden_sell").name(),
      "venta en corto confirmada en ROJO", fondo(it_v))

print("\n=== 8. Al llegar la orden real, el dibujo provisorio se retira ===")
check(not panel._pend, "no quedan dibujos provisorios", f"{len(panel._pend)} pendiente(s)")

print("\n=== 3. Rechazada: destella y despues desaparece ===")
clave = panel._pend_agregar({"tipo": "nueva", "compra": False, "qty": 5,
                             "precio": 100.09, "ids": []})
panel._resultado_del_worker(clave, False, "")
it, _ = celda(panel, 100.09, C_SELL)
check(fondo(it) == colores("orden_rechazada").name(), "destella en rojo fuerte", fondo(it))
panel._pend[clave]["t_fin"] = time.monotonic() - 0.01    # se cumple el destello
panel._repoblar()
it, _ = celda(panel, 100.09, C_SELL)
check(not panel._pend and (it is None or it.text().strip() == ""),
      "despues del destello se borra sola (reversion visible)")

print("\n=== 5. Mover: salta al precio nuevo en ambar y deja el viejo ===")
clave = panel._mover_orden_prueba = None
panel._orders = [orden("id-1", Side.BUY, 100.02, 25)]
panel._repoblar()
clave = panel._pend_agregar({"tipo": "mover", "compra": True, "qty": 25,
                             "precio": 100.05, "ids": ["id-1"], "origen": 100.02})
nuevo, _ = celda(panel, 100.05, C_BUY)
viejo, _ = celda(panel, 100.02, C_BUY)
check(fondo(nuevo) == colores("orden_moviendo").name(),
      "aparece en el destino, en ambar", fondo(nuevo))
check(viejo is None or viejo.text().strip() == "",
      "y ya no se ve en el precio viejo")
panel._resultado_del_worker(clave, False, "")
panel._pend[clave]["t_fin"] = time.monotonic() - 0.01
panel._repoblar()
viejo, _ = celda(panel, 100.02, C_BUY)
check(viejo is not None and viejo.text().strip() != "" and
      fondo(viejo) == colores("orden_buy").name(),
      "si el broker la rechaza, vuelve a su lugar", fondo(viejo))

print("\n=== 6. Cancelar: queda en gris, NO se borra (todavia esta viva) ===")
clave = panel._pend_agregar(panel._marca_cancelacion(["id-1"]))
it, _ = celda(panel, 100.02, C_BUY)
check(it is not None and it.text().strip() != "",
      "la orden SIGUE VISIBLE mientras se cancela", it.text() if it else "vacia")
check(fondo(it) == colores("orden_pendiente").name(),
      "pero en gris, para no creer que ya no esta", fondo(it))
panel._resultado_del_worker(clave, True, "")
panel._orders = []                                # el broker ya la saco
panel._repoblar()
it, _ = celda(panel, 100.02, C_BUY)
check(not panel._pend and (it is None or it.text().strip() == ""),
      "recien cuando el broker confirma, desaparece")

print("\n=== 7. Vencimiento: si el broker nunca contesta, no queda un fantasma ===")
clave = panel._pend_agregar({"tipo": "nueva", "compra": True, "qty": 9,
                             "precio": 100.01, "ids": []})
panel._pend[clave]["t"] = time.monotonic() - (panel.TTL_PEND + 1)
panel._repoblar()
it, _ = celda(panel, 100.01, C_BUY)
check(not panel._pend and (it is None or it.text().strip() == ""),
      f"se borra sola despues de {panel.TTL_PEND:.0f}s sin respuesta")

print("\n=== Los cuatro estados son colores DISTINTOS ===")
tonos = {n: colores(n).name() for n in
         ("orden_buy", "orden_sell", "orden_pendiente", "orden_moviendo",
          "orden_rechazada")}
check(len(set(tonos.values())) == len(tonos),
      "ningun estado se confunde con otro", str(tonos))

print()
if fallos:
    print(f"PROBLEMAS: {len(fallos)}")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("OK: la orden se ve al instante, y lo no confirmado nunca se confunde"
      " con lo confirmado.")
