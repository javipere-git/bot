"""
Smoke test de la pantalla: construye la ventana y la cierra enseguida.

Sirve para confirmar que la ventana ARRANCA sin errores, sin necesidad de una
pantalla real (se corre en modo invisible 'offscreen'). La ventana de verdad
la ves con:  python examples/correr_app.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.gui.main_window import MainWindow  # noqa: E402
from tradingbot.gui.perfiles import perfil_por_defecto  # noqa: E402
from tradingbot.core.models import Order, OrderStatus, Position, Side  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow(perfil_por_defecto())
    win.show()

    # verificar la lectura de configuracion del panel (sin arrancar el bot)
    win.control.txt_watchlist.setPlainText("MU, GE  wing")
    win.control.grp_cierre.setChecked(True)
    win.control.exit_rows[0]["on"].setChecked(True)
    win.control.exit_rows[1]["on"].setChecked(True)
    win.control.exit_rows[1]["cross"].setChecked(True)  # deberia deshabilitar el resto
    win.control.grp_guard.setChecked(True)
    win.control.ed_spread_min.setText("0.02")
    win.control.ed_vol_min.setText("1000")
    win.control.ed_vol_max.setText("100.000")   # escrito "a la argentina"
    syms = win.control.get_symbols()
    cfg = win.control.build_config()
    print("symbols:", syms)
    print(
        f"config OK -> lado {cfg.side.value}, cant {cfg.quantity}, "
        f"niveles salida {len(cfg.exit_levels)}, guardia {cfg.guard is not None}"
    )
    print(f"filtros -> spread min {cfg.spread_min} | volumen {cfg.volume_min} a "
          f"{cfg.volume_max} (esperado 1000 a 100000)")
    print(f"guardia referencia: {cfg.guard.reference.value} (esperado entry_calc)")
    nivel3_off = win.control.exit_rows[2]["off"].isEnabled()
    print(f"nivel 3 deshabilitado tras 'cruzar' en nivel 2: {not nivel3_off}")

    win.ladder.ed_symbol.setText("TEST")
    win.ladder._cambiar_symbol()
    win.ladder.set_positions([Position("TEST", 10, 100.02)])
    win.ladder.set_orders([Order(id="1", symbol="TEST", side=Side.BUY,
                                 quantity=10, price=99.99, status=OrderStatus.OPEN)])
    win.ladder.actualizar_quote("TEST", 100.00, 100.05, 300, 200)
    win.ladder._repintar()  # el repintado real es throttleado (timer); lo forzamos para el test
    print("ladder filas:", win.ladder.tabla.rowCount())
    print("NBBO display:", win.ladder.lbl_bid.text(), "/", win.ladder.lbl_ask.text())
    print("conexion header:", win.lbl_conexion.text())

    win.monitor.set_orders([Order(id="10", symbol="AAA", side=Side.BUY, quantity=10,
                                  price=100.0, status=OrderStatus.OPEN,
                                  create_date="2026-07-01T14:30:05.000Z")])
    win.monitor.set_closed_orders([Order(id="11", symbol="BBB", side=Side.SELL, quantity=5,
                                         price=50.0, status=OrderStatus.FILLED,
                                         avg_fill_price=50.0,
                                         transaction_date="2026-07-01T14:31:09.000Z")])
    print("monitor -> abiertas:", win.monitor.tbl_ord.rowCount(),
          "hora:", win.monitor.tbl_ord.item(0, 0).text(),
          "| ejecutadas:", win.monitor.tbl_exec.rowCount())
    win.ladder._zoom_out()
    win.ladder._zoom_out()
    print("ladder filas tras zoom out x2:", win.ladder.tabla.rowCount())

    # el re-centrado solo debe ocurrir si cambia el NBBO (o con el boton Centrar)
    llamadas = []
    win.ladder.tabla.scrollToItem = lambda *a, **k: llamadas.append(1)
    win.ladder.actualizar_quote("TEST", 100.00, 100.05, 999, 999); win.ladder._repintar()  # mismo NBBO
    igual = len(llamadas)
    win.ladder.actualizar_quote("TEST", 100.10, 100.15, 300, 200); win.ladder._repintar()  # NBBO cambio
    cambio = len(llamadas) - igual
    win.ladder._centrar()
    boton = len(llamadas) - igual - cambio
    print(f"recentrados -> mismo NBBO: {igual} (esperado 0) | NBBO cambio: {cambio} "
          f"(esperado 1) | boton Centrar: {boton} (esperado 1)")

    # el bot deja una posicion para cerrar a mano -> el ladder la carga solo
    # (por_guardia=False para no abrir el cartel modal de la alarma en el smoke)
    win._on_manual("NVDA", False)
    print(f"ladder tras 'paso a manual': {win.ladder.symbol()} (esperado NVDA)")
    print(f"alarma del guardia tildada por defecto: "
          f"{win.control.chk_guard_alarma.isChecked()} (esperado True)")

    QTimer.singleShot(500, win.close)
    app.exec()
    print("OK: la ventana se construyo y la configuracion se leyo sin errores.")


if __name__ == "__main__":
    main()
