"""
Prueba el caso de la ORDEN REEMPLAZADA (bug real encontrado el 22/07/2026 operando
en Alpaca con dinero real).

El problema: al repreciar (Orden 1 -> Orden 2, o los niveles de salida), algunos
brokers NO modifican la orden sino que la REEMPLAZAN por una nueva con OTRO id:
  - Tradier: modifica, conserva el id.
  - Alpaca: cancela la vieja y crea una NUEVA con id distinto.
Si el bot se queda con el id viejo, despues cancela una orden ya muerta y la NUEVA
queda HUERFANA: viva, sin control del bot, congelando el poder de compra y -lo mas
grave- pudiendo llenarse sola y dejar una posicion que nadie maneja.

Parte 1: con el broker de mentira (no toca nada), simulando los dos comportamientos.
Parte 2 (opcional, con --real): contra la cuenta PAPER de Alpaca, ciclo completo.

    python examples/demo_orden_reemplazada.py
    python examples/demo_orden_reemplazada.py --real
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import Order, OrderStatus, Side  # noqa: E402


class BrokerQueReemplaza(FakeBroker):
    """Se comporta como Alpaca: al modificar, cancela la orden y crea una NUEVA."""

    def modify_order(self, order_id, *, price=None, quantity=None):
        vieja = self._orders[order_id]
        if not vieja.is_active:
            raise ValueError(f"La orden {order_id} ya no esta viva")
        vieja.status = OrderStatus.CANCELED          # Alpaca mata la vieja...
        nueva = Order(
            id=f"REEMPLAZO-{next(self._ids)}",       # ...y crea otra con OTRO id
            symbol=vieja.symbol,
            side=vieja.side,
            quantity=vieja.quantity,
            price=price if price is not None else vieja.price,
            status=OrderStatus.OPEN,
        )
        self._orders[nueva.id] = nueva
        self._try_fill(nueva)
        return nueva


def _config() -> EngineConfig:
    return EngineConfig(
        side=Side.BUY,
        quantity=10,
        # ninguna de las dos se llena: quedan vivas hasta que el bot las cancele
        order1=OrderConfig(offset=0.0, unit=OffsetUnit.DOLLARS, timeout_s=1.0),
        order2=OrderConfig(offset=0.05, unit=OffsetUnit.DOLLARS, timeout_s=1.0),
        loop_watchlist=False,
    )


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def parte1() -> bool:
    print("PARTE 1: broker que REEMPLAZA la orden (como Alpaca)")
    print("-" * 70)
    broker = BrokerQueReemplaza()
    broker.set_quote("AAA", 100.00, 100.50)
    engine = BotEngine(broker, _config(), clock=FakeClock(), log=lambda m: print("   " + m))
    engine._process_symbol("AAA")     # entra, reprecia a Orden 2, no se llena, cancela
    print("-" * 70)

    vivas = [o for o in broker._orders.values() if o.is_active]
    print(f"ordenes que quedaron VIVAS: {len(vivas)}  (esperado 0)")
    for o in vivas:
        print(f"   HUERFANA -> {o.id} {o.symbol} {o.quantity} @ {o.price}")
    ok = not vivas
    print("OK: el bot siguio el id nuevo y no dejo ordenes sueltas.\n" if ok
          else "*** FALLO: quedo una orden huerfana.\n")
    return ok


def parte2() -> bool:
    print("PARTE 2: contra la cuenta PAPER de Alpaca (dinero simulado)")
    print("-" * 70)
    from tradingbot.connectors.alpaca import AlpacaBroker

    b = AlpacaBroker.from_credentials(environment="paper")
    previas = [o for o in b.get_orders() if o.is_active]
    if previas:
        print(f"   (limpio {len(previas)} orden(es) viva(s) de antes)")
        for o in previas:
            b.cancel_order(o.id)
        time.sleep(1.5)

    q = b.get_quote("SPY")
    base = round((q.bid or 600) * 0.5, 2)     # lejos: no se llena
    cfg = EngineConfig(
        side=Side.BUY,
        quantity=1,
        order1=OrderConfig(offset=0.0, unit=OffsetUnit.DOLLARS, timeout_s=2.0),
        order2=OrderConfig(offset=0.02, unit=OffsetUnit.DOLLARS, timeout_s=2.0),
        loop_watchlist=False,
    )

    class BrokerPrecioFijo(AlpacaBroker):
        """Fuerza un precio lejano para que la orden NO se llene en la prueba."""

        def get_quote(self, symbol):
            qq = super().get_quote(symbol)
            qq.bid, qq.ask = base, round(base + 0.10, 2)
            return qq

    bb = BrokerPrecioFijo.from_credentials(environment="paper")
    engine = BotEngine(bb, cfg, log=lambda m: print("   " + m))
    engine._process_symbol("SPY")
    time.sleep(2.0)
    print("-" * 70)

    vivas = [o for o in b.get_orders() if o.is_active]
    print(f"ordenes que quedaron VIVAS en Alpaca: {len(vivas)}  (esperado 0)")
    for o in vivas:
        print(f"   HUERFANA -> {o.id} {o.symbol} {o.quantity} @ {o.price}")
        b.cancel_order(o.id)
    ok = not vivas
    print("OK: contra Alpaca real (paper) no quedan ordenes huerfanas.\n" if ok
          else "*** FALLO: quedo una orden huerfana en Alpaca.\n")
    return ok


def main() -> None:
    ok = parte1()
    if "--real" in sys.argv:
        ok = parte2() and ok
    else:
        print("(para probarlo tambien contra la cuenta paper real: --real)")
    print("OK: el bot maneja bien los brokers que reemplazan ordenes."
          if ok else "*** HAY FALLOS.")


if __name__ == "__main__":
    main()
