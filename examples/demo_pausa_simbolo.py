"""
Pausa antes de entrar a un simbolo nuevo.

PARA QUE: hay brokers que no liberan al instante el poder de compra de una orden
recien cancelada. Medido en Tastytrade el 14/08/2026: tres segundos despues de
cancelar una orden de $4.541, rechazaron una de $670 teniendo $7.334 disponibles.

LO QUE SE VERIFICA (que es donde esta el valor, no en que "espere"):
 1. La pausa cae DESPUES de los filtros: un simbolo que se saltea no hace esperar.
 2. La cotizacion con la que se calcula la orden es la de DESPUES de la pausa.
 3. La referencia del GUARDIA tambien se actualiza con esa cotizacion fresca
    (si midiera desde el precio viejo, nace ciega: el punto ciego del 20/07/2026).
 4. En 0 no cambia nada: ni espera, ni pide una cotizacion de mas.
 5. Se puede Detener el bot DURANTE la pausa (no queda sordo esperando).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker            # noqa: E402
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine                        # noqa: E402
from tradingbot.core.models import Side                             # noqa: E402

fallos = []


def check(ok, titulo, detalle=""):
    print(f"  {'OK  ' if ok else 'FALLO'}  {titulo}{'  ->  ' + detalle if detalle else ''}")
    if not ok:
        fallos.append(titulo)


class Reloj:
    """Reloj de mentira: no espera de verdad, pero anota cuanto le pidieron."""

    def __init__(self):
        self.t = 1000.0
        self.dormido = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        s = max(0.0, s)
        self.dormido += s
        self.t += s


class BrokerEspia(FakeBroker):
    """Anota cada cotizacion pedida y, al mandar una orden, CUANTO se espero hasta
    ese momento. Medir el total dormido no sirve: incluiria la espera del llenado,
    que no tiene nada que ver con la pausa."""

    def __init__(self):
        super().__init__()
        self.quotes_pedidos = []
        self.espera_antes_de_mandar = None
        self.reloj = None

    def get_quote(self, symbol):
        q = super().get_quote(symbol)
        self.quotes_pedidos.append((symbol, q.bid, q.ask))
        return q

    def place_order(self, request):
        if self.espera_antes_de_mandar is None and self.reloj is not None:
            self.espera_antes_de_mandar = self.reloj.dormido
        return super().place_order(request)


def armar(pausa, spread_max=None):
    br = BrokerEspia()
    br.set_quote("AAA", 100.00, 100.20, 300, 300, volume=1_000_000)
    cfg = EngineConfig(
        side=Side.BUY, quantity=10,
        order1=OrderConfig(10, OffsetUnit.PERCENT_SPREAD, 1.0),
        order2=None, pausa_simbolo_s=pausa, spread_max=spread_max,
    )
    reloj = Reloj()
    br.reloj = reloj
    motor = BotEngine(br, cfg, clock=reloj, log=lambda m: None)
    return br, motor, reloj


print("\n=== 1. Un simbolo que NO pasa los filtros no hace esperar ===")
# spread_max 0.05 con un spread de 0.20 -> se saltea antes de la pausa
br, motor, reloj = armar(pausa=2.0, spread_max=0.05)
motor._process_symbol("AAA")
check(reloj.dormido == 0, "no espero nada por un simbolo que se saltea",
      f"durmio {reloj.dormido}s")
check(len(br.quotes_pedidos) == 1, "y pidio UNA sola cotizacion (no la de despues)",
      f"{len(br.quotes_pedidos)} cotizacion(es)")

print("\n=== 2. Un simbolo que SI pasa los filtros espera, y con precio fresco ===")
br, motor, reloj = armar(pausa=2.0)
# el precio cambia DURANTE la pausa: la orden tiene que salir con el nuevo
orig = br.get_quote


def mover_precio_al_segundo_pedido(symbol):
    q = orig(symbol)
    if len(br.quotes_pedidos) >= 1:      # ya hubo una: esta es la de despues
        br.set_quote("AAA", 101.00, 101.20, 300, 300, volume=1_000_000)
    return q


br.get_quote = mover_precio_al_segundo_pedido
motor._process_symbol("AAA")
check(br.espera_antes_de_mandar is not None and br.espera_antes_de_mandar >= 2.0,
      "espero la pausa ANTES de mandar la orden",
      f"{br.espera_antes_de_mandar}s")
check(len(br.quotes_pedidos) == 2,
      "pidio una cotizacion ANTES (filtros) y otra DESPUES (precio)",
      f"{len(br.quotes_pedidos)} cotizaciones")
ordenes = br.get_orders()
check(bool(ordenes), "mando la orden")
if ordenes:
    precio = ordenes[-1].price
    # bid nuevo 101.00 + 10% del spread (0.20) = 101.02
    check(abs(precio - 101.02) < 0.005,
          "el precio sale de la cotizacion NUEVA, no de la vieja",
          f"{precio:.2f} (viejo hubiera sido 100.02)")

print("\n=== 3. La referencia del guardia se actualiza con la fresca ===")
check(motor._entry_ref is not None and abs(motor._entry_ref - 101.00) < 0.005,
      "el guardia mide desde el bid nuevo (si no, nace ciego)",
      f"{motor._entry_ref}")

print("\n=== 4. En 0 se comporta EXACTAMENTE como antes ===")
br, motor, reloj = armar(pausa=0.0)
motor._process_symbol("AAA")
check(br.espera_antes_de_mandar == 0,
      "manda la orden sin esperar nada", f"{br.espera_antes_de_mandar}s")
check(len(br.quotes_pedidos) == 1, "y NO pide una cotizacion de mas",
      f"{len(br.quotes_pedidos)} cotizacion(es)")

print("\n=== 5. Se puede Detener el bot durante la pausa ===")
br, motor, reloj = armar(pausa=30.0)
sleep_orig = reloj.sleep
llamadas = {"n": 0}


def sleep_y_detener(s):
    llamadas["n"] += 1
    sleep_orig(s)
    if llamadas["n"] == 2:      # a mitad de la espera, apretan Detener
        motor.stop()


reloj.sleep = sleep_y_detener
antes_ordenes = len(br.get_orders())
motor._process_symbol("AAA")
check(reloj.dormido < 30.0, "corto la espera al detener (no durmio los 30s)",
      f"durmio {reloj.dormido:.1f}s de 30")
check(len(br.get_orders()) == antes_ordenes,
      "y NO mando la orden despues de que lo detuvieron")

print()
if fallos:
    print(f"PROBLEMAS: {len(fallos)}")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("OK: la pausa cae despues de los filtros, con precio fresco, y se puede frenar.")
