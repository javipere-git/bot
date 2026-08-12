"""
Los carteles y los botones van con el NBBO REAL, aunque el feed traiga odd lots.

EL PROBLEMA QUE ARREGLA: con Tastytrade, la escalera empezo a mostrar los odd lots
(bien), pero los carteles de arriba y los botones "Comprar al ask" / "Vender al
bid" tomaban ESE precio. Un ask de 2 acciones no es el mercado: el boton decia un
precio donde casi no hay nada.

Como queda:
  - la escalera muestra el NBBO real resaltado FUERTE y, ademas, los odd lots
    dentro del spread en el tono suave (se ven, pero no se confunden con el primer
    nivel);
  - los carteles y los botones usan SIEMPRE el NBBO real (lotes redondos).

Y no se pierde nada por operar al NBBO ancho: una orden limite de compra al ask
real se lleva PRIMERO los odd lots que esten mas baratos. Nunca se paga de mas.

Con Tradier y Alpaca no cambia nada: sus feeds no traen odd lots, asi que el
streaming YA es el NBBO (se comprueba abajo).

    python examples/demo_ladder_nbbo_real.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402
from tradingbot.gui.ladder_panel import LadderPanel  # noqa: E402


def _armar(broker, con_odd_lots: bool):
    l = LadderPanel(broker_provider=lambda: broker, log=lambda m: None)
    l.ed_symbol.setText("AGYS")
    l._cambiar_symbol()
    l.set_stream_vivo(lambda: True)
    l.set_stream_odd_lots(lambda: con_odd_lots)
    return l


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    broker = FakeBroker()
    broker.set_quote("AGYS", bid=107.72, ask=108.20)
    checks = {}

    # ================= FEED CON ODD LOTS (Tastytrade) =================
    print("=== Feed CON odd lots (Tastytrade) ===")
    l = _armar(broker, con_odd_lots=True)
    l.actualizar_quote_rest("AGYS", 107.72, 108.20, 100, 200)   # NBBO real
    l.actualizar_quote("AGYS", 107.87, 108.18, 7, 2)            # streaming: odd lots
    l._repintar()

    print(f"  NBBO real (REST)      : {107.72} x {108.20}")
    print(f"  streaming (odd lots)  : {107.87} x {108.18}")
    print(f"  cartel BID            : {l.lbl_bid.text()}")
    print(f"  cartel ASK            : {l.lbl_ask.text()}")
    print(f"  boton comprar         : {l.btn_buy_ask.text()}")
    print(f"  boton vender          : {l.btn_sell_bid.text()}")

    checks["el cartel BID usa el NBBO real"] = "107.72" in l.lbl_bid.text()
    checks["el cartel ASK usa el NBBO real"] = "108.20" in l.lbl_ask.text()
    checks["el boton comprar usa el NBBO real"] = "108.20" in l.btn_buy_ask.text()
    checks["el boton vender usa el NBBO real"] = "107.72" in l.btn_sell_bid.text()

    # lo que IMPORTA de verdad: a que precio sale la orden si aprietan el boton
    mandadas = []
    l._mandar = lambda side, precio: mandadas.append((side, precio))
    l._comprar_al_ask()
    l._vender_al_bid()
    print(f"  precios que se mandarian: {[p for _, p in mandadas]}")
    checks["la COMPRA sale al ask real (no al del odd lot)"] = \
        mandadas and mandadas[0] == (Side.BUY, 108.20)
    checks["la VENTA sale al bid real (no al del odd lot)"] = \
        len(mandadas) > 1 and mandadas[1][1] == 107.72

    # la escalera tiene que mostrar los DOS: el NBBO real y el odd lot
    def texto_en(precio, col):
        for i in range(l.tabla.rowCount()):
            if abs((l._precio_de_fila(i) or -1) - precio) < 0.001:
                it = l.tabla.item(i, col)
                return it.text() if it else ""
        return None

    from tradingbot.gui.ladder_panel import C_ASK, C_BID
    print(f"  en la escalera -> bid real 107.72: '{texto_en(107.72, C_BID)}'  "
          f"odd lot 107.87: '{texto_en(107.87, C_BID)}'")
    print(f"                    ask real 108.20: '{texto_en(108.20, C_ASK)}'  "
          f"odd lot 108.18: '{texto_en(108.18, C_ASK)}'")
    checks["la escalera muestra el NBBO real"] = \
        texto_en(107.72, C_BID) == "100" and texto_en(108.20, C_ASK) == "200"
    checks["la escalera muestra TAMBIEN el odd lot"] = \
        texto_en(107.87, C_BID) == "7" and texto_en(108.18, C_ASK) == "2"
    l.detener()

    # ================= FEED SIN ODD LOTS (Tradier / Alpaca) =================
    print("\n=== Feed SIN odd lots (Tradier / Alpaca): nada cambia ===")
    l2 = _armar(broker, con_odd_lots=False)
    l2.actualizar_quote("AGYS", 107.72, 108.20, 100, 200)   # el streaming YA es el NBBO
    l2._repintar()
    print(f"  cartel BID     : {l2.lbl_bid.text()}")
    print(f"  boton comprar  : {l2.btn_buy_ask.text()}")
    mandadas2 = []
    l2._mandar = lambda side, precio: mandadas2.append((side, precio))
    l2._comprar_al_ask()
    checks["sin odd lots, sigue usando el streaming (como siempre)"] = \
        "107.72" in l2.lbl_bid.text() and mandadas2 == [(Side.BUY, 108.20)]
    l2.detener()

    print()
    for nombre, ok in checks.items():
        print(f"  {'OK ' if ok else '*** FALLO'} {nombre}")
    todo = all(checks.values())
    print("\nOK: se opera contra el NBBO real y los odd lots se ven igual." if todo
          else "\n*** FALLO: revisar.")
    return 0 if todo else 1


if __name__ == "__main__":
    sys.exit(main())
