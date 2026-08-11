"""
El guardia avisa UNA SOLA VEZ (no dos carteles). No toca dinero: broker de mentira.

EL PROBLEMA QUE ARREGLA: con el cierre automatico activado, cuando el guardia
saltaba salian DOS carteles y habia que aceptar los dos para apagar la alarma.

Por que pasaba: el guardia dispara dentro del cierre escalonado -> la salida
termina en MANUAL_GUARD -> se avisa (alarma 1). Enseguida el motor se queda
vigilando en manual y, como el precio SIGUE corrido, el chequeo de ahi disparaba
al instante (alarma 2).

Sin cierre automatico no pasaba: ahi el guardia nunca llega a dispararse dentro
de la salida, asi que solo avisa el vigilante de manual (un solo cartel).

Este demo comprueba las dos cosas: que con cierre automatico ahora avisa UNA vez,
y que SIN cierre automatico el guardia sigue avisando igual que siempre (no se
rompio la pieza mas importante del bot).

    python examples/demo_guardia_una_alarma.py
"""
from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import (  # noqa: E402
    EngineConfig,
    ExitLevel,
    GuardAction,
    GuardConfig,
    GuardUnit,
    OffsetUnit,
    OrderConfig,
)
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def correr(con_cierre_automatico: bool) -> list[tuple[str, bool]]:
    """Entra en una posicion y hace que el precio se derrumbe: el guardia salta.
    Devuelve la lista de avisos (simbolo, fue_el_guardia)."""
    broker = FakeBroker()
    broker.set_quote("AAPL", 100.00, 100.10, volume=50_000)

    avisos: list[tuple[str, bool]] = []

    salidas = []
    if con_cierre_automatico:
        # un nivel de salida que NO se llena (asi el bot entra al escalonado y el
        # guardia tiene ocasion de dispararse ahi adentro)
        salidas = [ExitLevel(offset=5.0, unit=OffsetUnit.DOLLARS, timeout_s=1.0)]

    cfg = EngineConfig(
        side=Side.BUY,
        quantity=10,
        order1=OrderConfig(offset=0.10, unit=OffsetUnit.DOLLARS, timeout_s=1.0),
        order2=None,
        exit_levels=salidas,
        guard=GuardConfig(threshold=0.20, unit=GuardUnit.DOLLARS,
                          action=GuardAction.MANUAL, enabled=True),
        loop_watchlist=False,
        pause_on_fill=False,
    )

    engine = BotEngine(
        broker, cfg, clock=FakeClock(), log=lambda m: None,
        on_manual=lambda sym, guardia: avisos.append((sym, guardia)),
    )

    # apenas entra en posicion, el precio se DERRUMBA -> el guardia tiene que saltar
    original = broker.get_positions

    def posiciones_y_derrumbe():
        pos = original()
        if pos:
            broker.set_quote("AAPL", 95.00, 95.10, volume=50_000)
        return pos

    broker.get_positions = posiciones_y_derrumbe

    # el motor queda esperando a que el usuario reanude: lo hacemos desde afuera
    def reanudar_despues():
        import time as _t
        _t.sleep(1.5)
        engine.resume()
        _t.sleep(0.3)
        engine.stop()

    threading.Thread(target=reanudar_despues, daemon=True).start()
    engine.run_watchlist(["AAPL"])
    return avisos


def main() -> int:
    print("=== CON cierre automatico (el caso que fallaba) ===")
    con = correr(True)
    alarmas_con = [a for a in con if a[1]]
    print(f"  avisos del guardia: {len(alarmas_con)}  -> {con}")

    print("\n=== SIN cierre automatico (tiene que seguir avisando igual) ===")
    sin = correr(False)
    alarmas_sin = [a for a in sin if a[1]]
    print(f"  avisos del guardia: {len(alarmas_sin)}  -> {sin}")

    print()
    checks = {
        "con cierre automatico: UNA sola alarma (antes eran 2)": len(alarmas_con) == 1,
        "sin cierre automatico: el guardia SIGUE avisando": len(alarmas_sin) >= 1,
        "sin cierre automatico: tampoco se duplica": len(alarmas_sin) == 1,
    }
    for nombre, ok in checks.items():
        print(f"  {'OK ' if ok else '*** FALLO'} {nombre}")

    todo = all(checks.values())
    print("\nOK: el guardia avisa una sola vez y sigue funcionando." if todo
          else "\n*** FALLO: revisar el guardia.")
    return 0 if todo else 1


if __name__ == "__main__":
    sys.exit(main())
