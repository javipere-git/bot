"""Verifica el modo oscuro y la memoria de los anchos de las secciones."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.gui.estado_ui import guardar_splitter  # noqa: E402
from tradingbot.gui.main_window import MainWindow  # noqa: E402
from tradingbot.gui.perfiles import perfil_por_defecto  # noqa: E402
from tradingbot.gui.tema import aplicar_tema, es_oscuro  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    aplicar_tema(False)
    w = MainWindow(perfil_por_defecto())
    w.show()
    app.processEvents()

    def fondo():
        return app.palette().color(QPalette.Window).name()

    print("1) Modo oscuro (boton en el banner)")
    claro = fondo()
    print(f"   arranca: boton dice '{w.btn_tema.text()}'  fondo {claro}")
    w._cambiar_tema()
    app.processEvents()
    osc = fondo()
    print(f"   al tocarlo: boton dice '{w.btn_tema.text()}'  fondo {osc}")
    ok1 = osc != claro and es_oscuro()
    w._cambiar_tema()
    app.processEvents()
    ok1 = ok1 and fondo() == claro and not es_oscuro()
    print(f"   vuelve al claro: {fondo() == claro}")
    print(f"   -> {'OK' if ok1 else '*** FALLO'}\n")

    print("2) Se recuerda el ancho de cada seccion (bot / monitor / ladder / TAS)")
    w._splitter.setSizes([300, 500, 400, 300])
    app.processEvents()
    antes = w._splitter.sizes()
    guardar_splitter(w._splitter)          # (pasa al cerrar la app)
    w2 = MainWindow(perfil_por_defecto())  # "reabre"
    w2.show()
    app.processEvents()
    despues = w2._splitter.sizes()
    ok2 = despues == antes
    print(f"   anchos puestos: {antes}")
    print(f"   al reabrir    : {despues}")
    print(f"   -> {'OK' if ok2 else '*** FALLO'}\n")

    print("OK: modo oscuro y memoria de secciones funcionan."
          if ok1 and ok2 else "*** HAY FALLOS.")


if __name__ == "__main__":
    main()
