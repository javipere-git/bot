"""
Prueba del streaming de market data en vivo (produccion, SOLO LECTURA de precios).

Conecta al WebSocket de Tradier y escucha las cotizaciones de SPY por unos
segundos. NO toca dinero ni la cuenta: es solo lectura de precios en tiempo real.

Para correrlo:  python examples/probar_streaming.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.tradier_stream import TradierMarketStream  # noqa: E402


def main() -> None:
    stream = TradierMarketStream.from_credentials()
    recibidos = [0]

    def on_quote(sym, bid, ask, bidsz, asksz):
        recibidos[0] += 1
        if recibidos[0] <= 12:
            print(f"  {sym}  bid {bid} x ask {ask}   ({int(bidsz)}/{int(asksz)})")

    print("Conectando al streaming de SPY (produccion, SOLO lectura)... escucho 8s")
    print("-" * 60)
    stream.start(["SPY"], on_quote)
    time.sleep(8)
    stream.stop()
    print("-" * 60)
    print(f"Recibidos {recibidos[0]} updates en 8 segundos.")
    if recibidos[0] > 0:
        print("OK: el streaming en vivo funciona.")
    else:
        print("No llegaron updates (puede ser por baja actividad o mercado cerrado).")


if __name__ == "__main__":
    main()
