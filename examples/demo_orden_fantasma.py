"""
Demo de robustez: la 'orden fantasma' (carrera cancelar/llenarse).

Usa un broker trucado donde la orden SE LLENA en el instante exacto en que el
bot la cancela. Antes, el bot creia que la habia cancelado y seguia de largo,
dejando una posicion abierta sin manejar. Ahora debe DETECTAR el llenado,
tomarlo como entrada y trabajar la salida.

Para correrlo:  python examples/demo_orden_fantasma.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, ExitLevel, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import OrderStatus, Side  # noqa: E402


class BrokerFantasma(FakeBroker):
    """Al recibir la cancelacion, la orden en realidad YA se habia llenado."""

    def cancel_order(self, order_id: str) -> None:
        o = self._orders[order_id]
        if o.is_active:
            qty = o.remaining_quantity
            o.filled_quantity = o.quantity
            o.avg_fill_price = o.price
            o.status = OrderStatus.FILLED
            self._apply_to_position(o, qty, o.price)
            # (no se cancela: se lleno primero; el broker ignora la cancelacion)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def main() -> None:
    broker = BrokerFantasma()
    broker.set_quote("AAA", 100.00, 100.20)

    cfg = EngineConfig(
        side=Side.BUY, quantity=10,
        # Orden 1 al bid (no se llena sola); sin Orden 2 -> al vencer, cancela.
        order1=OrderConfig(0.0, OffsetUnit.DOLLARS, 2),
        # Salida: un nivel que cruza (en el fake, vender al bid llena al instante).
        exit_levels=[ExitLevel(0, OffsetUnit.DOLLARS, 2, cross=True)],
        pause_on_fill=False,
        loop_watchlist=False,
    )
    eng = BotEngine(broker, cfg, clock=FakeClock())

    print("La orden se llena JUSTO cuando el bot la cancela (orden fantasma):")
    print("-" * 60)
    outcome = eng.run_watchlist(["AAA"])
    print("-" * 60)
    print("Outcome:", outcome.value)
    print("Posiciones al final:", broker.get_positions(), "(vacio = manejo y cerro la posicion)")
    if outcome.value == "no_entry" and not broker.get_positions():
        print("OK: detecto la orden fantasma, tomo la entrada y cerro la posicion.")
    else:
        print("FALLO: revisar (posicion sin manejar o outcome inesperado).")


if __name__ == "__main__":
    main()
