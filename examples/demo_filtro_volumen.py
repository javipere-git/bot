"""
Prueba el FILTRO DE VOLUMEN del dia (no toca dinero: conector de mentira).

Arma 4 simbolos con distinto volumen operado en el dia y confirma que el bot
saltea los que quedan fuera del rango [min, max] y entra solo en los que pasan.

    python examples/demo_filtro_volumen.py
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
    VOL_MIN, VOL_MAX = 1_000, 100_000
    casos = [
        ("POCO", 500, "por DEBAJO del minimo -> saltear"),
        ("JUSTO", 1_000, "justo en el minimo -> ENTRAR"),
        ("BIEN", 50_000, "dentro del rango -> ENTRAR"),
        ("MUCHO", 200_000, "por ENCIMA del maximo -> saltear"),
    ]
    esperado_entra = {"JUSTO", "BIEN"}

    broker = FakeBroker()
    for sym, vol, _ in casos:
        broker.set_quote(sym, 100.00, 100.20, volume=vol)

    cfg = EngineConfig(
        side=Side.BUY,
        quantity=10,
        # offset 0.20 = bid + 0.20 = el ask -> se llena al instante si pasa el filtro
        order1=OrderConfig(offset=0.20, unit=OffsetUnit.DOLLARS, timeout_s=1.0),
        order2=None,
        volume_min=VOL_MIN,
        volume_max=VOL_MAX,
        loop_watchlist=False,
    )

    print(f"Filtro: volumen del dia entre {VOL_MIN:,} y {VOL_MAX:,} acciones\n")
    entraron = []
    for sym, vol, que_espero in casos:
        # un motor por simbolo: probamos el filtro de entrada aislado
        engine = BotEngine(broker, cfg, clock=FakeClock(), log=lambda m: print("   " + m))
        print(f"{sym} (volumen {vol:,}) -> {que_espero}")
        pos = engine._process_symbol(sym)
        if pos is not None:
            entraron.append(sym)
            broker._positions.pop(sym, None)  # dejar la cuenta plana para el proximo
        print()

    ok = set(entraron) == esperado_entra
    print(f"Entro en: {entraron or 'ninguno'}   (esperado: {sorted(esperado_entra)})")
    print("OK: el filtro de volumen funciona." if ok else "*** FALLO: el filtro no filtro bien.")


if __name__ == "__main__":
    main()
