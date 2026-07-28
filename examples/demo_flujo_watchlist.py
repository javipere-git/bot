"""
Demo del recorrido de la watchlist (run_watchlist) - verifica el fix del flujo.

Con el conector de mentira, comprueba que el bot, tras CERRAR una posicion,
CONTINUA con el siguiente simbolo (no finaliza). Usa pause_on_fill=False y
loop=False, con entradas que cruzan (se llenan ya) y salida cruzando.

Para correrlo:  python examples/demo_flujo_watchlist.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, ExitLevel, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def main() -> None:
    broker = FakeBroker()
    broker.set_quote("AAA", 100.00, 100.20)
    broker.set_quote("BBB", 50.00, 50.10)

    cfg = EngineConfig(
        side=Side.BUY,
        quantity=10,
        order1=OrderConfig(0.30, OffsetUnit.DOLLARS, 2),       # cruza -> entra ya
        exit_levels=[ExitLevel(0, OffsetUnit.DOLLARS, 2, cross=True)],  # cierra cruzando
        pause_on_fill=False,    # que siga solo
        loop_watchlist=False,   # una sola pasada
    )

    print("Recorriendo watchlist [AAA, BBB] (pause_on_fill=False, loop=False):")
    print("-" * 60)
    outcome = BotEngine(broker, cfg, clock=FakeClock()).run_watchlist(["AAA", "BBB"])
    print("-" * 60)
    print("Outcome:", outcome.value)
    print("Posiciones al final:", broker.get_positions(), "(vacio = todo cerrado)")
    print(">>> Si aparecieron AAA y BBB arriba, el bot NO finalizo tras el primero.")


if __name__ == "__main__":
    main()
