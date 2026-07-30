"""
El GUARDIA sigue vigilando aunque el cierre automatico este DESACTIVADO.

El agujero que arregla: si no tenias niveles de salida activos, el motor pasaba a
manual y ahi se quedaba esperando, SIN mirar el precio. El guardia vivia dentro del
ciclo de los niveles de salida, asi que nunca corria. Tenias la alarma tildada y no
te protegia.

Ahora, mientras espera que cierres a mano y aprietes Reanudar, el guardia sigue
mirando: si el precio se corre en contra del umbral, suena la alarma igual.

NO opera nunca: sin cierre automatico configurado, el motor no manda ordenes por su
cuenta. Solo avisa.

    python examples/demo_guardia_vigilando.py
"""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import (  # noqa: E402
    EngineConfig,
    GuardAction,
    GuardConfig,
    GuardUnit,
    OrderConfig,
    OffsetUnit,
)
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import Position, Side  # noqa: E402


def _armar(broker, bid, ask):
    """Motor SIN niveles de salida (cierre automatico destildado) y CON guardia."""
    avisos = []
    cfg = EngineConfig(
        quantity=10,
        side=Side.BUY,
        order1=OrderConfig(offset=50, unit=OffsetUnit.PERCENT_SPREAD, timeout_s=5),
        order2=OrderConfig(offset=50, unit=OffsetUnit.PERCENT_SPREAD, timeout_s=5),
        exit_levels=[],                        # <-- cierre automatico DESTILDADO
        guard=GuardConfig(enabled=True, threshold=0.30, unit=GuardUnit.DOLLARS,
                          action=GuardAction.MANUAL),
        poll_interval_s=0.05,
    )
    motor = BotEngine(broker, cfg, log=print,
                      on_manual=lambda sym, por_guardia: avisos.append((sym, por_guardia)))
    return motor, avisos


def main() -> None:
    print("=" * 70)
    print("CASO 1: el precio se corre en contra mientras esta en manual")
    print("=" * 70)
    b = FakeBroker()
    b.set_quote("AAPL", bid=100.00, ask=100.10)
    motor, avisos = _armar(b, 100.00, 100.10)
    motor._entry_ref = 100.00                     # referencia: precio de la entrada
    pos = Position("AAPL", quantity=10, avg_price=100.05)
    b._positions["AAPL"] = pos                    # el motor le pregunta al broker

    resultado = motor.manage_exit(pos)
    print(f"\nresultado: {resultado}  (pasa a manual, como siempre)")

    # la vigilancia corre en un hilo, como pasa en la app mientras espera Reanudar
    motor.pause()
    hilo = threading.Thread(target=motor._vigilar_en_manual, args=("AAPL", pos), daemon=True)
    hilo.start()
    time.sleep(0.3)
    print(f"\nalertas hasta ahora: {len(avisos)}  (el precio no se movio)")
    sin_mover = len(avisos)

    print("\n>>> el bid se DESPLOMA de 100.00 a 99.60 (0.40 en contra, umbral 0.30)")
    b.set_quote("AAPL", bid=99.60, ask=99.70)
    time.sleep(0.6)
    con_alerta = len(avisos)
    print(f"alertas ahora: {con_alerta}")
    ok1 = sin_mover == 0 and con_alerta == 1 and avisos[0] == ("AAPL", True)
    print(f"-> {'OK: salto la alarma estando ya en manual' if ok1 else '*** FALLO'}")

    print("\n>>> sigue cayendo: la alarma NO se repite en bucle")
    b.set_quote("AAPL", bid=99.00, ask=99.10)
    time.sleep(0.4)
    ok2 = len(avisos) == 1
    print(f"alertas: {len(avisos)} (esperado 1)")
    print(f"-> {'OK' if ok2 else '*** FALLO: alarma repetida'}")

    motor.resume()
    hilo.join(timeout=2)

    print("\n" + "=" * 70)
    print("CASO 2: si cerras la posicion a mano, deja de vigilar")
    print("=" * 70)
    b2 = FakeBroker()
    b2.set_quote("MSFT", bid=200.00, ask=200.10)
    motor2, avisos2 = _armar(b2, 200.00, 200.10)
    motor2._entry_ref = 200.00
    pos2 = Position("MSFT", quantity=10, avg_price=200.05)
    b2._positions["MSFT"] = pos2
    motor2.manage_exit(pos2)
    motor2.pause()
    hilo2 = threading.Thread(target=motor2._vigilar_en_manual, args=("MSFT", pos2), daemon=True)
    hilo2.start()
    time.sleep(0.3)
    print(">>> cerras la posicion a mano y el precio se desploma")
    b2._positions.clear()                         # posicion cerrada por el usuario
    b2.set_quote("MSFT", bid=199.00, ask=199.10)
    time.sleep(0.5)
    ok3 = len(avisos2) == 0
    print(f"alertas: {len(avisos2)} (esperado 0: ya no hay nada que vigilar)")
    print(f"-> {'OK' if ok3 else '*** FALLO: alerto sin posicion'}")
    motor2.resume()
    hilo2.join(timeout=2)

    print("\n" + "=" * 70)
    print("CASO 3: sin guardia tildado, se comporta como antes (no vigila)")
    print("=" * 70)
    b3 = FakeBroker()
    b3.set_quote("F", bid=10.00, ask=10.05)
    cfg = EngineConfig(
        quantity=10, side=Side.BUY,
        order1=OrderConfig(offset=50, unit=OffsetUnit.PERCENT_SPREAD, timeout_s=5),
        order2=OrderConfig(offset=50, unit=OffsetUnit.PERCENT_SPREAD, timeout_s=5),
        exit_levels=[], guard=None, poll_interval_s=0.05,
    )
    avisos3 = []
    m3 = BotEngine(b3, cfg, log=print,
                   on_manual=lambda s, p: avisos3.append((s, p)))
    pos3 = Position("F", quantity=10, avg_price=10.02)
    b3._positions["F"] = pos3
    m3.manage_exit(pos3)
    m3.pause()
    h3 = threading.Thread(target=m3._vigilar_en_manual, args=("F", pos3), daemon=True)
    h3.start()
    time.sleep(0.2)
    b3.set_quote("F", bid=9.00, ask=9.05)
    time.sleep(0.3)
    ok4 = len(avisos3) == 0
    print(f"alertas: {len(avisos3)} (esperado 0: no configuraste guardia)")
    print(f"-> {'OK' if ok4 else '*** FALLO'}")
    m3.resume()
    h3.join(timeout=2)

    print("\n" + "=" * 70)
    print("OK: el guardia vigila en manual, sin repetir la alarma, sin operar solo."
          if (ok1 and ok2 and ok3 and ok4) else "*** HAY FALLOS.")


if __name__ == "__main__":
    main()
