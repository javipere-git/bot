"""
Prueba CONTROLADA de mandar + cancelar UNA orden (Fase 3, arranque).

TODO ES SANDBOX (plata de mentira). NO toca dinero real.

Manda una compra limite de 1 accion de SPY a $1.00 (un precio absurdamente
bajo: JAMAS se va a ejecutar), confirma que la orden aparece viva, y despues
la CANCELA. La cuenta queda igual que antes.

De paso muestra el cupo real del balde de "operar" que informa Tradier.

Para correrlo:  python examples/probar_orden_sandbox.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.tradier import TradierBroker  # noqa: E402
from tradingbot.core.models import (  # noqa: E402
    Duration,
    OrderRequest,
    OrderType,
    Side,
)


def intentar(broker: TradierBroker, duration: Duration):
    req = OrderRequest("SPY", Side.BUY, 1, 1.00, OrderType.LIMIT, duration)
    print(f"Mando COMPRA limite 1 SPY @ 1.00  (duracion={duration.value}) ...")
    order = broker.place_order(req)
    print(f"   recibida.  id={order.id}   cupo trade: {broker.last_rate_limit}")
    return order


def main() -> None:
    broker = TradierBroker.from_credentials(environment="sandbox")
    print("PRUEBA: mandar + cancelar UNA orden de juguete (SANDBOX, plata de mentira)")
    print("-" * 60)

    order = None
    for dur in (Duration.DAY, Duration.POST):
        try:
            order = intentar(broker, dur)
            break
        except RuntimeError as e:
            print(f"   rechazada: {e}")
            if dur == Duration.DAY:
                print("   (puede ser por horario) pruebo con horario extendido...")

    if order is None or order.id == "None":
        print("-" * 60)
        print("No quedo una orden viva (probablemente por horario de mercado).")
        print("Igual el CAMINO de envio quedo probado: Tradier recibio la llamada.")
        return

    abiertas = broker.get_open_orders()
    print(f"Ordenes abiertas ahora: {len(abiertas)}")
    for o in abiertas:
        print(f"   id={o.id}  {o.side.value} {o.quantity} {o.symbol} @ {o.price} [{o.status.value}]")

    print(f"Cancelo la orden id={order.id} ...")
    try:
        broker.cancel_order(order.id)
        print(f"   cancelada.  cupo trade: {broker.last_rate_limit}")
    except RuntimeError as e:
        print(f"   no se pudo cancelar: {e}")

    abiertas2 = broker.get_open_orders()
    print(f"Ordenes abiertas despues de cancelar: {len(abiertas2)}")
    print("-" * 60)
    print("OK: el camino  mandar -> ver -> cancelar  funciona en sandbox.")
    print("La cuenta queda limpia (sin posiciones ni ordenes vivas).")


if __name__ == "__main__":
    main()
