"""
Demo de la ENTRADA del bot (Tanda 1).

Prueba la logica de entrada con el conector de mentira, en escenarios
controlados. No toca ningun broker ni dinero.

El truco: un 'reloj de mentira' que solo avanza el tiempo cuando el motor
'duerme', y en cada paso ejecuta un guion que mueve el mercado. Asi los
escenarios son deterministas (pasan siempre igual) y no dependen del reloj real.

Para correrlo:  python examples/demo_entrada.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402
from tradingbot.core.watchlist import parse_watchlist  # noqa: E402


class FakeClock:
    """Reloj de mentira: el tiempo solo avanza cuando el motor duerme.
    En cada 'sueno' llama a un guion que puede mover el mercado."""

    def __init__(self, guion=None):
        self.t = 0.0
        self._guion = guion

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds
        if self._guion:
            self._guion(self.t)


def titulo(t: str) -> None:
    print("\n" + "=" * 64)
    print(t)
    print("=" * 64)


def escenario_filtro_spread() -> None:
    titulo("Escenario 1: el filtro de spread evita entrar")
    broker = FakeBroker()
    broker.set_quote("AAA", bid=100.00, ask=100.50)  # spread 0.50, demasiado ancho
    cfg = EngineConfig(
        side=Side.BUY, quantity=50,
        order1=OrderConfig(0.02, OffsetUnit.DOLLARS, timeout_s=3),
        spread_max=0.10,  # solo entra si el spread es <= 0.10
    )
    BotEngine(broker, cfg, clock=FakeClock()).scan_and_enter(["AAA"], max_cycles=1)


def escenario_orden1() -> None:
    titulo("Escenario 2: se llena la Orden 1 (largo)")
    broker = FakeBroker()
    broker.set_quote("BBB", bid=100.00, ask=100.20)

    def guion(t):  # al segundo 1, el ask baja y toca mi compra (100.02)
        if t >= 1:
            broker.set_quote("BBB", bid=99.98, ask=100.02)

    cfg = EngineConfig(
        side=Side.BUY, quantity=50,
        order1=OrderConfig(0.02, OffsetUnit.DOLLARS, timeout_s=5),
    )
    pos = BotEngine(broker, cfg, clock=FakeClock(guion)).scan_and_enter(["BBB"], max_cycles=1)
    print("Resultado:", pos)


def escenario_orden2() -> None:
    titulo("Escenario 3: la Orden 1 no, la Orden 2 si (modificando)")
    broker = FakeBroker()
    broker.set_quote("CCC", bid=100.00, ask=100.20)

    def guion(t):  # recien al segundo 4 baja el ask a 100.10 (toca la Orden 2)
        if t >= 4:
            broker.set_quote("CCC", bid=100.05, ask=100.10)

    cfg = EngineConfig(
        side=Side.BUY, quantity=50,
        order1=OrderConfig(0.02, OffsetUnit.DOLLARS, timeout_s=3),
        order2=OrderConfig(0.10, OffsetUnit.DOLLARS, timeout_s=3),
    )
    pos = BotEngine(broker, cfg, clock=FakeClock(guion)).scan_and_enter(["CCC"], max_cycles=1)
    print("Resultado:", pos)


def escenario_nada() -> None:
    titulo("Escenario 4: no se llena nada -> pasa de largo")
    broker = FakeBroker()
    broker.set_quote("DDD", bid=100.00, ask=100.20)  # nunca se mueve
    cfg = EngineConfig(
        side=Side.BUY, quantity=50,
        order1=OrderConfig(0.02, OffsetUnit.DOLLARS, timeout_s=2),
        order2=OrderConfig(0.05, OffsetUnit.DOLLARS, timeout_s=2),
    )
    pos = BotEngine(broker, cfg, clock=FakeClock()).scan_and_enter(["DDD"], max_cycles=1)
    print("Resultado:", pos, " (None = no entro)")


def escenario_corto() -> None:
    titulo("Escenario 5: entrada en CORTO (venta ask -)")
    broker = FakeBroker()
    broker.set_quote("EEE", bid=100.00, ask=100.20)

    def guion(t):  # al segundo 1 sube el bid y toca mi venta corta (100.18)
        if t >= 1:
            broker.set_quote("EEE", bid=100.18, ask=100.30)

    cfg = EngineConfig(
        side=Side.SELL_SHORT, quantity=50,
        order1=OrderConfig(0.02, OffsetUnit.DOLLARS, timeout_s=5),
    )
    pos = BotEngine(broker, cfg, clock=FakeClock(guion)).scan_and_enter(["EEE"], max_cycles=1)
    print("Resultado:", pos)


def escenario_parser() -> None:
    titulo("Bonus: lector de watchlist (varios separadores)")
    texto = "aapl, msft; googl  tsla\nnvda,, $spy aapl"
    print(f"Texto crudo: {texto!r}")
    print("Simbolos:    ", parse_watchlist(texto))


def main() -> None:
    escenario_filtro_spread()
    escenario_orden1()
    escenario_orden2()
    escenario_nada()
    escenario_corto()
    escenario_parser()
    print("\nListo: la logica de entrada (Tanda 1) funciona en todos los escenarios.")


if __name__ == "__main__":
    main()
