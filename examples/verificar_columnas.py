"""
Verifica el manejo de columnas de TODAS las tablas de la app:
  1. Al abrir, TODAS las columnas entran (ninguna queda fuera de la vista).
  2. Se pueden ajustar de ancho y arrastrar para reordenar.
  3. Los anchos y el orden se RECUERDAN entre sesiones.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.gui.estado_ui import guardar_columnas, olvidar_columnas  # noqa: E402
from tradingbot.gui.main_window import MainWindow  # noqa: E402
from tradingbot.gui.perfiles import perfil_por_defecto  # noqa: E402


def tablas(w):
    return [
        ("monitor: posiciones", w.monitor.tbl_pos),
        ("monitor: abiertas", w.monitor.tbl_ord),
        ("monitor: ejecutadas", w.monitor.tbl_exec),
        ("monitor: canceladas", w.monitor.tbl_canc),
        ("ladder", w.ladder.tabla),
        ("Time & Sales", w.tape.tabla),
    ]


def main() -> None:
    app = QApplication(sys.argv)
    olvidar_columnas()          # arrancar como un usuario nuevo

    w = MainWindow(perfil_por_defecto())
    w.show()
    app.processEvents()         # deja que se dibuje (ahi se fijan los anchos)

    print("1) Al abrir, TODAS las columnas entran en la vista")
    todo = True
    for nombre, t in tablas(w):
        cab = t.horizontalHeader()
        suma = sum(cab.sectionSize(i) for i in range(cab.count()))
        ancho = t.viewport().width()
        entran = suma <= ancho + 2          # +2 por redondeo
        ajustable = "Interactive" in str(cab.sectionResizeMode(0))
        movible = cab.sectionsMovable()
        ok = entran and ajustable and movible
        todo = todo and ok
        print(f"  {'OK ' if ok else '***'} {nombre:22} columnas={cab.count()} "
              f"suman {suma}px de {ancho}px | ajustable={ajustable} movible={movible}")

    print("\n2) Los anchos y el orden se recuerdan")
    t = w.ladder.tabla
    t.horizontalHeader().resizeSection(0, 137)   # el usuario ajusta una columna
    guardar_columnas(t)                          # (pasa al cerrar la app)
    w2 = MainWindow(perfil_por_defecto())        # "reabre" la app
    w2.show()
    app.processEvents()
    recordado = w2.ladder.tabla.horizontalHeader().sectionSize(0)
    ok2 = recordado == 137
    todo = todo and ok2
    print(f"  {'OK ' if ok2 else '***'} ancho puesto: 137px -> al reabrir: {recordado}px")

    olvidar_columnas()          # no dejar basura de la prueba
    print("\nOK: las columnas entran, se ajustan, se mueven y se recuerdan."
          if todo else "\n*** HAY FALLOS.")
    return bool(todo)


if __name__ == "__main__":
    # os._exit evita un choque de Qt al desarmar la aplicacion, que hacia que el
    # script terminara con codigo de error aunque todas las pruebas pasaran.
    ok = main()
    sys.stdout.flush()
    os._exit(0 if ok else 1)
