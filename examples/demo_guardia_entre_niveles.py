"""
Prueba el GUARDIA en el cambio de nivel de salida (no toca dinero: broker de mentira).

Escenario del usuario: largo con baseline bid=100.00, umbral $0.20, 3 niveles de
salida. Los primeros niveles pasan sin que el guardia salte, y el bid cae a 99.60
JUSTO en el instante del cambio de nivel (vencio el timeout del nivel anterior y
el bot esta por repreciar al siguiente).

Lo correcto: el guardia salta ANTES de mandar/repreciar ese nivel, o sea que la
orden NO se reprecia con el mercado ya caido.

Caso A (accion = pasar a manual): no debe haber NINGUN reprecio y termina MANUAL_GUARD.
Caso B (accion = salida forzada): cruza el spread al instante y cierra (CLOSED).

    python examples/demo_guardia_entre_niveles.py
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
from tradingbot.core.engine import BotEngine, Outcome  # noqa: E402
from tradingbot.core.models import Position, Quote, Side  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


class BrokerConCaida(FakeBroker):
    """La cotizacion arranca 100.00 x 100.20 y, tras las primeras 5 lecturas
    (baseline + nivel 1 + las esperas del nivel 1), cae a 99.60 x 99.80: la
    caida ocurre EXACTAMENTE en el cambio de nivel. Ademas anota cada reprecio."""

    CAIDA_DESDE_LECTURA = 6

    def __init__(self) -> None:
        super().__init__()
        self.lecturas = 0
        self.reprecios: list[float] = []

    def get_quote(self, symbol: str) -> Quote:
        self.lecturas += 1
        if self.lecturas >= self.CAIDA_DESDE_LECTURA:
            q = Quote(symbol, 99.60, 99.80)
        else:
            q = Quote(symbol, 100.00, 100.20)
        self._quotes[symbol] = q  # el simulador de llenados lee de aca
        return q

    def modify_order(self, order_id, *, price=None, quantity=None):
        if price is not None:
            self.reprecios.append(price)
        return super().modify_order(order_id, price=price, quantity=quantity)


def _config(accion: GuardAction) -> EngineConfig:
    return EngineConfig(
        side=Side.BUY,
        quantity=20,
        order1=OrderConfig(offset=0.0, unit=OffsetUnit.DOLLARS, timeout_s=1.0),
        exit_levels=[
            ExitLevel(0.05, OffsetUnit.DOLLARS, timeout_s=1.0),
            ExitLevel(0.03, OffsetUnit.DOLLARS, timeout_s=1.0),
            ExitLevel(0.01, OffsetUnit.DOLLARS, timeout_s=1.0),
        ],
        guard=GuardConfig(threshold=0.20, unit=GuardUnit.DOLLARS, action=accion),
    )


def _correr(accion: GuardAction) -> tuple[Outcome, BrokerConCaida]:
    broker = BrokerConCaida()
    broker._positions["TEST"] = Position("TEST", 20, 100.10)  # ya estamos largos
    engine = BotEngine(broker, _config(accion), clock=FakeClock(),
                       log=lambda m: print("   " + m))
    outcome = engine.manage_exit(Position("TEST", 20, 100.10))
    return outcome, broker


def main() -> None:
    todo_ok = True

    print("Caso A: el bid cae a 99.60 en el cambio de nivel, accion = PASAR A MANUAL")
    print("-" * 70)
    outcome, broker = _correr(GuardAction.MANUAL)
    print("-" * 70)
    ok_a = outcome == Outcome.MANUAL_GUARD and broker.reprecios == []
    todo_ok = todo_ok and ok_a
    print(f"Outcome: {outcome.value} (esperado manual_guard)")
    print(f"Reprecios enviados con el mercado caido: {broker.reprecios} (esperado ninguno)")
    print("OK: el guardia salto ANTES de repreciar el nivel.\n" if ok_a
          else "*** FALLO caso A.\n")

    print("Caso B: idem, accion = SALIDA FORZADA")
    print("-" * 70)
    outcome, broker = _correr(GuardAction.FORCE_EXIT)
    print("-" * 70)
    # el unico reprecio valido es el del cruce (al bid caido, 99.60) para salir YA
    ok_b = outcome == Outcome.CLOSED and broker.reprecios == [99.60] \
        and broker.get_positions() == []
    todo_ok = todo_ok and ok_b
    print(f"Outcome: {outcome.value} (esperado closed)")
    print(f"Reprecios: {broker.reprecios} (esperado solo el cruce a 99.60)")
    print(f"Posicion cerrada: {broker.get_positions() == []}")
    print("OK: cruzo el spread y salio al instante.\n" if ok_b else "*** FALLO caso B.\n")

    print("OK: el guardia ahora tambien revisa ANTES de mandar cada nivel."
          if todo_ok else "*** HAY FALLOS.")


if __name__ == "__main__":
    main()
