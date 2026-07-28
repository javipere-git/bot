"""
Prueba el streaming de precios de Alpaca (WebSocket) con la cuenta paper.

Se conecta, autentica, se suscribe a un simbolo y muestra las primeras
cotizaciones que llegan en vivo. Con el feed 'iex' (gratis) o 'sip' (si
contrataste Algo Trader Plus), segun data_feed en credentials.ini.

    python examples/probar_alpaca_stream.py

NO toca dinero: es solo lectura de precios.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.alpaca_stream import AlpacaMarketStream  # noqa: E402


def main() -> None:
    s = AlpacaMarketStream.from_credentials(environment="paper")
    print(f"feed: {s._feed}   url: {s._url}")
    recibidas = []

    def on_q(sym, bid, ask, bidsz, asksz):
        recibidas.append((sym, bid, ask))
        if len(recibidas) <= 8:
            print(f"  quote {sym}: bid {bid:.2f} x ask {ask:.2f}   (sz {bidsz:.0f}/{asksz:.0f})")

    print("conectando y suscribiendo a SPY...")
    s.start(["SPY"], on_q)

    conecto = False
    for i in range(12):
        time.sleep(1)
        if s.esta_conectado():
            conecto = True
        if len(recibidas) >= 8:
            break
    s.stop()

    total = len(recibidas)
    print(f"\nconecto y autentico: {conecto}")
    print(f"quotes recibidas: {total}")
    if conecto and total > 0:
        print("OK: streaming de Alpaca conecta Y trae quotes (feed con datos).")
    elif conecto:
        print("OK PARCIAL: la conexion funciona, pero no llegaron quotes.")
        print("   Con el feed 'iex' (gratis) esto es ESPERADO: IEX casi no manda")
        print("   quotes. Para el ladder hace falta el feed 'sip' (Algo Trader Plus).")
        print("   Cuando contrates, pone data_feed = sip en credentials.ini y volve a probar.")
    else:
        print("*** No conecto: revisar claves / que no haya otra conexion de datos")
        print("    abierta (el plan gratis permite UNA sola conexion a la vez).")


if __name__ == "__main__":
    main()
