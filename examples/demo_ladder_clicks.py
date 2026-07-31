"""
Ladder: mandar ordenes al estilo ThinkorSwim + botones de cantidad configurables.

EL PROBLEMA que resuelve: antes, mandar y cancelar se hacian en la MISMA celda
(columnas Compra/Venta). Era facil equivocarse: darle a la X queriendo mandar otra
orden, mandar una queriendo cancelar, o soltar el mouse sin llegar a arrastrar y
terminar mandando una orden nueva.

AHORA (como ThinkorSwim):
  - MANDAR: click en la columna BID (compra) o ASK (venta).
  - CANCELAR: click en tu orden, que sigue dibujada en Compra/Venta.
  - MOVER: arrastrar la orden, igual que antes.

Ademas, los 4 botones de cantidad se configuran con la rueda y se recuerdan.

    python examples/demo_ladder_clicks.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.gui.estado_ui import (  # noqa: E402
    cantidades_botones,
    guardar_cantidades_botones,
)
from tradingbot.gui.ladder_panel import (  # noqa: E402
    C_ASK,
    C_BID,
    C_BUY,
    C_SELL,
    LadderPanel,
)
from tradingbot.core.models import Side  # noqa: E402


def _fila_de_precio(ladder, precio):
    for i in range(ladder.tabla.rowCount()):
        if abs((ladder._precio_de_fila(i) or -1) - precio) < 0.0001:
            return i
    return None


def main() -> None:
    app = QApplication(sys.argv)
    broker = FakeBroker()
    broker.set_quote("AAPL", bid=100.00, ask=100.10)
    ladder = LadderPanel(broker_provider=lambda: broker, log=lambda m: None)
    ladder.ed_symbol.setText("AAPL")
    ladder._cambiar_symbol()
    ladder.actualizar_quote("AAPL", 100.00, 100.10, 500, 400)
    ladder._repintar()
    ladder.spin_size.setValue(10)

    print("1) Click en BID = manda COMPRA")
    fila = _fila_de_precio(ladder, 99.95)
    ladder._click_celda(fila, C_BID)
    abiertas = broker.get_open_orders()
    ok1 = len(abiertas) == 1 and abiertas[0].side == Side.BUY and abiertas[0].price == 99.95
    print(f"   ordenes: {len(abiertas)}"
          + (f" -> {abiertas[0].side.value} @ {abiertas[0].price}" if abiertas else ""))
    print(f"   -> {'OK' if ok1 else '*** FALLO'}\n")

    print("2) Click en ASK = manda VENTA")
    fila = _fila_de_precio(ladder, 100.20)
    ladder._click_celda(fila, C_ASK)
    ventas = [o for o in broker.get_open_orders() if o.side == Side.SELL]
    ok2 = len(ventas) == 1 and ventas[0].price == 100.20
    print(f"   ordenes de venta: {len(ventas)}"
          + (f" @ {ventas[0].price}" if ventas else ""))
    print(f"   -> {'OK' if ok2 else '*** FALLO'}\n")

    print("3) Click en Compra/Venta VACIA ya NO manda nada (antes si)")
    antes = len(broker.get_open_orders())
    fila = _fila_de_precio(ladder, 99.90)
    ladder._click_celda(fila, C_BUY)
    ladder._click_celda(fila, C_SELL)
    despues = len(broker.get_open_orders())
    ok3 = antes == despues
    print(f"   ordenes antes {antes}, despues {despues} (esperado iguales)")
    print(f"   -> {'OK: esas columnas solo cancelan' if ok3 else '*** FALLO'}\n")

    print("4) Click en TU ORDEN la cancela")
    ladder.set_orders(broker.get_open_orders())
    ladder._repintar()
    fila = _fila_de_precio(ladder, 99.95)
    ladder._click_celda(fila, C_BUY)          # ahi esta dibujada la compra
    quedan = broker.get_open_orders()
    ok4 = all(o.price != 99.95 for o in quedan)
    print(f"   quedan {len(quedan)} ordenes; la de 99.95 se cancelo: {ok4}")
    print(f"   -> {'OK' if ok4 else '*** FALLO'}\n")

    print("5) Botones de cantidad configurables y con memoria")
    originales = cantidades_botones()
    guardar_cantidades_botones([5, 15, 200, 500])
    l2 = LadderPanel(broker_provider=lambda: broker, log=lambda m: None)
    textos = [b.text() for b in l2._botones_size]
    l2._botones_size[3].click()
    ok5 = textos == ["5", "15", "200", "500"] and l2.spin_size.value() == 500
    print(f"   botones al reabrir: {textos}")
    print(f"   click en el ultimo -> cantidad {l2.spin_size.value()}")
    print(f"   -> {'OK' if ok5 else '*** FALLO'}")
    guardar_cantidades_botones(originales)     # dejar como estaba
    print(f"   (restaurados a {cantidades_botones()})\n")

    print("6) Mover una orden respeta su DURACION (horario extendido)")
    # Bug real: al mover una orden de post-market, se mandaba duration=day y Tradier
    # la rechazaba con "pre and post market orders cannot modify duration".
    from tradingbot.core.models import Duration

    class BrokerEspia(FakeBroker):
        """Anota con que duracion se pidio la modificacion."""
        def __init__(self):
            super().__init__()
            self.duraciones = []

        def modify_order(self, order_id, *, price=None, quantity=None, duration=None):
            self.duraciones.append(duration)
            return super().modify_order(order_id, price=price, quantity=quantity)

    espia = BrokerEspia()
    espia.set_quote("AAPL", bid=100.00, ask=100.10)
    l3 = LadderPanel(broker_provider=lambda: espia, log=lambda m: None)
    l3.ed_symbol.setText("AAPL")
    l3._cambiar_symbol()
    l3.actualizar_quote("AAPL", 100.00, 100.10, 500, 400)
    l3._repintar()
    l3.chk_ext.setChecked(True)               # orden de horario extendido
    fila = _fila_de_precio(l3, 99.95)
    l3._click_celda(fila, C_BID)
    orden = espia.get_open_orders()[0]
    orden.duration = Duration.POST            # como la reporta el broker en post-market
    l3.set_orders(espia.get_open_orders())
    l3._repintar()
    destino = _fila_de_precio(l3, 99.90)
    l3._mover_orden([orden.id], destino)
    ok6 = espia.duraciones == [Duration.POST]
    print(f"   la orden es POST; al moverla se mando duracion: {espia.duraciones}")
    print(f"   -> {'OK: respeta la duracion (antes mandaba day y fallaba)' if ok6 else '*** FALLO'}\n")

    todo = ok1 and ok2 and ok3 and ok4 and ok5 and ok6
    print("OK: mandar por bid/ask, cancelar en tu orden, botones configurables."
          if todo else "*** HAY FALLOS.")


if __name__ == "__main__":
    main()
