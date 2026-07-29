"""
Prueba cuanto tarda el LADDER en mostrar la escalera al cargar un simbolo.

Por que existe: el ladder se alimentaba SOLO del streaming, y el streaming manda
datos unicamente cuando el precio CAMBIA. En acciones poco liquidas eso significa
que la escalera puede quedar VACIA varios minutos (medido: 45s sin un solo quote
en KPLT y SFBC), aunque el precio este disponible por REST al instante.

Ahora, al cargar un simbolo, se pide el precio por REST en el acto y ademas se
refresca cada ciclo; el streaming sigue dando el tiempo real cuando hay movimiento.

    python examples/demo_ladder_carga.py            (con el broker de mentira)
    python examples/demo_ladder_carga.py --real     (contra Alpaca, acciones reales)
"""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.gui.ladder_panel import LadderPanel  # noqa: E402
from tradingbot.gui.market_worker import MarketWorker  # noqa: E402


class BrokerLento:
    """Broker de mentira: da precios por REST, pero NUNCA manda nada por streaming
    (justo lo que pasa con una accion poco liquida)."""

    def __init__(self):
        self.pedidos = 0

    def get_positions(self):
        return []

    def get_orders(self, limit=None):
        return []

    def get_day_pnl(self):
        return None

    def get_quote(self, sym):
        self.pedidos += 1
        from tradingbot.core.models import Quote
        return Quote(sym, 43.82, 45.01, 100, 100)


def main() -> None:
    app = QApplication(sys.argv)
    ladder = LadderPanel()
    broker = BrokerLento()
    w = MarketWorker(broker, interval=4.0)
    w.quote.connect(ladder.actualizar_quote)
    hilo = threading.Thread(target=w.run, daemon=True)
    hilo.start()

    print("Se carga un simbolo en el ladder (accion SIN movimiento: el streaming")
    print("no manda nada). Antes, la escalera quedaba vacia esperando.\n")

    ladder.ed_symbol.setText("SFBC")
    ladder._cambiar_symbol()
    w.set_ladder_symbol("SFBC")        # es lo que hace la ventana al cargar el simbolo

    t0 = time.time()
    filas = 0
    while time.time() - t0 < 6:
        app.processEvents()
        ladder._repintar()
        filas = ladder.tabla.rowCount()
        if filas:
            break
        time.sleep(0.05)
    tardo = time.time() - t0
    w.stop()

    print(f"la escalera se lleno en {tardo:.2f} segundos ({filas} filas)")
    print(f"BID/ASK en pantalla: {ladder.lbl_bid.text()} / {ladder.lbl_ask.text()}")
    ok = filas > 0 and tardo < 3
    print(f"\n{'OK: carga al instante, sin depender del streaming.' if ok else '*** FALLO: sigue tardando.'}")

    if "--real" in sys.argv:
        print("\n--- contra Alpaca, con las acciones que dieron problema ---")
        from tradingbot.connectors.alpaca import AlpacaBroker
        real = AlpacaBroker.from_credentials(environment="live")
        for sym in ("KPLT", "SFBC", "TWFG"):
            t0 = time.time()
            q = real.get_quote(sym)
            print(f"  {sym}: {time.time()-t0:.2f}s -> bid {q.bid} x ask {q.ask}")


if __name__ == "__main__":
    main()
