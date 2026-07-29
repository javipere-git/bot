"""Verifica que TODAS las tablas de la app tengan columnas ajustables y movibles."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.gui.main_window import MainWindow  # noqa: E402
from tradingbot.gui.perfiles import perfil_por_defecto  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    w = MainWindow(perfil_por_defecto())
    tablas = [
        ("monitor: posiciones", w.monitor.tbl_pos),
        ("monitor: abiertas", w.monitor.tbl_ord),
        ("monitor: ejecutadas", w.monitor.tbl_exec),
        ("monitor: canceladas", w.monitor.tbl_canc),
        ("ladder", w.ladder.tabla),
        ("Time & Sales", w.tape.tabla),
    ]
    todo = True
    for nombre, t in tablas:
        cab = t.horizontalHeader()
        ajustable = "Interactive" in str(cab.sectionResizeMode(0))
        movible = cab.sectionsMovable()
        ok = ajustable and movible
        todo = todo and ok
        print(f"  {'OK ' if ok else '***'} {nombre:22} ancho ajustable={ajustable}  "
              f"columnas movibles={movible}")
    print()
    print(f"tilde 'Ext. hours' en el ladder: {w.ladder.chk_ext.isChecked()} "
          f"(destildado por defecto = comportamiento de siempre)")
    print("\nOK: todas las columnas se pueden ajustar y arrastrar."
          if todo else "\n*** FALTA alguna tabla.")


if __name__ == "__main__":
    main()
