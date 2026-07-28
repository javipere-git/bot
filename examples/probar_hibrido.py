"""
Prueba del broker HIBRIDO: opera en Alpaca (paper) pero toma los precios de
Tradier (NBBO real). No toca dinero real (la operativa es la cuenta paper).

Confirma que:
  - get_quote sale de Tradier (mismo bid/ask que Tradier directo, NO el de Alpaca IEX)
  - la operativa (cuenta, mandar, cancelar) va a Alpaca paper

    python examples/probar_hibrido.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.alpaca import AlpacaBroker  # noqa: E402
from tradingbot.connectors.hibrido import BrokerHibrido  # noqa: E402
from tradingbot.connectors.tradier import TradierBroker  # noqa: E402
from tradingbot.core.models import OrderRequest, OrderType, Side  # noqa: E402


def main() -> None:
    alpaca = AlpacaBroker.from_credentials(environment="paper")
    tradier = TradierBroker.from_credentials(environment="production")
    hib = BrokerHibrido(operativa=alpaca, datos=tradier)

    print("== La operativa es Alpaca (paper) ==")
    print(f"cuenta que reporta el hibrido: {hib.get_account_id()}")
    print(f"   (Alpaca directo:            {alpaca.get_account_id()})")

    print("\n== Los precios salen de Tradier, NO del IEX de Alpaca ==")
    for s in ("MU", "CRDO", "AAPL"):
        qh = hib.get_quote(s)
        qt = tradier.get_quote(s)
        qa = alpaca.get_quote(s)
        igual_tradier = abs(qh.bid - qt.bid) < 0.005 and abs(qh.ask - qt.ask) < 0.005
        print(f"{s:6}: hibrido {qh.bid:8.2f} x {qh.ask:8.2f}  | "
              f"Tradier {qt.bid:8.2f} x {qt.ask:8.2f}  | "
              f"Alpaca IEX {qa.bid:8.2f} x {qa.ask:8.2f}  -> "
              f"{'usa Tradier OK' if igual_tradier else '*** NO coincide con Tradier'}")

    print("\n== La orden se ejecuta en Alpaca paper (mandar -> cancelar) ==")
    precio = round((hib.get_quote('SPY').bid or 100.0) * 0.5, 2)
    o = hib.place_order(OrderRequest("SPY", Side.BUY, 1, precio, OrderType.LIMIT))
    print(f"mandada en Alpaca: id {o.id} @ {precio:.2f}")
    time.sleep(1.0)
    en_alpaca = any(x.id == o.id for x in alpaca.get_orders())
    print(f"aparece en la cuenta de Alpaca: {en_alpaca}")
    hib.cancel_order(o.id)
    time.sleep(1.0)
    final = hib.get_order(o.id)
    print(f"estado final: {final.status.value}  activa={final.is_active}")

    vivas = [x for x in alpaca.get_orders() if x.is_active]
    print(f"\nordenes vivas tras la prueba: {len(vivas)}")
    print("\nOK: opera en Alpaca, precios de Tradier."
          if en_alpaca and not final.is_active and not vivas
          else "*** REVISAR: algo no cerro bien.")


if __name__ == "__main__":
    main()
