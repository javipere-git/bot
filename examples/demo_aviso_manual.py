"""
Prueba el AVISO "queda a mano" (no toca dinero: conector de mentira).

Cuando el bot deja una posicion para que la cierres vos (el guardia se disparo, o
los niveles de salida no cerraron), avisa el simbolo. La pantalla usa ese aviso
para cargar el simbolo en el ladder sola.

Confirma que avisa SOLO en esos dos casos (y no cuando cerro bien), y que si la
pantalla falla, el bot no se cae.

    python examples/demo_aviso_manual.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine, Outcome  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402


def _config() -> EngineConfig:
    return EngineConfig(
        side=Side.BUY,
        quantity=10,
        order1=OrderConfig(offset=0.0, unit=OffsetUnit.DOLLARS, timeout_s=1.0),
    )


def main() -> None:
    avisos: list[tuple[str, bool]] = []
    engine = BotEngine(FakeBroker(), _config(), log=lambda m: None,
                       on_manual=lambda s, g: avisos.append((s, g)))

    casos = [
        (Outcome.MANUAL_GUARD, "GUARDIA", True, "el guardia paso a manual"),
        (Outcome.MANUAL_NO_EXIT, "SINSALIDA", True, "los niveles no cerraron"),
        (Outcome.CLOSED, "CERRADA", False, "cerro sola: no hace falta el ladder"),
        (Outcome.ABORTED, "ABORTADA", False, "freno por errores del broker"),
    ]

    todo_ok = True
    for outcome, sym, espera_aviso, por_que in casos:
        antes = len(avisos)
        engine._announce(outcome, sym)
        hubo = len(avisos) > antes
        ok = hubo == espera_aviso
        todo_ok = todo_ok and ok
        print(
            f"{'OK  ' if ok else '*** FALLO'}: {outcome.value:15} ({por_que})\n"
            f"      -> carga el ladder: {hubo}  (esperado {espera_aviso})"
        )

    esperado = [("GUARDIA", True), ("SINSALIDA", False)]  # (simbolo, fue_el_guardia)
    print(f"\nAvisos al ladder: {avisos}   (esperado: {esperado})")
    todo_ok = todo_ok and avisos == esperado

    # Si la pantalla llegara a fallar, el bot NO se cae por eso.
    def explota(_sym, _por_guardia):
        raise RuntimeError("la pantalla fallo")

    roto = BotEngine(FakeBroker(), _config(), log=lambda m: None, on_manual=explota)
    try:
        roto._announce(Outcome.MANUAL_GUARD, "BOOM")
        print("OK  : un error al avisar a la pantalla NO frena al bot.")
    except Exception as e:  # noqa: BLE001
        todo_ok = False
        print(f"*** FALLO: el error de la pantalla rompio el bot: {e}")

    print("\nOK: el aviso a mano funciona." if todo_ok else "\n*** HAY FALLOS.")


if __name__ == "__main__":
    main()
