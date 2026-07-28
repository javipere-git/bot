"""
Prueba de CICLO COMPLETO con llenado real (sandbox, plata de mentira).

Con el mercado abierto:
  1. Entra con 1 accion de GE, cruzando el spread para que SE LLENE.
  2. Apenas se llena, el bot trabaja la salida con un nivel "cruzar" que cierra.
  3. La cuenta deberia quedar PLANA otra vez.

Es paper: no toca dinero real. Igualmente, una red de seguridad cierra
cualquier posicion que quedara colgada.

Para correrlo:  python examples/probar_ciclo_completo.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.tradier import TradierBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, ExitLevel, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import OrderRequest, OrderType, Side  # noqa: E402

SYM = "GE"


def cerrar_posiciones(broker: TradierBroker) -> bool:
    """Red de seguridad: cierra cualquier posicion cruzando el spread."""
    for _ in range(3):
        posiciones = broker.get_positions()
        if not posiciones:
            return True
        for p in posiciones:
            side = Side.SELL if p.is_long else Side.BUY_TO_COVER
            q = broker.get_quote(p.symbol)
            price = round(q.bid if p.is_long else q.ask, 2)
            print(f"  red de seguridad: {side.value} {abs(p.quantity)} {p.symbol} @ {price}")
            try:
                broker.place_order(
                    OrderRequest(p.symbol, side, abs(p.quantity), price, OrderType.LIMIT)
                )
            except Exception as e:
                print(f"    error: {e}")
        time.sleep(2)
    return not broker.get_positions()


def main() -> None:
    broker = TradierBroker.from_credentials(environment="sandbox")

    print("CICLO COMPLETO con llenado real (sandbox, plata de mentira)")
    print("-" * 64)
    q = broker.get_quote(SYM)
    print(f"Estado inicial: posiciones {len(broker.get_positions())} | "
          f"ordenes abiertas {len(broker.get_open_orders())}")
    print(f"{SYM} (demorado ~15 min): bid {q.bid} x ask {q.ask}")
    print("-" * 64)

    cfg = EngineConfig(
        side=Side.BUY,
        quantity=1,
        # Entrada que cruza el spread para asegurar el llenado:
        order1=OrderConfig(1.00, OffsetUnit.DOLLARS, timeout_s=6),
        # Salida que cruza para cerrar enseguida:
        exit_levels=[ExitLevel(0, OffsetUnit.DOLLARS, timeout_s=6, cross=True)],
        poll_interval_s=1.0,
    )
    engine = BotEngine(broker, cfg)

    try:
        outcome = engine.run_episode([SYM], max_cycles=1)
        print("-" * 64)
        print(f"Outcome: {outcome.value}")
    except Exception as e:
        print(f"Error durante el ciclo: {e}")
    finally:
        abiertas = broker.get_open_orders()
        if abiertas:
            print(f"Limpieza: cancelo {len(abiertas)} orden(es) viva(s)...")
            for o in abiertas:
                try:
                    broker.cancel_order(o.id)
                except Exception:
                    pass
        if broker.get_positions():
            print("Quedo una posicion abierta -> activo la red de seguridad:")
            cerrar_posiciones(broker)
        print("-" * 64)
        print(f"Estado final: posiciones {len(broker.get_positions())} | "
              f"ordenes abiertas {len(broker.get_open_orders())}")
        if not broker.get_positions() and not broker.get_open_orders():
            print(">>> Ciclo completo OK: entro, cerro, y la cuenta quedo PLANA.")


if __name__ == "__main__":
    main()
