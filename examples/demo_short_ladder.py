"""
Ladder: tilde SS (short sell) y la red de seguridad para Alpaca.

Que se verifica:
  1. SS destildado -> las ventas salen como 'sell' (solo cierran un largo).
  2. SS tildado    -> las ventas salen como 'sell_short' (ABREN un corto).
  3. Las compras NO cambian con el tilde.
  4. RED DE SEGURIDAD: en un broker que NO distingue venta de venta en corto (Alpaca),
     con SS apagado la app FRENA la venta que dejaria corto. En Tradier no estorba:
     ahi el propio broker rechaza la venta de mas.

Por que existe (4): a Alpaca solo se le puede mandar buy/sell. Vender estando sin
posicion abre un CORTO en silencio; al usuario le paso quedar corto sin querer.

    python examples/demo_short_ladder.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.models import Position, Side  # noqa: E402
from tradingbot.gui.ladder_panel import C_ASK, C_BID, LadderPanel  # noqa: E402


class BrokerTradier(FakeBroker):
    """Distingue sell de sell_short (como Tradier)."""

    def distingue_venta_en_corto(self) -> bool:
        return True


class BrokerAlpaca(FakeBroker):
    """NO distingue: solo buy/sell (como Alpaca)."""

    def distingue_venta_en_corto(self) -> bool:
        return False


def _fila(ladder, precio):
    for i in range(ladder.tabla.rowCount()):
        if abs((ladder._precio_de_fila(i) or -1) - precio) < 0.0001:
            return i
    return None


def _ultima_orden(broker, antes: int, segundos: float = 5.0):
    """Espera a que la orden LLEGUE al broker y la devuelve.

    Desde que el ladder manda las ordenes en un hilo propio (para no congelar la
    pantalla), el click vuelve al instante y la orden sale un momento despues. Por
    eso no se puede mirar el broker en la misma linea del click: hay que esperarla.
    Devuelve None si no llego (asi el demo falla con un mensaje claro y no revienta).
    """
    import time
    app = QApplication.instance()
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        if app is not None:
            app.processEvents()
        ordenes = broker.get_open_orders()
        if len(ordenes) > antes:
            return ordenes[-1]
        time.sleep(0.02)
    return None


def _armar(broker):
    l = LadderPanel(broker_provider=lambda: broker, log=lambda m: None)
    l.ed_symbol.setText("AAPL")
    l._cambiar_symbol()
    l.actualizar_quote("AAPL", 100.00, 100.10, 500, 400)
    l._repintar()
    l.spin_size.setValue(10)
    return l


def main() -> None:
    app = QApplication(sys.argv)

    print("1) SS destildado -> la venta sale como 'sell'")
    b = BrokerTradier()
    b.set_quote("AAPL", bid=100.00, ask=100.10)
    l = _armar(b)
    antes = len(b.get_open_orders())
    l._click_celda(_fila(l, 100.20), C_ASK)
    o = _ultima_orden(b, antes)
    ok1 = o is not None and o.side == Side.SELL
    print(f"   lado enviado: {o.side.value if o else 'NO LLEGO'} (esperado sell)")
    print(f"   -> {'OK' if ok1 else '*** FALLO'}\n")

    print("2) SS tildado -> la venta sale como 'sell_short'")
    l.chk_short.setChecked(True)
    antes = len(b.get_open_orders())
    l._click_celda(_fila(l, 100.15), C_ASK)
    o = _ultima_orden(b, antes)
    ok2 = o is not None and o.side == Side.SELL_SHORT
    print(f"   lado enviado: {o.side.value if o else 'NO LLEGO'} (esperado sell_short)")
    print(f"   -> {'OK' if ok2 else '*** FALLO'}\n")

    print("3) Las COMPRAS no cambian con el tilde")
    antes = len(b.get_open_orders())
    l._click_celda(_fila(l, 99.90), C_BID)
    o = _ultima_orden(b, antes)
    ok3 = o is not None and o.side == Side.BUY
    print(f"   lado enviado: {o.side.value if o else 'NO LLEGO'} "
          f"(esperado buy, con SS tildado)")
    print(f"   -> {'OK' if ok3 else '*** FALLO'}\n")

    print("4) RED DE SEGURIDAD en un broker que no distingue (Alpaca)")
    a = BrokerAlpaca()
    a.set_quote("AAPL", bid=100.00, ask=100.10)
    la = _armar(a)
    la.set_positions([])                       # SIN posicion
    antes = len(a.get_open_orders())
    la._click_celda(_fila(la, 100.20), C_ASK)  # venta con SS apagado
    # frenada = NO tiene que llegar ninguna (se espera un rato para estar seguros)
    sin_pos = _ultima_orden(a, antes, segundos=1.0) is None
    print(f"   sin posicion, SS apagado -> venta frenada: {sin_pos}")

    la.set_positions([Position("AAPL", quantity=25, avg_price=99.0)])
    antes = len(a.get_open_orders())
    la._click_celda(_fila(la, 100.15), C_ASK)  # 10 de 25: entra
    con_pos = _ultima_orden(a, antes) is not None
    print(f"   con 25 en cartera, vendo 10 -> pasa: {con_pos}")

    la.spin_size.setValue(40)                  # 40 de 25: quedaria corto
    antes = len(a.get_open_orders())
    la._click_celda(_fila(la, 100.18), C_ASK)
    de_mas = _ultima_orden(a, antes, segundos=1.0) is None
    print(f"   con 25 en cartera, vendo 40 -> frenada: {de_mas}")

    la.chk_short.setChecked(True)              # a proposito: pasa
    antes = len(a.get_open_orders())
    la._click_celda(_fila(la, 100.22), C_ASK)
    a_proposito = _ultima_orden(a, antes) is not None
    print(f"   con SS tildado (a proposito) -> pasa: {a_proposito}")
    ok4 = sin_pos and con_pos and de_mas and a_proposito
    print(f"   -> {'OK' if ok4 else '*** FALLO'}\n")

    print("5) En Tradier la red NO estorba (el broker ya rechaza solo)")
    lt = _armar(BrokerTradier())
    lt.set_positions([])                       # sin posicion
    permite = lt._venta_permitida(lt._broker(), Side.SELL, 10)
    ok5 = permite
    print(f"   sin posicion, SS apagado -> la app deja pasar: {permite}")
    print(f"   -> {'OK' if ok5 else '*** FALLO'}\n")

    todo = ok1 and ok2 and ok3 and ok4 and ok5
    print("OK: el tilde SS manda short sell y la red protege donde hace falta."
          if todo else "*** HAY FALLOS.")
    return todo


if __name__ == "__main__":
    ok = main()
    sys.stdout.flush()
    os._exit(0 if ok else 1)
