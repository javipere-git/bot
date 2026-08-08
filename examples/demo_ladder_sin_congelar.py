"""
Prueba que el LADDER no congela la pantalla al operar (no toca dinero: broker falso).

Que se verifica (con un broker de mentira que tarda 300 ms a proposito):

  1. NO BLOQUEA: el click vuelve al instante (antes esperaba los 300 ms).
  2. EN ORDEN: tres clicks seguidos salen 1, 2, 3 (nunca mezclados ni en paralelo).
  3. HILO CORRECTO: la llamada al broker corre FUERA del hilo de la pantalla, y el
     aviso del registro vuelve DENTRO del hilo de la pantalla (tocar widgets desde
     otro hilo tumba la app).
  4. RED DE SEGURIDAD: la venta que abriria un corto sin querer se frena ANTES de
     encolar; al broker no le llega nada.

    python examples/demo_ladder_sin_congelar.py
"""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.core.models import Order, OrderStatus, Side  # noqa: E402


DEMORA = 0.30          # lo que "tarda" el broker falso en contestar


class BrokerLento:
    """Broker de mentira que tarda a proposito, y anota quien lo llamo y cuando.

    Se guarda el ID REAL del hilo (threading.get_ident()), no el nombre: a los hilos
    creados por Qt, Python les inventa nombres tipo 'Dummy-N' que no son estables.
    Tambien se anota cuando EMPEZO y cuando TERMINO cada llamada, para comprobar que
    dos nunca se solapan (esa es la garantia de verdad: de a una y en orden)."""

    def __init__(self) -> None:
        self.llamadas = []            # (que, id_hilo, inicio, fin)
        self.lock = threading.Lock()

    def _trabajar(self, que):
        inicio = time.monotonic()
        time.sleep(DEMORA)
        with self.lock:
            self.llamadas.append((que, threading.get_ident(), inicio, time.monotonic()))

    def place_order(self, req):
        self._trabajar(f"place {req.symbol} {req.side.value} {req.quantity} @ {req.price}")
        return Order(id=f"id-{len(self.llamadas)}", symbol=req.symbol, side=req.side,
                     quantity=req.quantity, price=req.price, status=OrderStatus.PENDING)

    def modify_order(self, oid, *, price=None, quantity=None, duration=None):
        self._trabajar(f"modify {oid} -> {price}")
        return Order(id=str(oid), symbol="", side=Side.BUY, quantity=0, price=price or 0.0,
                     status=OrderStatus.PENDING)

    def cancel_order(self, oid):
        self._trabajar(f"cancel {oid}")

    def get_open_orders(self):
        self._trabajar("get_open_orders")
        return []

    def distingue_venta_en_corto(self) -> bool:
        return False          # como Alpaca: la app pone la red de seguridad


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    from tradingbot.gui.ladder_panel import LadderPanel

    broker = BrokerLento()
    recibidos = []            # (mensaje, hilo en que llego)
    panel = LadderPanel(
        broker_provider=lambda: broker,
        log=lambda m: recibidos.append((m, threading.get_ident())),
    )
    panel._symbol = "AAPL"
    panel.spin_size.setValue(10)
    hilo_pantalla = threading.get_ident()

    if panel._worker is None:
        print("*** FALLO: no arranco el hilo del ladder")
        return 1

    # ---- 1 y 2: tres clicks seguidos, medir cuanto tarda en volver y en que orden ----
    t0 = time.monotonic()
    panel._mandar(Side.BUY, 10.01)
    panel._mandar(Side.BUY, 10.02)
    panel._mandar(Side.BUY, 10.03)
    demora_click = time.monotonic() - t0

    # ---- 4: venta que abriria un corto (sin posicion) -> se frena aca ----
    panel._pos_qty = 0
    panel._mandar(Side.SELL, 9.99)

    # esperar a que el hilo termine las tres, sin bloquear el bucle de Qt
    fin = time.monotonic() + 5
    while len(broker.llamadas) < 3 and time.monotonic() < fin:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()       # entregar los avisos pendientes a la pantalla

    hechos = [c[0] for c in broker.llamadas]
    hilos_broker = {c[1] for c in broker.llamadas}
    hilos_log = {h for _, h in recibidos}

    # ninguna llamada empezo antes de que terminara la anterior (nunca dos a la vez)
    tramos = sorted((c[2], c[3]) for c in broker.llamadas)
    sin_solape = all(tramos[i][0] >= tramos[i - 1][1] for i in range(1, len(tramos)))

    print(f"El click volvio en {demora_click*1000:.0f} ms "
          f"(el broker tarda {DEMORA*1000:.0f} ms por orden; 3 ordenes = "
          f"{3*DEMORA*1000:.0f} ms si bloqueara)")
    print("Llamadas al broker, en orden:")
    for h in hechos:
        print("   ", h)
    print("Hilo(s) donde corrio el broker:", hilos_broker)
    print("Hilo(s) donde llego el registro:", hilos_log, f"(pantalla = {hilo_pantalla})")
    print()

    checks = {
        "el click NO bloquea (volvio en menos de 1 demora)":
            demora_click < DEMORA,
        "salieron las 3 ordenes": len(hechos) == 3,
        "salieron EN ORDEN (10.01, 10.02, 10.03)":
            hechos == ["place AAPL buy 10 @ 10.01",
                       "place AAPL buy 10 @ 10.02",
                       "place AAPL buy 10 @ 10.03"],
        "el broker NO corrio en el hilo de la pantalla":
            hilo_pantalla not in hilos_broker,
        "el broker corrio en UN solo hilo":
            len(hilos_broker) == 1,
        "las llamadas NO se solaparon (de a una)": sin_solape,
        "el registro llego EN el hilo de la pantalla":
            hilos_log <= {hilo_pantalla},
        "la venta sin posicion NO llego al broker (red de seguridad)":
            not any("sell" in h for h in hechos),
    }
    for nombre, ok in checks.items():
        print(f"  {'OK ' if ok else '*** FALLO'} {nombre}")

    panel.detener()
    QTimer.singleShot(0, app.quit)
    todo = all(checks.values())
    print("\nOK: el ladder opera sin congelar la pantalla." if todo
          else "\n*** FALLO en alguna verificacion.")
    return 0 if todo else 1


if __name__ == "__main__":
    sys.exit(main())
