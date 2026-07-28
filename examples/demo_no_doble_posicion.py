"""
Demo del salvaguarda principal del modo LIVE (vale tambien en paper):
si YA hay una posicion abierta en la cuenta (aunque sea de otro simbolo o
abierta a mano), el bot NO abre otra: avisa y se pausa.

Para correrlo:  python examples/demo_no_doble_posicion.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import OrderRequest, Side  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def main() -> None:
    broker = FakeBroker()
    broker.set_quote("XYZ", 50.00, 50.10)
    broker.set_quote("AAA", 100.00, 100.20)

    # Posicion PREEXISTENTE (como si la hubieras abierto a mano): largo 10 XYZ.
    broker.place_order(OrderRequest("XYZ", Side.BUY, 10, 50.10))
    print("Posicion preexistente:", broker.get_positions())
    print("-" * 60)

    cfg = EngineConfig(side=Side.BUY, quantity=10,
                       order1=OrderConfig(0.02, OffsetUnit.DOLLARS, 2))
    eng = BotEngine(broker, cfg, clock=FakeClock())

    print("El bot intenta procesar AAA (deberia NEGARSE y pausarse):")
    resultado = eng._process_symbol("AAA")
    print("-" * 60)
    ordenes_aaa = [o for o in broker.get_open_orders() if o.symbol == "AAA"]
    pausado = not eng._resume.is_set()
    print("resultado:", resultado, "| ordenes nuevas en AAA:", len(ordenes_aaa),
          "| bot pausado:", pausado)
    if resultado is None and not ordenes_aaa and pausado:
        print("OK: con una posicion abierta, el bot NO abre otra y se pausa.")
    else:
        print("FALLO: revisar.")


if __name__ == "__main__":
    main()
