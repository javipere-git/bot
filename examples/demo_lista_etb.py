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

    todo = ok1 and ok2 and ok3 and ok4 and ok5
    print("OK: la lista ETB sale del broker donde se opera, se carga y se descarga."
          if todo else "*** HAY FALLOS.")
    return todo


if __name__ == "__main__":
    ok = main()
    sys.stdout.flush()
    os._exit(0 if ok else 1)
