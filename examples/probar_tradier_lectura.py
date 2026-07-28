"""
Prueba del conector real de Tradier (Fase 2 - SOLO LECTURA).

Se conecta a tu cuenta SANDBOX y solo MIRA: numero de cuenta, posiciones,
ordenes abiertas y la cotizacion de un simbolo. NO manda, modifica ni cancela
nada. No toca dinero (es paper).

Para correrlo:  python examples/probar_tradier_lectura.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.tradier import TradierBroker  # noqa: E402


def main() -> None:
    broker = TradierBroker.from_credentials(environment="sandbox")

    print("Conector de Tradier (SANDBOX, solo lectura)")
    print("-" * 60)
    print(f"Numero de cuenta: {broker.get_account_id()}")

    posiciones = broker.get_positions()
    print(f"Posiciones abiertas: {len(posiciones)}")
    for p in posiciones:
        lado = "LARGO" if p.is_long else "CORTO"
        print(f"   {lado}  {p.quantity} {p.symbol} @ {p.avg_price}")

    ordenes = broker.get_open_orders()
    print(f"Ordenes abiertas: {len(ordenes)}")
    for o in ordenes:
        print(f"   {o.side.value} {o.quantity} {o.symbol} @ {o.price} [{o.status.value}]")

    print("-" * 60)
    simbolo = "SPY"
    q = broker.get_quote(simbolo)
    print(f"Cotizacion {simbolo} (demorada ~15 min en sandbox):")
    print(f"   bid {q.bid}  x  ask {q.ask}   (spread {q.spread})")
    print(f"   tamano  bid {q.bid_size}  /  ask {q.ask_size}")
    print("-" * 60)
    print("OK: el conector real de Tradier lee la cuenta sandbox correctamente.")
    print("Habla EXACTAMENTE igual que el conector de mentira: el cerebro no nota la diferencia.")


if __name__ == "__main__":
    main()
