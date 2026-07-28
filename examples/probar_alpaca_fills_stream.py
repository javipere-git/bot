"""
Prueba que el bot ya NO agota el limite de llamadas de Alpaca: el estado de las
ordenes se lee del stream de avisos (cache), no preguntando por REST.

Contra la cuenta PAPER (dinero simulado). Cuenta cuantas llamadas REST de verdad
salen al consultar el estado de una orden muchas veces (como hace el bot en la
espera de llenado).

    python examples/probar_alpaca_fills_stream.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors import alpaca as alpaca_mod  # noqa: E402
from tradingbot.connectors.alpaca import AlpacaBroker, detener_streams_de_cuenta  # noqa: E402
from tradingbot.core.models import OrderRequest, OrderType, Side  # noqa: E402


def main() -> None:
    b = AlpacaBroker.from_credentials(environment="paper")

    # contar cuantas llamadas REST a /v2/orders/{id} salen de verdad
    llamadas_rest = {"n": 0}
    orig_get = b._get

    def get_contando(path, *a, **k):
        if path.startswith("/v2/orders/"):
            llamadas_rest["n"] += 1
        return orig_get(path, *a, **k)

    b._get = get_contando

    print("esperando a que conecte el stream de avisos...")
    for _ in range(20):
        time.sleep(0.5)
        if b._hub is not None and b._hub.vivo():
            break
    print(f"stream de avisos conectado: {b._hub is not None and b._hub.vivo()}\n")

    # mando una orden limite lejos (queda viva) y el stream nos avisa de su estado
    o = b.place_order(OrderRequest("AAPL", Side.BUY, 1, 50.00, OrderType.LIMIT))
    print(f"orden mandada: {o.id[:8]}... esperando el aviso del stream...")
    for _ in range(10):
        time.sleep(0.5)
        if b._hub.get_order(o.id) is not None:
            break

    # ahora consulto su estado 30 veces, como en la espera de llenado del bot
    print("\nconsulto el estado de la orden 30 veces (como el polling del bot):")
    estados = set()
    for _ in range(30):
        estados.add(b.get_order(o.id).status.value)
        time.sleep(0.05)
    print(f"   estado leido: {estados}")
    print(f"   *** llamadas REST que salieron de verdad: {llamadas_rest['n']} ***")
    print(f"   (antes serian 30; con el stream deberian ser 0)")

    # verifico el fallback: una orden que el stream NO vio -> cae a REST
    print("\nprueba de seguridad (fallback): consulto una orden que el stream no vio:")
    antes = llamadas_rest["n"]
    try:
        b.get_order(o.id[:-4] + "0000")   # id inexistente
    except Exception:
        pass
    print(f"   llamadas REST usadas en el fallback: {llamadas_rest['n'] - antes}  "
          f"(esperado 1: cayo a REST, seguro)")

    # limpieza
    try:
        b.cancel_order(o.id)
    except Exception:
        pass
    detener_streams_de_cuenta()

    ok = llamadas_rest["n"] == 1  # las 30 consultas: 0 REST; el fallback: 1
    print("\nOK: el estado de las ordenes se lee del stream; el bot ya no agota el "
          "limite. Y si el stream no tiene el dato, cae a REST (seguro)."
          if ok else "\n*** REVISAR: el conteo de llamadas no dio lo esperado.")


if __name__ == "__main__":
    main()
