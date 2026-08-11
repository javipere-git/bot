"""
Los botones del bot se prenden y apagan segun el estado. No toca dinero ni red.

Lo que tiene que pasar:

    DETENIDO  -> solo Iniciar
    CORRIENDO -> Pausar y Detener
    PAUSADO   -> Reanudar y Detener

Antes, con el bot corriendo, Reanudar quedaba activo (no hacia nada).

Tambien se comprueba lo importante de fondo: que la pantalla se entere cuando el
motor se pausa SOLO (una posicion queda en manual, 'pausar tras operar', o ya
habia una posicion abierta). Si no, los botones quedarian mintiendo.

    python examples/demo_botones_bot.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402


def estado(control) -> dict:
    return {
        "Iniciar": control.btn_iniciar.isEnabled(),
        "Pausar": control.btn_pausar.isEnabled(),
        "Reanudar": control.btn_reanudar.isEnabled(),
        "Detener": control.btn_detener.isEnabled(),
    }


def mostrar(titulo, real, esperado) -> bool:
    ok = real == esperado
    activos = [k for k, v in real.items() if v] or ["ninguno"]
    print(f"  {'OK ' if ok else '***'} {titulo:32} activos: {', '.join(activos)}")
    if not ok:
        print(f"        esperaba: {[k for k, v in esperado.items() if v]}")
    return ok


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    from tradingbot.gui.main_window import MainWindow
    from tradingbot.gui.perfiles import Perfil

    perfil = Perfil(id="demo", broker_nombre="Falso", cuenta_texto="PAPER",
                    es_live=False, _crear_broker=lambda: FakeBroker())
    win = MainWindow(perfil)
    c = win.control
    todo = True

    print("=== ESTADOS DE LOS BOTONES ===")
    todo &= mostrar("DETENIDO (recien abierta)", estado(c),
                    {"Iniciar": True, "Pausar": False, "Reanudar": False,
                     "Detener": False})

    win._set_running(True)
    todo &= mostrar("CORRIENDO", estado(c),
                    {"Iniciar": False, "Pausar": True, "Reanudar": False,
                     "Detener": True})

    win._set_running(True, pausado=True)
    todo &= mostrar("PAUSADO", estado(c),
                    {"Iniciar": False, "Pausar": False, "Reanudar": True,
                     "Detener": True})

    win._set_running(True, pausado=False)
    todo &= mostrar("REANUDADO (vuelve a correr)", estado(c),
                    {"Iniciar": False, "Pausar": True, "Reanudar": False,
                     "Detener": True})

    win._set_running(False)
    todo &= mostrar("DETENIDO otra vez", estado(c),
                    {"Iniciar": True, "Pausar": False, "Reanudar": False,
                     "Detener": False})

    # ---- el motor avisa cuando se pausa SOLO ----
    print("\n=== EL MOTOR AVISA SUS PROPIAS PAUSAS ===")
    avisos: list[bool] = []
    cfg = EngineConfig(side=Side.BUY, quantity=1,
                       order1=OrderConfig(offset=0.0, unit=OffsetUnit.DOLLARS,
                                          timeout_s=1.0))
    motor = BotEngine(FakeBroker(), cfg, log=lambda m: None,
                      on_pausa=avisos.append)
    motor.pause()
    motor.resume()
    motor.pause()
    bien = avisos == [True, False, True]
    print(f"  {'OK ' if bien else '***'} pause()/resume() avisan a la pantalla: {avisos}")
    todo &= bien

    win.close()
    print("\nOK: los botones reflejan el estado real del bot." if todo
          else "\n*** FALLO en algun estado.")
    return 0 if todo else 1


if __name__ == "__main__":
    sys.exit(main())
