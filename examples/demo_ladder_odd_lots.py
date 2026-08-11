"""
El sondeo por REST no puede pisar al streaming. No toca dinero ni red.

EL PROBLEMA QUE ARREGLA: con Tastytrade, los ODD LOTS aparecian un momento en el
ladder y despues se iban.

Por que pasaba: el ladder recibia precios de DOS fuentes a la vez.
  - el STREAMING, que en Tastytrade trae los tamanos reales (con odd lots),
  - y el SONDEO POR REST del monitoreo, cada pocos segundos, que informa los
    tamanos REDONDEADOS AL LOTE (multiplos de 40 o 100).
Como la segunda pisaba a la primera, los odd lots duraban lo que tardaba el
proximo sondeo.

El REST sigue haciendo falta: en acciones poco liquidas el streaming solo manda
datos cuando el precio CAMBIA, y sin el respaldo la escalera puede quedar vacia
minutos. Por eso no se saca, pero entra SOLO en dos casos: cuando todavia no
llego ninguna del streaming para ese simbolo (la foto inicial) y cuando el
streaming esta CAIDO.

OJO con el criterio: NO se decide por tiempo. Una cotizacion no vence porque el
mercado este quieto -- sigue siendo la verdad hasta que llegue otra. Medido en
CHCI: 1 mensaje de streaming cada ~100 segundos, y la cotizacion seguia buena.

Y no es solo cuestion de tamanos: el REST informa un mercado PEOR. Medido en
AGYS, en el mismo instante: streaming 107.87 x 108.18, REST 107.74 x 108.34.

    python examples/demo_ladder_odd_lots.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.gui.ladder_panel import LadderPanel  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    broker = FakeBroker()
    broker.set_quote("AAPL", bid=306.17, ask=306.18)
    l = LadderPanel(broker_provider=lambda: broker, log=lambda m: None)
    l.ed_symbol.setText("AAPL")
    l._cambiar_symbol()

    checks = {}

    # --- 1) llega el streaming con ODD LOTS (27 y 42: no son multiplos de 40) ---
    l.set_stream_vivo(lambda: True)
    l.actualizar_quote("AAPL", 306.17, 306.18, 27, 42)
    checks["el streaming se muestra"] = l._last == (306.17, 306.18, 27, 42)
    print(f"  streaming        -> bid x{l._last[2]}  ask x{l._last[3]}")

    # --- 2) enseguida llega el sondeo REST con los tamanos redondeados ---
    l.actualizar_quote_rest("AAPL", 306.14, 306.21, 400, 200)
    tras_rest = l._last
    checks["el REST NO pisa al streaming"] = tras_rest == (306.17, 306.18, 27, 42)
    print(f"  + sondeo REST    -> bid x{tras_rest[2]}  ask x{tras_rest[3]}"
          f"   (antes quedaba en 400/200 y se perdian los odd lots)")

    # --- 3) EL CASO REAL: el streaming se calla un rato LARGO ---
    # En CHCI se midio 1 mensaje cada ~100 segundos. Aun asi la cotizacion del
    # streaming SIGUE SIENDO VALIDA: no vence porque el mercado este quieto.
    for _ in range(20):                       # 20 sondeos seguidos (mas de un minuto)
        l.actualizar_quote_rest("AAPL", 306.14, 306.21, 400, 200)
    checks["aunque el streaming calle 20 sondeos, no lo pisa"] = \
        l._last == (306.17, 306.18, 27, 42)
    print(f"  20 sondeos mas   -> bid x{l._last[2]}  ask x{l._last[3]}"
          f"   (este era el bug: aca se perdian)")

    # --- 4) si el streaming SE CAE, el respaldo tiene que entrar ---
    vivo = {"ok": True}
    l.set_stream_vivo(lambda: vivo["ok"])
    vivo["ok"] = False
    l.actualizar_quote_rest("AAPL", 306.20, 306.22, 400, 200)
    checks["si el streaming se CAE, el REST entra"] = l._last == (306.20, 306.22, 400, 200)
    print(f"  streaming CAIDO  -> bid x{l._last[2]}  ask x{l._last[3]}"
          f"   (el respaldo hace su trabajo)")

    # --- 5) y cuando el streaming vuelve, manda el streaming otra vez ---
    vivo["ok"] = True
    l.actualizar_quote("AAPL", 306.21, 306.23, 9, 19)
    checks["cuando vuelve el streaming, manda el streaming"] = \
        l._last == (306.21, 306.23, 9, 19)
    print(f"  vuelve streaming -> bid x{l._last[2]}  ask x{l._last[3]}")

    # --- 6) simbolo nuevo: el respaldo da la foto inicial ---
    broker.set_quote("MSFT", bid=500.00, ask=500.40)
    l.ed_symbol.setText("MSFT")
    l._cambiar_symbol()
    l.actualizar_quote_rest("MSFT", 500.00, 500.40, 400, 200)
    checks["en un simbolo nuevo, el REST da la foto inicial"] = \
        l._last == (500.00, 500.40, 400, 200)
    print(f"  simbolo nuevo    -> bid x{l._last[2]}  ask x{l._last[3]}"
          f"   (si no, la escalera quedaria vacia)")

    print()
    for nombre, ok in checks.items():
        print(f"  {'OK ' if ok else '*** FALLO'} {nombre}")
    todo = all(checks.values())
    l.detener()      # cortar el hilo del ladder antes de salir
    print("\nOK: el streaming manda y el REST queda de respaldo." if todo
          else "\n*** FALLO: el REST sigue pisando al streaming.")
    return 0 if todo else 1


if __name__ == "__main__":
    sys.exit(main())
