"""
Verifica el fix de la 'carrera' de llenado en el repricio.

Reproduce el caso real: la Orden 1 se llena JUSTO cuando el bot la iba a
repreciar. El bot debe DETECTAR el llenado (no mandar una orden nueva por error
ni dejar la posicion sin trabajar).

Para correrlo:  python examples/demo_carrera_llenado.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import OrderRequest, OrderType, Side  # noqa: E402


def main() -> None:
    broker = FakeBroker()
    broker.set_quote("AAA", 100.00, 100.20)

    # Orden 1 descansando a 100.02 (no se llena con el ask en 100.20)
    order = broker.place_order(OrderRequest("AAA", Side.BUY, 10, 100.02, OrderType.LIMIT))
    print("Orden 1 estado:", broker.get_order(order.id).status.value)

    # Se llena: el ask baja a 100.02 (simula el llenado justo antes del repricio)
    broker.set_quote("AAA", 99.98, 100.02)
    print("Tras moverse el mercado, Orden 1 estado:", broker.get_order(order.id).status.value)
    print("-" * 55)

    cfg = EngineConfig(side=Side.BUY, quantity=10,
                       order1=OrderConfig(0.02, OffsetUnit.DOLLARS, 1))
    eng = BotEngine(broker, cfg)

    # El bot va a repreciar (creyendo que no se lleno) -> debe DETECTAR el llenado
    nueva, filled = eng._reprice(order, "AAA", 100.10)
    print("reprice detecto el llenado:", filled)
    print("ordenes abiertas (deberia ser 0):", len(broker.get_open_orders()))
    print("posicion:", broker.get_positions())
    print("-" * 55)
    if filled and not broker.get_open_orders() and broker.get_positions():
        print("OK: detecto el llenado, NO creo orden fantasma, y la posicion esta.")
    else:
        print("FALLO: revisar.")


if __name__ == "__main__":
    main()
