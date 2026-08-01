"""
Verifica que en MODO OSCURO no quede nada ilegible.

El problema que revisa: poner una hoja de estilo en un widget (aunque sea solo
"font-size: 11px") hace que Qt DESCARTE la paleta para ese widget y use sus colores
por defecto. Resultado: titulos en NEGRO sobre fondo oscuro (ilegibles) y tablas con
fondo BLANCO aunque el tema sea oscuro.

Se comprueba:
  1. Ningun widget usa una hoja de estilo que rompa la paleta (sin color explicito).
  2. Los titulos de los paneles se leen: su color contrasta con el fondo.
  3. El ladder y la cinta usan el fondo oscuro (no quedan en blanco).
  4. Los colores del ladder cambian con el tema, y el texto contrasta con su celda.

    python examples/verificar_modo_oscuro.py
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.gui.main_window import MainWindow  # noqa: E402
from tradingbot.gui.perfiles import perfil_por_defecto  # noqa: E402
from tradingbot.gui.tema import aplicar_tema, colores  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _luminancia(c):
    """0 = negro, 1 = blanco (formula estandar de brillo percibido)."""
    r, g, b = c.redF(), c.greenF(), c.blueF()
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrasta(a, b, minimo=0.25) -> bool:
    return abs(_luminancia(a) - _luminancia(b)) >= minimo


def revisar_hojas_de_estilo() -> bool:
    """Ninguna hoja de estilo debe fijar letra/tamano SIN fijar tambien el color."""
    print("1) Hojas de estilo que romperian la paleta")
    malas = []
    carpeta = os.path.join(RAIZ, "tradingbot", "gui")
    for archivo in sorted(os.listdir(carpeta)):
        if not archivo.endswith(".py"):
            continue
        texto = open(os.path.join(carpeta, archivo), encoding="utf-8").read()
        for m in re.finditer(r"setStyleSheet\(\s*\"([^\"]*)\"", texto):
            hoja = m.group(1)
            if "color" in hoja or "background-color: {" in hoja:
                continue          # fija el color a proposito: no rompe nada
            if "font" in hoja or "border" in hoja:
                linea = texto[:m.start()].count("\n") + 1
                malas.append(f"{archivo}:{linea} -> {hoja[:45]}")
    for m in malas:
        print(f"   *** {m}")
    print(f"   -> {'OK: ninguna' if not malas else '*** FALLO'}\n")
    return not malas


def main() -> bool:
    app = QApplication(sys.argv)
    aplicar_tema(True)                      # modo OSCURO
    w = MainWindow(perfil_por_defecto())
    w.show()
    app.processEvents()

    ok1 = revisar_hojas_de_estilo()

    fondo = app.palette().color(QPalette.Window)
    base = app.palette().color(QPalette.Base)

    print("2) Los titulos de los paneles se leen sobre el fondo oscuro")
    titulos = {
        "Control del bot": w.control,
        "Monitoreo": w.monitor,
        "Ladder": w.ladder,
        "Time & Sales": w.tape,
    }
    ok2 = True
    from PySide6.QtWidgets import QLabel, QToolButton
    for nombre, panel in titulos.items():
        lbl = next((x for x in panel.findChildren(QLabel) if x.text() == nombre), None)
        if lbl is None:
            print(f"   ?  no encontre el titulo {nombre!r}")
            continue
        color = lbl.palette().color(QPalette.WindowText)
        bien = _contrasta(color, fondo)
        ok2 = ok2 and bien
        print(f"   {'OK ' if bien else '***'} {nombre:16} texto {color.name()} sobre {fondo.name()}")
    # las secciones colapsables del monitoreo
    for btn in w.monitor.findChildren(QToolButton):
        color = btn.palette().color(QPalette.ButtonText)
        bien = _contrasta(color, fondo)
        ok2 = ok2 and bien
        print(f"   {'OK ' if bien else '***'} {btn.text():16} texto {color.name()}")
    print(f"   -> {'OK' if ok2 else '*** FALLO: hay titulos ilegibles'}\n")

    print("3) El ladder y la cinta NO quedan en blanco")
    # usan un fondo propio (fondo_ladder), a proposito mas TENUE que el resto de la
    # app, pero igual oscuro. Lo que se verifica es que no queden claros.
    propio = colores("fondo_ladder")
    ok3 = True
    for nombre, tabla in (("ladder", w.ladder.tabla), ("Time & Sales", w.tape.tabla)):
        c = tabla.palette().color(QPalette.Base)
        bien = _luminancia(c) < 0.5 and c.name() == propio.name()
        ok3 = ok3 and bien
        print(f"   {'OK ' if bien else '***'} {nombre:12} fondo {c.name()} "
              f"(esperado {propio.name()}, mas tenue que el {base.name()} general)")
    print(f"   -> {'OK' if ok3 else '*** FALLO: quedaron claros'}\n")

    print("4) Los colores del ladder cambian con el tema y el texto contrasta")
    ok4 = True
    for clave in ("verde", "rojo", "azul", "amarillo"):
        c_osc = colores(clave)
        texto = colores("texto")
        bien = _contrasta(c_osc, texto, 0.20)
        ok4 = ok4 and bien
        print(f"   {'OK ' if bien else '***'} {clave:9} celda {c_osc.name()} / letra {texto.name()}")
    aplicar_tema(False)
    distintos = colores("verde").name() != c_osc.name()
    ok4 = ok4 and distintos
    print(f"   {'OK ' if distintos else '***'} en modo claro el verde es {colores('verde').name()}"
          f" (distinto del oscuro)")
    print(f"   -> {'OK' if ok4 else '*** FALLO'}\n")

    print("5) Tamanos de letra: los de siempre (en PIXELES, no en puntos)")
    aplicar_tema(True)
    from PySide6.QtWidgets import QLabel as _QL
    tam_ladder = w.ladder.tabla.font().pixelSize()
    tam_tape = w.tape.tabla.font().pixelSize()
    t_lad = next(x for x in w.ladder.findChildren(_QL) if x.text() == "Ladder")
    tam_titulo = t_lad.font().pixelSize()
    ok5 = tam_ladder == 11 and tam_tape == 11 and tam_titulo == 13
    print(f"   tabla del ladder {tam_ladder}px, cinta {tam_tape}px (esperado 11)")
    print(f"   titulo {tam_titulo}px (esperado 13)")
    print(f"   -> {'OK' if ok5 else '*** FALLO: cambiaron de tamano'}" + chr(10))

    print("6) Ladder: columnas sombreadas con el best bid/ask resaltado")
    w.ladder.ed_symbol.setText("SPY")
    w.ladder._cambiar_symbol()
    w.ladder.actualizar_quote("SPY", 100.00, 100.10, 500, 400)
    w.ladder._repintar()
    from tradingbot.gui.ladder_panel import C_ASK, C_BID
    hallados = {}
    for r in range(w.ladder.tabla.rowCount()):
        precio = w.ladder._precio_de_fila(r)
        for objetivo, (col, nombre) in {
            100.00: (C_BID, "best_bid"), 99.95: (C_BID, "col_bid"),
            100.10: (C_ASK, "best_ask"), 100.20: (C_ASK, "col_ask"),
        }.items():
            if abs(precio - objetivo) < 0.001:
                hallados[nombre] = w.ladder.tabla.item(r, col).background().color().name()
    esperado = {
        "best_bid": colores("verde").name(), "col_bid": colores("verde_col").name(),
        "best_ask": colores("rojo").name(), "col_ask": colores("rojo_col").name(),
    }
    ok6 = hallados == esperado
    for k, v in esperado.items():
        bien = hallados.get(k) == v
        print(f"   {'OK ' if bien else '***'} {k:9} {hallados.get(k)} (esperado {v})")
    print(f"   -> {'OK' if ok6 else '*** FALLO'}" + chr(10))

    print("7) Las tablas NO llevan hoja de estilo (si no, se rompe todo)")
    # Con una hoja de estilo en QTableView::item, Qt ignora el color propio de cada
    # celda (se pierde el sombreado), las barras de desplazamiento se dibujan blancas
    # y el texto se ve como en negrita. El fondo y la grilla van por PALETA.
    ok7 = True
    for nombre, t in (("ladder", w.ladder.tabla), ("Time & Sales", w.tape.tabla),
                      ("ordenes", w.monitor.tbl_ord)):
        limpia = t.styleSheet() == ""
        ok7 = ok7 and limpia
        print(f"   {'OK ' if limpia else '***'} {nombre:12} hoja de estilo: "
              f"{t.styleSheet()[:30]!r} (esperada vacia)")
    print(f"   -> {'OK' if ok7 else '*** FALLO'}" + chr(10))

    todo = ok1 and ok2 and ok3 and ok4 and ok5 and ok6 and ok7
    print("OK: el modo oscuro se lee bien en todos los paneles."
          if todo else "*** HAY FALLOS EN EL MODO OSCURO.")
    return todo


if __name__ == "__main__":
    ok = main()
    sys.stdout.flush()
    os._exit(0 if ok else 1)
