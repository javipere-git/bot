"""
Prueba de integracion del conector de Alpaca contra la cuenta PAPER real
(dinero simulado). Lee cuenta/posiciones/ordenes, cotiza, y hace el ciclo
completo de una orden: mandar -> leer -> modificar -> cancelar -> verificar.

    python examples/probar_alpaca.py

NO toca dinero real: la cuenta paper de Alpaca es 100% simulada.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.alpaca import AlpacaBroker  # noqa: E402
from tradingbot.core.models import OrderRequest, OrderType, Side  # noqa: E402


def main() -> None:
    b = AlpacaBroker.from_credentials()
    print("== Conexion ==")
    print(f"cuenta paper: {b.get_account_id()}")

    print("\n== Lectura ==")
    print(f"posiciones abiertas: {len(b.get_positions())}")
    print(f"ordenes del dia: {len(b.get_orders())}")

    print("\n== Cotizacion (SPY) ==")
    q = b.get_quote("SPY")
    print(f"bid {q.bid}  ask {q.ask}  bidsz {q.bid_size}  asksz {q.ask_size}"
          f"  volumen dia {q.volume:,}")
    if q.bid <= 0:
        print("(sin cotizacion en vivo -uso un precio fijo para la prueba de orden)")

    print("\n== Ciclo de una orden (limite lejos del mercado, NO se llena) ==")
    # compra muy por debajo del mercado: queda descansando, no se ejecuta
    precio = round((q.bid or 100.0) * 0.5, 2)
    req = OrderRequest("SPY", Side.BUY, 1, precio, OrderType.LIMIT)
    o = b.place_order(req)
    print(f"1) mandada: id {o.id} @ {precio:.2f}")
    time.sleep(1.0)

    leida = b.get_order(o.id)
    print(f"2) leida:   {leida.symbol} {leida.side.value} {leida.quantity} "
          f"@ {leida.price:.2f}  estado {leida.status.value}  activa={leida.is_active}")

    nuevo_precio = round(precio + 0.10, 2)
    try:
        mod = b.modify_order(o.id, price=nuevo_precio)
        print(f"3) modificada a {nuevo_precio:.2f} (Alpaca da id nuevo: {mod.id})")
        id_para_cancelar = mod.id or o.id
    except Exception as e:  # noqa: BLE001
        print(f"3) no se pudo modificar ({e}) -cancelo la original")
        id_para_cancelar = o.id
    time.sleep(1.0)

    b.cancel_order(id_para_cancelar)
    print(f"4) cancelada (id {id_para_cancelar})")
    time.sleep(1.0)

    final = b.get_order(id_para_cancelar)
    ok = not final.is_active
    print(f"5) estado final: {final.status.value}  activa={final.is_active}")

    # confirmar que no quedo ninguna orden viva ni posicion de la prueba
    vivas = [x for x in b.get_orders() if x.is_active]
    print(f"\nordenes vivas tras la prueba: {len(vivas)}")
    print(f"posiciones tras la prueba: {len(b.get_positions())}")
    print("\nOK: el conector de Alpaca funciona (mandar/leer/modificar/cancelar)."
          if ok and not vivas else "*** REVISAR: quedo algo vivo, mirar arriba.")


if __name__ == "__main__":
    main()
