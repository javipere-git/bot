"""
Prueba los AVISOS DE CUENTA: que las ordenes aparezcan al instante.

Antes: la app se enteraba de una orden (puesta / ejecutada / cancelada) recien en
el proximo sondeo, cada 4 segundos. Eso retrasaba el ladder, las listas de ordenes
y hasta el sonido, y complicaba decidir como seguir operando.

Ahora el broker AVISA y la pantalla se refresca en el momento (medido: ~200 ms).

    python examples/demo_avisos_instantaneos.py          (broker de mentira)
    python examples/demo_avisos_instantaneos.py --real   (contra Alpaca PAPER)
"""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.gui.market_worker import MarketWorker  # noqa: E402


class BrokerContando:
    """Broker de mentira: cuenta cuantas veces le piden las ordenes."""

    def __init__(self):
        self.consultas = 0

    def get_positions(self):
        return []

    def get_day_pnl(self):
        return None

    def get_quote(self, sym):
        raise RuntimeError("sin quote")

    def get_orders(self, limit=None):
        self.consultas += 1
        return []


def parte1() -> bool:
    app = QApplication.instance() or QApplication(sys.argv)
    b = BrokerContando()
    w = MarketWorker(b, interval=4.0)
    hilo = threading.Thread(target=w.run, daemon=True)
    hilo.start()
    time.sleep(0.6)

    print("1) Un aviso del broker refresca las ordenes EN EL MOMENTO")
    antes = b.consultas
    t0 = time.time()
    w.refrescar_ya()                      # es lo que hace el aviso del broker
    while b.consultas == antes and time.time() - t0 < 2:
        time.sleep(0.02)
    tardo = time.time() - t0
    ok1 = b.consultas > antes and tardo < 0.5
    print(f"   refresco en {tardo*1000:.0f} ms (el sondeo tardaba hasta 4000 ms)")
    print(f"   -> {'OK' if ok1 else '*** FALLO'}\n")

    print("2) Freno: una rafaga de avisos NO dispara decenas de llamadas")
    antes = b.consultas
    for _ in range(40):                   # 40 avisos de golpe (bot operando rapido)
        w.refrescar_ya()
        time.sleep(0.01)
    time.sleep(0.5)
    usadas = b.consultas - antes
    ok2 = usadas <= 3
    print(f"   40 avisos seguidos -> {usadas} consultas al broker (esperado <= 3)")
    print(f"   -> {'OK: el freno funciona' if ok2 else '*** FALLO: se dispararon demasiadas'}\n")
    w.stop()
    return ok1 and ok2


def parte2() -> bool:
    """Contra Alpaca PAPER: mide el aviso real de punta a punta."""
    from tradingbot.gui.perfiles import perfiles_disponibles
    from tradingbot.connectors.alpaca import AlpacaBroker
    from tradingbot.core.models import OrderRequest, OrderType, Side

    app = QApplication.instance() or QApplication(sys.argv)
    perfil = next(p for p in perfiles_disponibles() if p.id == "alpaca_paper")
    avisos = perfil.crear_avisos()
    llegadas = []
    avisos.cambio.connect(lambda: llegadas.append(time.time()))
    avisos.start()
    for _ in range(20):
        app.processEvents()
        time.sleep(0.5)
        if avisos.esta_conectado():
            break
    print("3) Contra Alpaca PAPER (dinero simulado)")
    print(f"   canal de avisos conectado: {avisos.esta_conectado()}")

    b = AlpacaBroker.from_credentials(environment="paper")
    o = b.place_order(OrderRequest("AAPL", Side.BUY, 1, 50.00, OrderType.LIMIT))
    llegadas.clear()
    t0 = time.time()
    b.cancel_order(o.id)                  # cambio de estado -> deberia avisar
    while not llegadas and time.time() - t0 < 5:
        app.processEvents()
        time.sleep(0.02)
    ok = bool(llegadas)
    if ok:
        print(f"   aviso de la cancelacion en {(llegadas[0]-t0)*1000:.0f} ms")
    else:
        print("   no llego el aviso en 5s")
    avisos.stop()
    print(f"   -> {'OK' if ok else '*** FALLO'}\n")
    return ok


def main() -> None:
    ok = parte1()
    if "--real" in sys.argv:
        ok = parte2() and ok
    else:
        print("(para medirlo contra Alpaca paper: --real)")
    print("OK: las ordenes se refrescan al instante, con freno para no agotar la API."
          if ok else "*** HAY FALLOS.")


if __name__ == "__main__":
    main()
