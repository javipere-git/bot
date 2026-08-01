"""
Prueba el panel de Time & Sales (la cinta), sin conectarse a nada.

Verifica lo que importa:
  - CADA print se muestra por separado (no se agrupan).
  - Color segun el agresivo: verde si se dio en el ask, rojo en el bid, gris adentro.
  - La mas nueva queda ARRIBA.
  - Se respeta el tope de filas (no crece infinito).
  - Al cambiar de simbolo, la cinta se limpia y solo toma el simbolo activo.

    python examples/demo_time_and_sales.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.gui.tema import colores  # noqa: E402
from tradingbot.gui.tape_panel import (  # noqa: E402
    C_CANT, C_EXCH, C_HORA, C_PRECIO, TapePanel,
)


def fila(t, i):
    return tuple(t.tabla.item(i, c).text() for c in (C_HORA, C_PRECIO, C_CANT, C_EXCH))


def color(t, i):
    return t.tabla.item(i, C_PRECIO).foreground().color().name()


def main() -> None:
    app = QApplication(sys.argv)
    t = TapePanel()
    t.set_symbol("SPY")
    t.actualizar_quote("SPY", 100.00, 100.10)
    ahora = time.time()

    print("1) NO se agrupan los prints: mando 10 operaciones de 10 acciones")
    for i in range(10):
        t.agregar_trade("SPY", 100.05, 10, "Q", ahora + i)
    t._volcar()
    ok1 = t.tabla.rowCount() == 10
    print(f"   filas en la cinta: {t.tabla.rowCount()} (esperado 10, NO 1 de 100)")
    print(f"   -> {'OK: cada print por separado' if ok1 else '*** FALLO: los agrupo'}\n")

    print("2) Color segun quien fue el agresivo (bid 100.00 x ask 100.10)")
    t.set_symbol("SPY"); t.actualizar_quote("SPY", 100.00, 100.10)
    t.agregar_trade("SPY", 100.10, 50, "P", ahora)      # en el ask -> compra
    t.agregar_trade("SPY", 100.00, 30, "K", ahora + 1)  # en el bid -> venta
    t.agregar_trade("SPY", 100.05, 20, "V", ahora + 2)  # adentro   -> gris
    t._volcar()
    # la mas nueva arriba: fila 0 = la de 100.05
    c_dentro, c_bid, c_ask = color(t, 0), color(t, 1), color(t, 2)
    VERDE, ROJO, GRIS = (colores("tape_verde"), colores("tape_rojo"),
                         colores("tape_gris"))     # dependen del tema activo
    ok2 = (c_ask == VERDE.name() and c_bid == ROJO.name() and c_dentro == GRIS.name())
    print(f"   en el ask (100.10): {c_ask}  = verde {VERDE.name()}")
    print(f"   en el bid (100.00): {c_bid}  = rojo  {ROJO.name()}")
    print(f"   dentro   (100.05): {c_dentro}  = gris  {GRIS.name()}")
    print(f"   -> {'OK' if ok2 else '*** FALLO'}\n")

    print("3) La mas nueva queda ARRIBA")
    ok3 = fila(t, 0)[1] == "100.05"
    print(f"   fila 0: {fila(t, 0)}  (la ultima que mande)")
    print(f"   -> {'OK' if ok3 else '*** FALLO'}\n")

    print("4) Tope de filas (no crece infinito)")
    t.set_symbol("SPY"); t.actualizar_quote("SPY", 100.00, 100.10)
    for i in range(t.MAX_FILAS + 120):
        t.agregar_trade("SPY", 100.05, 1, "Q", ahora + i)
    t._volcar()
    ok4 = t.tabla.rowCount() == t.MAX_FILAS
    print(f"   mande {t.MAX_FILAS + 120} operaciones -> quedaron {t.tabla.rowCount()} "
          f"(tope {t.MAX_FILAS})")
    print(f"   -> {'OK' if ok4 else '*** FALLO'}\n")

    print("5) Solo el simbolo activo, y limpia al cambiar")
    t.set_symbol("AAPL")
    vacia = t.tabla.rowCount() == 0
    t.agregar_trade("SPY", 100.05, 10, "Q", ahora)   # simbolo viejo: se ignora
    t.agregar_trade("AAPL", 340.00, 10, "Q", ahora)
    t._volcar()
    ok5 = vacia and t.tabla.rowCount() == 1 and fila(t, 0)[1] == "340.00"
    print(f"   limpio al cambiar de simbolo: {vacia}")
    print(f"   filas tras mandar 1 de SPY (viejo) y 1 de AAPL: {t.tabla.rowCount()} (esperado 1)")
    print(f"   -> {'OK' if ok5 else '*** FALLO'}\n")

    todo = ok1 and ok2 and ok3 and ok4 and ok5
    print("OK: la cinta muestra cada print, con color de agresivo y sin crecer al infinito."
          if todo else "*** HAY FALLOS.")


if __name__ == "__main__":
    main()
