"""
Demo de robustez (Fase 6): el "3 strikes".

Usa un broker que SIEMPRE rechaza las ordenes. El bot deberia frenarse solo
(ABORTED) tras 3 rechazos seguidos, sin caerse.

Para correrlo:  python examples/demo_robustez.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import OrderRequest, Side  # noqa: E402


class BrokerQueRechaza(FakeBroker):
    """Un broker que rechaza toda orden con un error GENERAL (deberia frenar)."""

    def place_order(self, request: OrderRequest):
        raise RuntimeError("orden rechazada (prueba)")


class BrokerSimboloNoOperable(FakeBroker):
    """Rechaza por un motivo del SIMBOLO (no shorteable) -> deberia saltear, no frenar."""

    def place_order(self, request: OrderRequest):
        raise RuntimeError("Symbol not shortable")


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def main() -> None:
    broker = BrokerQueRechaza()
    broker.set_quote("AAA", 100.00, 100.20)

    cfg = EngineConfig(
        side=Side.BUY, quantity=10,
        order1=OrderConfig(0.0, OffsetUnit.DOLLARS, 1),
        loop_watchlist=True,   # seguiria reintentando... pero los strikes lo frenan
        max_strikes=3,
    )
    eng = BotEngine(broker, cfg, clock=FakeClock())

    print("El broker rechaza todas las ordenes. El bot deberia frenar tras 3 strikes:")
    print("-" * 60)
    outcome = eng.run_watchlist(["AAA"])
    print("-" * 60)
    print("Outcome:", outcome.value)
    print("Strikes acumulados:", eng._order_strikes, "| abort:", eng._abort)
    if outcome.value == "aborted" and eng._abort:
        print("OK: el bot se freno solo (no se cayo) tras los rechazos.")
    else:
        print("FALLO: revisar.")

    print()
    print("Caso 2: rechazo por SIMBOLO no operable (deberia SALTEAR, NO frenar):")
    print("-" * 60)
    b2 = BrokerSimboloNoOperable()
    b2.set_quote("AAA", 100.00, 100.20)
    b2.set_quote("BBB", 50.00, 50.10)
    cfg2 = EngineConfig(
        side=Side.BUY, quantity=10,
        order1=OrderConfig(0.0, OffsetUnit.DOLLARS, 1),
        loop_watchlist=False, max_strikes=3,
    )
    eng2 = BotEngine(b2, cfg2, clock=FakeClock())
    out2 = eng2.run_watchlist(["AAA", "BBB"])
    print("-" * 60)
    print("Outcome:", out2.value, "| strikes:", eng2._order_strikes, "| abort:", eng2._abort)
    if out2.value == "no_entry" and eng2._order_strikes == 0 and not eng2._abort:
        print("OK: saltea los simbolos no operables sin frenar el bot.")
    else:
        print("FALLO: revisar.")


if __name__ == "__main__":
    main()
