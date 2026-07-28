"""
Demo de la SALIDA del bot (Tanda 2).

Prueba el cierre escalonado y el guardia de movimiento en contra con el
conector de mentira, en escenarios controlados. No toca ningun broker ni dinero.

Para correrlo:  python examples/demo_salida.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import (  # noqa: E402
    EngineConfig,
    ExitLevel,
    GuardAction,
    GuardConfig,
    GuardUnit,
    OffsetUnit,
    OrderConfig,
)
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import OrderRequest, OrderType, Side  # noqa: E402


class FakeClock:
    """El tiempo solo avanza cuando el motor duerme; en cada paso, un guion
    puede mover el mercado. Hace los escenarios deterministas."""

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


def seed_largo(broker: FakeBroker, sym: str, qty: int, bid: float, ask: float):
    """Deja la cuenta YA con una posicion larga (entramos antes)."""
    broker.set_quote(sym, bid, ask)
    broker.place_order(OrderRequest(sym, Side.BUY, qty, ask, OrderType.LIMIT))  # llena al ask
    return next(p for p in broker.get_positions() if p.symbol == sym)


def _cfg(**extra) -> EngineConfig:
    base = dict(side=Side.BUY, quantity=50, order1=OrderConfig(0, OffsetUnit.DOLLARS, 1))
    base.update(extra)
    return EngineConfig(**base)


def s1_cierre_limpio() -> None:
    titulo("Salida 1: cierre limpio en el nivel 1 (largo)")
    b = FakeBroker()
    pos = seed_largo(b, "AAA", 50, 100.10, 100.30)

    def guion(t):
        if t >= 1:
            b.set_quote("AAA", 100.28, 100.40)  # el bid sube y toca mi venta

    cfg = _cfg(exit_levels=[ExitLevel(0.02, OffsetUnit.DOLLARS, 5)])
    out = BotEngine(b, cfg, clock=FakeClock(guion)).manage_exit(pos)
    print("Outcome:", out.value, "| posiciones:", b.get_positions())


def s2_escalonado() -> None:
    titulo("Salida 2: escalonado, cierra en el nivel 2 (largo)")
    b = FakeBroker()
    pos = seed_largo(b, "BBB", 50, 100.10, 100.30)

    def guion(t):
        if t >= 4:
            b.set_quote("BBB", 100.22, 100.40)

    cfg = _cfg(exit_levels=[
        ExitLevel(0.02, OffsetUnit.DOLLARS, 3),
        ExitLevel(0.10, OffsetUnit.DOLLARS, 3),
    ])
    out = BotEngine(b, cfg, clock=FakeClock(guion)).manage_exit(pos)
    print("Outcome:", out.value, "| posiciones:", b.get_positions())


def s3_guardia_manual() -> None:
    titulo("Salida 3: el guardia dispara y pasa a MANUAL (el caso feo)")
    b = FakeBroker()
    pos = seed_largo(b, "CCC", 50, 100.00, 100.20)

    def guion(t):
        if t >= 2:
            b.set_quote("CCC", 99.70, 99.90)  # el bid se escapa para abajo

    cfg = _cfg(
        exit_levels=[ExitLevel(0.02, OffsetUnit.DOLLARS, 10)],
        guard=GuardConfig(0.25, GuardUnit.DOLLARS, GuardAction.MANUAL),
    )
    out = BotEngine(b, cfg, clock=FakeClock(guion)).manage_exit(pos)
    print("Outcome:", out.value, "| posiciones:", b.get_positions(), "(sigue ABIERTA)")


def s4_guardia_forzado() -> None:
    titulo("Salida 4: el guardia con accion (B) SALIDA FORZADA")
    b = FakeBroker()
    pos = seed_largo(b, "DDD", 50, 100.00, 100.20)

    def guion(t):
        if t >= 2:
            b.set_quote("DDD", 99.70, 99.90)

    cfg = _cfg(
        exit_levels=[ExitLevel(0.02, OffsetUnit.DOLLARS, 10)],
        guard=GuardConfig(0.25, GuardUnit.DOLLARS, GuardAction.FORCE_EXIT),
    )
    out = BotEngine(b, cfg, clock=FakeClock(guion)).manage_exit(pos)
    print("Outcome:", out.value, "| posiciones:", b.get_positions(), "(salio cruzando)")


def s5_sin_salida() -> None:
    titulo("Salida 5: los 4 niveles no cierran -> MANUAL (posicion abierta)")
    b = FakeBroker()
    pos = seed_largo(b, "EEE", 50, 100.10, 100.30)  # mercado congelado
    cfg = _cfg(exit_levels=[
        ExitLevel(0.02, OffsetUnit.DOLLARS, 2),
        ExitLevel(0.10, OffsetUnit.DOLLARS, 2),
        ExitLevel(0.15, OffsetUnit.DOLLARS, 2),
        ExitLevel(0.18, OffsetUnit.DOLLARS, 2),
    ])
    out = BotEngine(b, cfg, clock=FakeClock()).manage_exit(pos)
    print("Outcome:", out.value, "| posiciones:", b.get_positions())


def s6_cruzar() -> None:
    titulo("Salida 6: un nivel con CRUZAR asegura la salida")
    b = FakeBroker()
    pos = seed_largo(b, "FFF", 50, 100.10, 100.30)
    cfg = _cfg(exit_levels=[
        ExitLevel(0.02, OffsetUnit.DOLLARS, 2),
        ExitLevel(0, OffsetUnit.DOLLARS, 2, cross=True),
    ])
    out = BotEngine(b, cfg, clock=FakeClock()).manage_exit(pos)
    print("Outcome:", out.value, "| posiciones:", b.get_positions())


def s7_flujo_completo() -> None:
    titulo("Flujo completo: entra, resuelve, y NO sigue con la watchlist")
    b = FakeBroker()
    b.set_quote("GGG", 100.00, 100.20)
    b.set_quote("HHH", 50.00, 50.10)  # este NO deberia tocarse nunca

    def guion(t):
        if t >= 1:
            b.set_quote("GGG", 100.00, 100.02)  # entra largo en GGG

    cfg = EngineConfig(
        side=Side.BUY, quantity=50,
        order1=OrderConfig(0.02, OffsetUnit.DOLLARS, 5),
        exit_levels=[ExitLevel(0, OffsetUnit.DOLLARS, 5, cross=True)],  # cierra cruzando
    )
    out = BotEngine(b, cfg, clock=FakeClock(guion)).run_episode(["GGG", "HHH"], max_cycles=1)
    print("Outcome:", out.value)
    print("Nota: 'HHH' nunca aparecio en el log -> el bot NO siguio con la watchlist.")


def main() -> None:
    s1_cierre_limpio()
    s2_escalonado()
    s3_guardia_manual()
    s4_guardia_forzado()
    s5_sin_salida()
    s6_cruzar()
    s7_flujo_completo()
    print("\nListo: la salida (Tanda 2) funciona en todos los escenarios.")


if __name__ == "__main__":
    main()
