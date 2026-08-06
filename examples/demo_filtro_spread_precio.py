"""
Prueba el FILTRO DE SPREAD CONTRA EL PRECIO (no toca dinero: conector de mentira).

La idea: un spread de 0.10 es angosto en una accion de 200 y carisimo en una de 1.00.
Este filtro mide el spread como PORCENTAJE del precio (el punto medio entre bid y ask)
y saltea las acciones donde ese porcentaje llega al tope.

OJO con el borde: saltea si es IGUAL O MAYOR al tope (asi se pidio), no mayor estricto.

    python examples/demo_filtro_spread_precio.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402


class FakeClock:
    """Reloj falso: no espera de verdad (el test corre al instante)."""

    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def main() -> None:
    TOPE = 5.0          # spread >= 5% del precio -> saltear
    casos = [
        # (simbolo, bid, ask, que esperamos)
        ("CARA",    199.90, 200.10, "0.20 sobre 200.00 = 0.10% -> ENTRAR"),
        ("NORMAL",   10.00,  10.20, "0.20 sobre 10.10 = 1.98% -> ENTRAR"),
        ("JUSTO",     9.75,  10.25, "0.50 sobre 10.00 = 5.00% EXACTO -> saltear"),
        ("CASI",      9.80,  10.20, "0.40 sobre 10.00 = 4.00% -> ENTRAR"),
        ("ILIQUIDA",  1.00,   1.20, "0.20 sobre 1.10 = 18.18% -> saltear"),
    ]
    esperado_entra = {"CARA", "NORMAL", "CASI"}

    broker = FakeBroker()
    for sym, bid, ask, _ in casos:
        broker.set_quote(sym, bid, ask, volume=50_000)

    print(f"Filtro: saltear si el spread es {TOPE:g}% o MAS del precio\n")
    entraron = []
    for sym, bid, ask, que_espero in casos:
        # la orden se manda al ask para que se llene al instante si pasa el filtro
        cfg = EngineConfig(
            side=Side.BUY,
            quantity=10,
            order1=OrderConfig(offset=round(ask - bid, 4), unit=OffsetUnit.DOLLARS,
                               timeout_s=1.0),
            order2=None,
            max_spread_pct_precio=TOPE,
            loop_watchlist=False,
        )
        engine = BotEngine(broker, cfg, clock=FakeClock(), log=lambda m: print("   " + m))
        print(f"{sym} ({bid:.2f} x {ask:.2f}) -> {que_espero}")
        pos = engine._process_symbol(sym)
        if pos is not None:
            entraron.append(sym)
            broker._positions.pop(sym, None)  # dejar la cuenta plana para el proximo
        print()

    ok = set(entraron) == esperado_entra
    print(f"Entro en: {entraron or 'ninguno'}   (esperado: {sorted(esperado_entra)})")
    print("OK: el filtro de spread contra precio funciona." if ok
          else "*** FALLO: el filtro no filtro bien.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
