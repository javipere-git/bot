"""
Genera una imagen PNG de la ventana (para control de calidad visual), sin
necesidad de una pantalla real. Uso interno de desarrollo.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.gui.main_window import MainWindow  # noqa: E402
from tradingbot.core.models import Order, OrderStatus, Position, Side  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow(mode="paper")
    win.resize(1200, 720)
    win.show()
    win.ladder.ed_symbol.setText("TEST")
    win.ladder._cambiar_symbol()
    win.ladder.set_positions([Position("TEST", 10, 100.02)])
    win.ladder.set_orders([Order(id="1", symbol="TEST", side=Side.BUY,
                                 quantity=10, price=99.99, status=OrderStatus.OPEN)])
    win.ladder.actualizar_quote("TEST", 100.00, 100.05, 300, 200)
    for _ in range(5):
        app.processEvents()
    out = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "_captura_esqueleto.png",
    )
    win.grab().save(out)
    print("captura guardada en:", out)
    win.close()


if __name__ == "__main__":
    main()
