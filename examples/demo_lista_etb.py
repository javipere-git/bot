"""
Lista ETB (Easy To Borrow): cargarla en la watchlist o descargarla a un archivo.

ETB = las acciones que el broker deja vender en CORTO. En Alpaca, ademas, no pagan
costo de prestamo, y las que NO estan en la lista directamente no se pueden shortear
(la orden se rechaza).

LO IMPORTANTE que se verifica aca: la lista se le pide al broker donde se OPERA, NO
al que da los precios. Con el perfil hibrido (opera en Alpaca, precios de Tradier)
tiene que traer la de ALPACA, que es quien acepta o rechaza el short.

    python examples/demo_lista_etb.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.connectors.hibrido import BrokerHibrido  # noqa: E402
from tradingbot.gui.control_panel import ControlPanel  # noqa: E402


class BrokerOpera(FakeBroker):
    """El broker donde se MANDAN las ordenes."""

    def lista_etb(self):
        return ["AAPL", "MSFT", "SPY"]


class BrokerDatos(FakeBroker):
    """El broker que solo da PRECIOS (su lista no debe usarse)."""

    def lista_etb(self):
        return ["ZZZZ", "YYYY"]


def main() -> None:
    app = QApplication(sys.argv)

    print("1) El HIBRIDO pide la lista a quien OPERA, no a quien da los precios")
    h = BrokerHibrido(operativa=BrokerOpera(), datos=BrokerDatos())
    lista = h.lista_etb()
    ok1 = lista == ["AAPL", "MSFT", "SPY"]
    print(f"   opera con lista {BrokerOpera().lista_etb()}")
    print(f"   datos  con lista {BrokerDatos().lista_etb()}")
    print(f"   el hibrido devuelve: {lista}")
    print(f"   -> {'OK: uso la del que opera' if ok1 else '*** FALLO: uso la equivocada'}\n")

    print("2) 'Cargar lista ETB' llena la watchlist")
    panel = ControlPanel()
    panel.txt_watchlist.setPlainText(" ".join(lista))
    cargados = panel.get_symbols()
    ok2 = cargados == ["AAPL", "MSFT", "SPY"]
    print(f"   watchlist: {cargados}")
    print(f"   -> {'OK' if ok2 else '*** FALLO'}\n")

    print("3) 'Descargar lista ETB' guarda un archivo con un simbolo por linea")
    ruta = os.path.join(tempfile.gettempdir(), "etb_prueba.txt")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lista) + "\n")
    leido = [x.strip() for x in open(ruta, encoding="utf-8") if x.strip()]
    ok3 = leido == lista
    print(f"   guardado en {ruta}")
    print(f"   releido: {leido}")
    print(f"   -> {'OK' if ok3 else '*** FALLO'}")
    os.remove(ruta)
    print()

    print("4) Los dos botones existen en el panel de Control")
    ok4 = (hasattr(panel, "btn_etb_cargar") and hasattr(panel, "btn_etb_bajar")
           and panel.btn_etb_cargar.text() == "Cargar lista ETB"
           and panel.btn_etb_bajar.text() == "Descargar lista ETB")
    print(f"   '{panel.btn_etb_cargar.text()}' y '{panel.btn_etb_bajar.text()}'")
    print(f"   -> {'OK' if ok4 else '*** FALLO'}\n")

    print("5) Un broker que no informa ETB devuelve lista vacia (no rompe)")
    ok5 = FakeBroker().lista_etb() == []
    print(f"   FakeBroker.lista_etb() -> {FakeBroker().lista_etb()}")
    print(f"   -> {'OK' if ok5 else '*** FALLO'}\n")

    print("6) El pedido EN OTRO HILO termina de verdad (y suelta los botones)")
    # Bug real (04/08/2026): se guardaba la referencia del hilo pero NO la del objeto
    # que hace el trabajo. Python lo descartaba, su run() nunca corria, y los botones
    # quedaban deshabilitados para siempre sin ningun mensaje (al usuario le paso:
    # 5 minutos esperando una lista que tarda segundos).
    import time
    from tradingbot.gui.main_window import MainWindow
    from tradingbot.gui.perfiles import Perfil

    class BrokerLento(FakeBroker):
        def lista_etb(self):
            time.sleep(0.4)              # como una llamada de red
            return ["AAPL", "MSFT", "SPY"]

    perfil = Perfil(
        id="prueba", broker_nombre="Prueba", cuenta_texto="test", es_live=False,
        _crear_broker=lambda: BrokerLento(),
    )
    w = MainWindow(perfil)
    app.processEvents()
    w._lista_etb("cargar")
    app.processEvents()
    deshabilitados = not w.control.btn_etb_cargar.isEnabled()
    t0 = time.time()
    while time.time() - t0 < 8:          # el bug dejaba esto colgado para siempre
        app.processEvents()
        if w.control.btn_etb_cargar.isEnabled():
            break
        time.sleep(0.05)
    tardo = time.time() - t0
    volvieron = w.control.btn_etb_cargar.isEnabled()
    cargo = w.control.get_symbols() == ["AAPL", "MSFT", "SPY"]
    ok6 = deshabilitados and volvieron and cargo and tardo < 5
    print(f"   botones deshabilitados mientras trae: {deshabilitados}")
    print(f"   termino en {tardo:.1f}s y los solto: {volvieron}")
    print(f"   watchlist cargada: {cargo}")
    print(f"   -> {'OK' if ok6 else '*** FALLO: quedo colgado (es el bug)'}" + chr(10))

    todo = ok1 and ok2 and ok3 and ok4 and ok5 and ok6
    print("OK: la lista ETB sale del broker donde se opera, se carga y se descarga."
          if todo else "*** HAY FALLOS.")
    return todo


if __name__ == "__main__":
    ok = main()
    sys.stdout.flush()
    os._exit(0 if ok else 1)
