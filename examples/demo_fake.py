"""
Demo del conector de mentira (Fase 1).

Recrea el ejemplo que charlamos: entramos largos en XYZ y despues salimos.
No toca ningun broker ni dinero: todo es simulado y en memoria.

Para correrlo:  python examples/demo_fake.py
"""
from __future__ import annotations

import os
import sys

# Permite ejecutar este archivo directamente, sin instalar el paquete.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.models import OrderRequest, Side  # noqa: E402


def main() -> None:
    broker = FakeBroker()

    # Cada vez que algo se ejecuta, lo avisamos por pantalla.
    broker.subscribe_account(
        lambda f: print(
            f"   >> EJECUCION: {f.side.value} {f.quantity} {f.symbol} "
            f"@ {f.price:.2f}"
        )
    )

    print(f"Cuenta (simulada): {broker.get_account_id()}")
    print("-" * 60)

    # 1) Cotizacion inicial: 100.00 x 100.20
    print("XYZ cotiza  100.00 (bid)  x  100.20 (ask)")
    broker.set_quote("XYZ", bid=100.00, ask=100.20)

    # 2) Entramos: compra limite 50 @ 100.02 (bid + 0.02)
    print("Mando COMPRA limite 50 @ 100.02 ...")
    entry = broker.place_order(OrderRequest("XYZ", Side.BUY, 50, 100.02))
    print(f"   estado: {entry.status.value}  (esperando, todavia no se lleno)")
    print("-" * 60)

    # 3) El mercado baja y el ask toca mi precio -> me llena
    print("El ask baja a 100.02  ->  deberia llenarse mi compra")
    broker.set_quote("XYZ", bid=99.95, ask=100.02)
    pos = broker.get_positions()[0]
    print(f"   posicion REAL: {pos.quantity} XYZ @ {pos.avg_price:.2f}")
    print("-" * 60)

    # 4) Salida: la cantidad sale de la POSICION REAL, no de lo seteado.
    #    (Asi un llenado parcial no rompe nada.)
    qty = abs(pos.quantity)
    print(f"Mando VENTA limite {qty} @ 100.15 (salida sobre la posicion real)")
    exit_order = broker.place_order(OrderRequest("XYZ", Side.SELL, qty, 100.15))
    print(f"   estado: {exit_order.status.value}")
    print("-" * 60)

    # 5) El mercado sube y el bid toca mi salida -> me llena
    print("El bid sube a 100.15  ->  deberia llenarse mi venta")
    broker.set_quote("XYZ", bid=100.15, ask=100.20)
    abiertas = broker.get_positions()
    print(f"   posiciones abiertas ahora: {abiertas}  (vacio = quedamos planos)")
    print("-" * 60)
    print("OK: el conector de mentira funciona.")
    print("El cerebro le va a hablar EXACTAMENTE igual a Tradier.")


if __name__ == "__main__":
    main()
