"""
Usar la orden que YA viene en el aviso del broker, en vez de volver a preguntarla.

EL PROBLEMA: cuando el broker avisaba que una orden cambio, tirabamos el contenido
del aviso y le preguntabamos "¿como quedo esa orden?". Le preguntabamos algo que
acababa de decirnos. Costo: ~1 segundo y dos llamadas por accion, teniendo el dato.

Cada broker manda distinto, y eso es parte de lo que se verifica:
    Alpaca      -> la orden ENTERA
    Tastytrade  -> la orden ENTERA, envuelta en {'type': 'Order', 'data': {...}}
    Tradier     -> SOLO id y estado (ni simbolo ni lado)

LA REGLA QUE SE RESPETA: el aviso es un camino RAPIDO que se suma, nunca un
reemplazo. La lectura periodica sigue corriendo como red, asi que si un aviso se
pierde (una reconexion del canal) no se pierde la orden.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tradingbot.core.models import Order, OrderStatus, Side          # noqa: E402
from tradingbot.gui.market_worker import MarketWorker                # noqa: E402

fallos = []


def check(ok, titulo, detalle=""):
    print(f"  {'OK  ' if ok else 'FALLO'}  {titulo}{'  ->  ' + detalle if detalle else ''}")
    if not ok:
        fallos.append(titulo)


print("\n=== 1. Cada conector entiende SU formato de aviso ===")

from tradingbot.connectors.alpaca import AlpacaBroker                # noqa: E402
from tradingbot.connectors.tastytrade import TastytradeBroker        # noqa: E402
from tradingbot.connectors.tradier import TradierBroker              # noqa: E402

alp = AlpacaBroker.__new__(AlpacaBroker)          # sin conectar: solo se traduce
aviso_alpaca = {"id": "a-1", "symbol": "AAPL", "side": "buy", "qty": "25",
                "limit_price": "305.10", "type": "limit", "status": "new",
                "extended_hours": False}
oid, estado, orden = alp.orden_de_aviso(aviso_alpaca)
check(oid == "a-1" and orden is not None, "Alpaca: saca la orden del aviso", str(oid))
if orden is not None:
    check(orden.symbol == "AAPL" and orden.quantity == 25 and orden.price == 305.10,
          "y viene COMPLETA (simbolo, cantidad, precio)",
          f"{orden.symbol} {orden.quantity} @ {orden.price}")

tas = TastytradeBroker.__new__(TastytradeBroker)
aviso_tasty = {"type": "Order", "data": {
    "id": "t-9", "status": "Filled", "price": "14.20", "order-type": "Limit",
    "legs": [{"symbol": "F", "action": "Buy to Open", "quantity": "10",
              "fills": [{"quantity": "10", "fill-price": "14.19"}]}]}}
oid, estado, orden = tas.orden_de_aviso(aviso_tasty)
check(oid == "t-9" and orden is not None, "Tastytrade: saca la orden del aviso", str(oid))
if orden is not None:
    check(orden.symbol == "F" and orden.status == OrderStatus.FILLED,
          "y viene completa, con su estado", f"{orden.symbol} {orden.status}")
check(tas.orden_de_aviso({"type": "AccountBalance", "data": {}})[0] is None,
      "un aviso que NO es de orden se ignora (saldo, posicion)")

tra = TradierBroker.__new__(TradierBroker)
oid, estado, orden = tra.orden_de_aviso({"event": "order", "id": 1234,
                                         "status": "filled"})
check(oid == "1234" and estado == OrderStatus.FILLED,
      "Tradier: saca el id y el estado", f"{oid} / {estado}")
check(orden is None,
      "y NO inventa una orden (su aviso no trae ni simbolo ni lado)")

print("\n=== 2. Un broker que no lo implemente sigue como siempre ===")
from tradingbot.connectors.fake_broker import FakeBroker             # noqa: E402
check(FakeBroker().orden_de_aviso({"lo": "que sea"}) == (None, None, None),
      "no entiende el aviso y no rompe nada")


class BrokerMudo(FakeBroker):
    """Cuenta si le piden las ordenes: el camino rapido NO debe pedir nada."""

    def __init__(self):
        super().__init__()
        self.veces_que_le_pidieron = 0

    def get_orders(self, limit=None):
        self.veces_que_le_pidieron += 1
        return super().get_orders(limit=limit)


def orden(oid, estado, precio=100.0, qty=10):
    return Order(id=oid, symbol="AAA", side=Side.BUY, quantity=qty, price=precio,
                 status=estado, filled_quantity=0)


print("\n=== 3. El aviso actualiza la pantalla SIN pedirle nada al broker ===")
br = BrokerMudo()
w = MarketWorker(br)
emitidas = {"abiertas": None, "cerradas": None}
w.orders.connect(lambda l: emitidas.__setitem__("abiertas", l))
w.closed_orders.connect(lambda l: emitidas.__setitem__("cerradas", l))

w.aplicar_aviso("x-1", OrderStatus.OPEN, orden("x-1", OrderStatus.OPEN))
check(br.veces_que_le_pidieron == 0, "cero llamadas al broker",
      f"{br.veces_que_le_pidieron}")
check(emitidas["abiertas"] and emitidas["abiertas"][0].id == "x-1",
      "la orden aparece en la tabla al instante")

print("\n=== 4. Con solo el id y el estado (Tradier) ===")
emitidas["abiertas"] = emitidas["cerradas"] = None   # para no leer lo de antes
w.aplicar_aviso("x-1", OrderStatus.FILLED, None)     # se lleno
# OJO: hay que exigir que se HAYA emitido. Con "not emitidas[...]" un None pasaria
# el chequeo sin que la pantalla se enterara de nada: una prueba que no puede fallar.
check(emitidas["abiertas"] == [], "sale de las abiertas", str(emitidas["abiertas"]))
check(bool(emitidas["cerradas"])
      and emitidas["cerradas"][0].status == OrderStatus.FILLED,
      "y pasa a las cerradas, como llenada", str(emitidas["cerradas"]))
check(bool(emitidas["cerradas"]) and emitidas["cerradas"][0].symbol == "AAA"
      and emitidas["cerradas"][0].price == 100.0,
      "conservando lo que ya sabiamos de ella (simbolo y precio)")
check(br.veces_que_le_pidieron == 0, "y sigue sin pedirle nada al broker")

print("\n=== 5. Lo que NO se conoce, no se inventa ===")
antes = dict(emitidas)
w.aplicar_aviso("desconocida-9", OrderStatus.FILLED, None)
check(emitidas["abiertas"] == antes["abiertas"]
      and emitidas["cerradas"] == antes["cerradas"],
      "un id que la pantalla no conoce no cambia nada (lo trae la lectura)")

print("\n=== 6. La lectura de respaldo sigue existiendo ===")
# el camino rapido NO reemplaza al periodico: si se pierde un aviso, la lectura lo trae
w._emitir_ordenes()
check(br.veces_que_le_pidieron == 1,
      "la lectura periodica sigue pidiendo las ordenes igual que antes",
      f"{br.veces_que_le_pidieron} llamada(s)")

print()
if fallos:
    print(f"PROBLEMAS: {len(fallos)}")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("OK: el aviso se aprovecha entero, sin llamadas, y la red de respaldo queda.")
