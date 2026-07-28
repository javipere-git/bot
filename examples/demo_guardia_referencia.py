"""
Prueba la REFERENCIA del guardia (no toca dinero: broker de mentira).

Escenario del usuario: la accion cotiza 100.00 x 101.00, el bot calcula la
entrada desde el bid 100.00 y entra long. JUSTO al entrar (no despues), el bid
se desploma a 99.50. Umbral del guardia: 0.20.

- Referencia "precio de calculo de la entrada" (nueva, default): el guardia mide
  desde 100.00 -> caida 0.50 >= 0.20 -> SALTA apenas arranca el cierre, sin
  mandar ninguna orden de salida con el mercado caido.
- Referencia "precio al iniciar el cierre" (comportamiento anterior): el guardia
  mide desde 99.50 (ya caido) -> caida 0.00 -> NO salta, y el cierre escalonado
  sigue como si nada.

    python examples/demo_guardia_referencia.py
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
    GuardReference,
    GuardUnit,
    OffsetUnit,
    OrderConfig,
)
from tradingbot.core.engine import BotEngine, Outcome  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def _config(ref: GuardReference) -> EngineConfig:
    return EngineConfig(
        side=Side.BUY,
        quantity=50,
        # offset 100% del spread = orden al ask -> se llena al instante (entra si o si)
        order1=OrderConfig(offset=100.0, unit=OffsetUnit.PERCENT_SPREAD, timeout_s=1.0),
        order2=None,
        exit_levels=[
            ExitLevel(0.05, OffsetUnit.DOLLARS, timeout_s=1.0),
            ExitLevel(0.03, OffsetUnit.DOLLARS, timeout_s=1.0),
        ],
        guard=GuardConfig(threshold=0.20, unit=GuardUnit.DOLLARS,
                          action=GuardAction.MANUAL, reference=ref),
    )


def _correr(ref: GuardReference):
    broker = FakeBroker()
    broker.set_quote("TEST", 100.00, 101.00)
    engine = BotEngine(broker, _config(ref), clock=FakeClock(),
                       log=lambda m: print("   " + m))
    pos = engine._process_symbol("TEST")   # entra long (cruzando, para la prueba)
    assert pos is not None, "la entrada de la prueba tenia que llenarse"
    # el bid se desploma JUNTO con la entrada, antes de que arranque el cierre
    broker.set_quote("TEST", 99.50, 99.70)
    outcome = engine.manage_exit(pos)
    salidas = [o for o in broker._orders.values() if o.side == Side.SELL]
    return engine, outcome, salidas


def main() -> None:
    todo_ok = True

    print("Caso A: referencia = PRECIO DE CALCULO DE LA ENTRADA (100.00)")
    print("-" * 70)
    engine, outcome, salidas = _correr(GuardReference.ENTRY_CALC)
    print("-" * 70)
    ok_a = (engine._entry_ref == 100.00 and outcome == Outcome.MANUAL_GUARD
            and len(salidas) == 0)
    todo_ok = todo_ok and ok_a
    print(f"Referencia guardada: {engine._entry_ref} (esperado 100.0)")
    print(f"Outcome: {outcome.value} (esperado manual_guard)")
    print(f"Ordenes de salida mandadas con el mercado caido: {len(salidas)} (esperado 0)")
    print("OK: el guardia VIO el golpe de la entrada y salto.\n" if ok_a
          else "*** FALLO caso A.\n")

    print("Caso B: referencia = PRECIO AL INICIAR EL CIERRE (comport. anterior)")
    print("-" * 70)
    engine, outcome, salidas = _correr(GuardReference.EXIT_START)
    print("-" * 70)
    # con la referencia ya caida (99.50) el guardia no salta y el cierre sigue
    ok_b = outcome == Outcome.MANUAL_NO_EXIT and len(salidas) == 1
    todo_ok = todo_ok and ok_b
    print(f"Outcome: {outcome.value} (esperado manual_no_exit: probo niveles sin llenar)")
    print(f"Ordenes de salida mandadas: {len(salidas)} (esperado 1: el guardia no salto)")
    print("OK: reproduce el comportamiento anterior (el golpe no se ve).\n" if ok_b
          else "*** FALLO caso B.\n")

    print("OK: la referencia del guardia funciona (y por default cubre la entrada)."
          if todo_ok else "*** HAY FALLOS.")


if __name__ == "__main__":
    main()
