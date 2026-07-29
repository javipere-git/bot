"""
Prueba el CONGELADO del ladder con el mouse encima (no toca dinero: solo pantalla).

Idea (como ThinkorSwim): mientras el cursor esta sobre la escalera, los precios
quedan CLAVADOS en su fila. Sin esto, si el precio se mueve justo cuando vas a
hacer click, la fila cambia de precio abajo del cursor y la orden sale a OTRO
precio. Es el escenario que le costo plata al usuario.

Reproduce el caso: mirando 100.00 x 100.10, el precio salta a 100.50 x 100.80.

    python examples/demo_ladder_congelado.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.gui.ladder_panel import C_PRICE, LadderPanel  # noqa: E402


def precios_por_fila(panel) -> dict:
    """{fila: precio} de lo que se ve en pantalla."""
    out = {}
    for i in range(panel.tabla.rowCount()):
        it = panel.tabla.item(i, C_PRICE)
        if it and it.text():
            out[i] = it.text()
    return out


def main() -> None:
    app = QApplication(sys.argv)
    panel = LadderPanel()
    panel.show()
    panel.ed_symbol.setText("TEST")
    panel._cambiar_symbol()

    mouse = {"encima": False}
    panel._mouse_sobre_escalera = lambda: mouse["encima"]   # simulo el cursor

    panel.actualizar_quote("TEST", 100.00, 100.10, 300, 200)
    panel._repintar()
    antes = precios_por_fila(panel)
    fila_objetivo = next(f for f, p in antes.items() if p == "100.02")
    print(f"Estado inicial: 100.00 x 100.10")
    print(f"   la fila {fila_objetivo} muestra el precio {antes[fila_objetivo]} "
          f"(ahi voy a clickear)\n")

    # ---- CASO 1: mouse ENCIMA, el precio se dispara ----
    print("CASO 1: con el mouse ENCIMA, el precio salta a 100.50 x 100.80")
    mouse["encima"] = True
    panel.actualizar_quote("TEST", 100.50, 100.80, 300, 200)
    panel._repintar()
    congelado = precios_por_fila(panel)
    precio_ahora = congelado.get(fila_objetivo)
    ok1 = precio_ahora == antes[fila_objetivo]
    print(f"   la fila {fila_objetivo} ahora muestra: {precio_ahora}  "
          f"(esperado {antes[fila_objetivo]})")
    print(f"   -> {'OK: el precio NO se movio de fila' if ok1 else '*** FALLO: cambio'}")
    print(f"   aviso en pantalla: \"{panel._ayuda.text()}\"")
    # el NBBO grande de arriba SI se actualiza (para no operar a ciegas)
    ok2 = "100.50" in panel.lbl_bid.text() and "100.80" in panel.lbl_ask.text()
    print(f"   BID/ASK arriba: {panel.lbl_bid.text()} / {panel.lbl_ask.text()}")
    print(f"   -> {'OK: el precio real sigue a la vista' if ok2 else '*** FALLO'}\n")

    # ---- CASO 2: saco el mouse -> se re-sincroniza ----
    print("CASO 2: saco el mouse de la escalera")
    mouse["encima"] = False
    panel.actualizar_quote("TEST", 100.50, 100.80, 300, 200)
    panel._repintar()
    libre = precios_por_fila(panel)
    hay_10050 = "100.50" in libre.values()
    ok3 = libre.get(fila_objetivo) != antes[fila_objetivo] and hay_10050
    print(f"   la escalera ahora abarca el precio actual (100.50 visible): {hay_10050}")
    print(f"   -> {'OK: volvio a seguir al mercado' if ok3 else '*** FALLO'}\n")

    # ---- CASO 3: boton Centrar funciona aunque el mouse este encima ----
    print("CASO 3: con el mouse ENCIMA, apreto el boton Centrar")
    mouse["encima"] = True
    panel.actualizar_quote("TEST", 101.00, 101.10, 300, 200)
    panel._repintar()                      # congelada: no deberia seguir al precio
    antes_centrar = "101.00" in precios_por_fila(panel).values()
    panel._centrar()                       # el usuario pide centrar
    despues_centrar = "101.00" in precios_por_fila(panel).values()
    ok4 = (not antes_centrar) and despues_centrar
    print(f"   antes de Centrar, 101.00 visible: {antes_centrar} (esperado False)")
    print(f"   despues de Centrar, 101.00 visible: {despues_centrar} (esperado True)")
    print(f"   -> {'OK: Centrar manda al precio actual' if ok4 else '*** FALLO'}\n")

    todo = ok1 and ok2 and ok3 and ok4
    print("OK: el congelado protege el click y no deja la escalera pegada."
          if todo else "*** HAY FALLOS.")


if __name__ == "__main__":
    main()
