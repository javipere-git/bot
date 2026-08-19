"""
Watchlists guardadas: los botones WL 1 / WL 2 / WL 3 y la ruedita.

PARA QUE: la watchlist se arma a mano o con el boton de ETB (que trae miles de
simbolos). Rearmarla cada vez es tedioso, y peor si tenes varias segun el dia.

LO IMPORTANTE, y es lo primero que se verifica: el CAMPO de la pantalla sigue
siendo el que manda. Los botones solo lo llenan. El bot lee lo que hay en el
campo, igual que siempre: esto no le agrega ni una llamada ni una vuelta.

 1. Ida y vuelta al archivo, con los nombres.
 2. Guardar una NO pisa las otras.
 3. Los simbolos se normalizan igual que la watchlist de la pantalla.
 4. Una PC nueva arranca con la lista COMPARTIDA, y guardar no la toca (la regla
    del 18/08/2026: un archivo que la app reescribe no va al repositorio).
 5. El boton carga la lista en el campo, y el bot la lee igual que si la
    hubieras escrito a mano.
 6. Una WL vacia queda deshabilitada (no te deja borrar la watchlist sin querer).
 7. El nombre esta en la ayuda del boton, aunque el boton diga "WL 1".
 8. "Tomar la de la pantalla" guarda lo que tenes cargado, sin copiar y pegar.
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.core import watchlists                              # noqa: E402

fallos = []


def check(ok, titulo, detalle=""):
    print(f"  {'OK  ' if ok else 'FALLO'}  {titulo}{'  ->  ' + detalle if detalle else ''}")
    if not ok:
        fallos.append(titulo)


carpeta = tempfile.mkdtemp(prefix="watchlists_")
ruta = os.path.join(carpeta, "watchlists.txt")

print("\n=== 1. Ida y vuelta, con los nombres ===")
watchlists.guardar([("Acciones caras", ["aapl", "$msft"]),
                    ("ETB del dia", ["AAA", "BBB", "CCC"]),
                    ("Vacia", [])], ruta)
listas = watchlists.leer(ruta)
check(len(listas) == watchlists.CUANTAS,
      f"vuelven siempre las {watchlists.CUANTAS}", f"{len(listas)}")
check(listas[0] == ("Acciones caras", ["AAPL", "MSFT"]),
      "el nombre y los simbolos, en mayuscula y sin el $", f"{listas[0]}")
check(listas[1][1] == ["AAA", "BBB", "CCC"], "cada una con lo suyo", f"{listas[1]}")
check(listas[2][1] == [], "y la vacia queda vacia")

print("\n=== 2. Guardar una NO pisa las otras ===")
listas[1] = ("ETB del dia", ["ZZZ"])
watchlists.guardar(listas, ruta)
listas = watchlists.leer(ruta)
check(listas[0][1] == ["AAPL", "MSFT"] and listas[1][1] == ["ZZZ"],
      "cambio solo la que toque", f"{[(n, s) for n, s in listas]}")

print("\n=== 3. Los simbolos se normalizan como en la pantalla ===")
watchlists.guardar([("Mezcla", ["aapl, msft;  nvda\ntsla", "AAPL"])], ruta)
listas = watchlists.leer(ruta)
check(listas[0][1] == ["AAPL", "MSFT", "NVDA", "TSLA"],
      "comas, espacios, ; y saltos; y sin repetir", f"{listas[0][1]}")
watchlists.guardar([("", ["AAA"])], ruta)
check(watchlists.leer(ruta)[0][0], "una lista sin nombre igual se guarda, con uno puesto",
      f"{watchlists.leer(ruta)[0][0]}")
watchlists.guardar([("Con = y\nsaltos", ["AAA"])], ruta)
l0 = watchlists.leer(ruta)[0]
check(l0[1] == ["AAA"] and "\n" not in l0[0] and "=" not in l0[0],
      "un nombre con caracteres raros no rompe el archivo", f"{l0}")

print("\n=== 4. Una PC nueva arranca con la COMPARTIDA, y guardar no la toca ===")
ruta_pc = os.path.join(carpeta, "pcnueva.txt")
with open(watchlists._compartida(ruta_pc), "w", encoding="utf-8") as f:
    f.write("# === WL Las de siempre ===\nMU\nGE\n\n# === WL Caras ===\nNVDA\n")
listas = watchlists.leer(ruta_pc)
check(listas[0] == ("Las de siempre", ["MU", "GE"]) and listas[1][1] == ["NVDA"],
      "sin lista propia, arranca con la compartida", f"{listas[:2]}")
antes = open(watchlists._compartida(ruta_pc), encoding="utf-8").read()
watchlists.guardar(listas, ruta_pc)
check(open(watchlists._compartida(ruta_pc), encoding="utf-8").read() == antes,
      "guardar NO toca la compartida (por eso no puede chocar con el repositorio)")
check(os.path.exists(ruta_pc), "y esta PC pasa a tener la suya")

print("\n=== 5. El boton carga la lista, y el bot la lee igual ===")
from PySide6.QtWidgets import QApplication                          # noqa: E402

from tradingbot.gui.control_panel import ControlPanel               # noqa: E402
from tradingbot.gui.watchlists_dialog import DialogoWatchlists      # noqa: E402

app = QApplication.instance() or QApplication([])
ruta_ui = os.path.join(carpeta, "ui.txt")
watchlists.guardar([("Acciones caras", ["AAPL", "MSFT", "NVDA"]),
                    ("ETB del dia", ["MU", "GE"]),
                    ("Sin cargar", [])], ruta_ui)
panel = ControlPanel(ruta_watchlists=ruta_ui)
check(len(panel.btn_wl) == watchlists.CUANTAS and hasattr(panel, "btn_wl_config"),
      f"hay {watchlists.CUANTAS} botones WL y el de la ruedita", f"{len(panel.btn_wl)}")

panel.txt_watchlist.setPlainText("ESCRITO A MANO")
panel.btn_wl[0].click()
check(panel.get_symbols() == ["AAPL", "MSFT", "NVDA"],
      "apretar WL 1 deja la watchlist lista para el bot", f"{panel.get_symbols()}")
panel.btn_wl[1].click()
check(panel.get_symbols() == ["MU", "GE"],
      "y WL 2 la reemplaza, no la suma", f"{panel.get_symbols()}")

# el campo sigue mandando: lo que escribas a mano despues, gana
panel.txt_watchlist.setPlainText("otra cosa")
check(panel.get_symbols() == ["OTRA", "COSA"],
      "el campo sigue siendo el que manda", f"{panel.get_symbols()}")

print("\n=== 6. Una WL vacia no te borra la watchlist ===")
check(panel.btn_wl[2].isEnabled() is False,
      "la vacia queda deshabilitada", f"{panel.btn_wl[2].isEnabled()}")
panel.txt_watchlist.setPlainText("AAPL MSFT")
panel.btn_wl[2].click()
check(panel.get_symbols() == ["AAPL", "MSFT"],
      "y aunque se la apriete, no vacia lo que habia", f"{panel.get_symbols()}")
check(panel.btn_wl[0].isEnabled() and panel.btn_wl[1].isEnabled(),
      "las que tienen simbolos si se pueden apretar")

print("\n=== 7. El nombre esta en la ayuda, aunque el boton diga WL 1 ===")
check(panel.btn_wl[0].text() == "WL 1",
      "el boton dice WL 1 (es lo que entra en la pantalla)", panel.btn_wl[0].text())
check("Acciones caras" in panel.btn_wl[0].toolTip(),
      "y la ayuda dice como la llamaste", panel.btn_wl[0].toolTip().splitlines()[0])
check("3" in panel.btn_wl[0].toolTip() and "AAPL" in panel.btn_wl[0].toolTip(),
      "con cuantos simbolos tiene y una muestra")

print("\n=== 8. 'Tomar la de la pantalla' evita copiar y pegar ===")
panel.txt_watchlist.setPlainText("mu  ge  wing")
dlg = DialogoWatchlists(ruta=ruta_ui, en_pantalla=panel.txt_watchlist.toPlainText())
dlg._tomar(2)                       # el boton de la fila 3
check(dlg.listas()[2][1] == ["MU", "GE", "WING"],
      "copia lo que hay en la pantalla a la WL elegida", f"{dlg.listas()[2]}")
check(dlg.listas()[0][1] == ["AAPL", "MSFT", "NVDA"],
      "y no toca las otras", f"{dlg.listas()[0]}")
dlg.filas[2][0].setText("La de hoy")
watchlists.guardar(dlg.listas(), ruta_ui)
panel._refrescar_wl()
check(panel.btn_wl[2].isEnabled() and "La de hoy" in panel.btn_wl[2].toolTip(),
      "al guardar, el boton se habilita solo y toma el nombre nuevo",
      panel.btn_wl[2].toolTip().splitlines()[0])

# con la pantalla vacia no hay nada que copiar: el boton se apaga, para que no
# se pueda vaciar una lista de un click sin querer
dlg2 = DialogoWatchlists(ruta=ruta_ui, en_pantalla="   ")
check(all(not b.isEnabled() for b in dlg2.btn_tomar),
      "con la pantalla vacia, 'Tomar' queda apagado (no vacia una lista sin querer)",
      f"{[b.isEnabled() for b in dlg2.btn_tomar]}")
check(all(b.isEnabled() for b in dlg.btn_tomar),
      "y con simbolos en la pantalla, encendido")
check(dlg2.listas()[0][1] == ["AAPL", "MSFT", "NVDA"],
      "y las listas guardadas siguen enteras", f"{dlg2.listas()[0]}")

print()
if fallos:
    print(f"PROBLEMAS: {len(fallos)}")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("OK: los botones cargan la watchlist, el campo sigue mandando, y lo que "
      "escribe la app no viaja con el repositorio.")
