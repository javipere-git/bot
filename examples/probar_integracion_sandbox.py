"""
Prueba de INTEGRACION: el cerebro manejando el conector REAL de Tradier.

Todo es SANDBOX (plata de mentira). Con el mercado cerrado los precios estan
congelados, asi que nada se va a llenar; ademas, a proposito colocamos las
ordenes por DEBAJO del mercado (offset negativo) para que NO se ejecuten.
Es una prueba del RECORRIDO (mandar -> modificar -> cancelar), no de un llenado.

La prueba limpia sola cualquier orden que quede viva.

Para correrlo:  python examples/probar_integracion_sandbox.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.tradier import TradierBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402


def main() -> None:
    broker = TradierBroker.from_credentials(environment="sandbox")
    symbols = ["SPY"]

    print("INTEGRACION: cerebro + Tradier REAL (sandbox, plata de mentira)")
    print("-" * 60)
    print("Estado inicial:")
    print(f"  posiciones: {len(broker.get_positions())} | "
          f"ordenes abiertas: {len(broker.get_open_orders())}")
    q = broker.get_quote("SPY")
    print(f"  SPY (demorado ~15 min): bid {q.bid} x ask {q.ask}")
    print("-" * 60)

    # Offsets NEGATIVOS a proposito: las ordenes quedan por debajo del mercado
    # y no se pueden llenar. Probamos el recorrido, no un llenado.
    cfg = EngineConfig(
        side=Side.BUY,
        quantity=1,
        order1=OrderConfig(-0.50, OffsetUnit.DOLLARS, timeout_s=4),
        order2=OrderConfig(-1.00, OffsetUnit.DOLLARS, timeout_s=4),
        poll_interval_s=2.0,
    )
    engine = BotEngine(broker, cfg)

    try:
        resultado = engine.scan_and_enter(symbols, max_cycles=1)
        print("-" * 60)
        print(f"Resultado entrada: {resultado}  (None = no entro, como esperabamos)")
    except Exception as e:
        print("-" * 60)
        print(f"Hubo un error durante el recorrido: {e}")
    finally:
        # Limpieza: cancelar cualquier orden que haya quedado viva.
        abiertas = broker.get_open_orders()
        if abiertas:
            print(f"Limpieza: cancelo {len(abiertas)} orden(es) que quedaron vivas...")
            for o in abiertas:
                try:
                    broker.cancel_order(o.id)
                except Exception:
                    pass
        print("Estado final:")
        print(f"  posiciones: {len(broker.get_positions())} | "
              f"ordenes abiertas: {len(broker.get_open_orders())}")
        print("-" * 60)
        print("OK: el cerebro maneja el conector REAL de Tradier de punta a punta.")


if __name__ == "__main__":
    main()
