"""
Prueba el REPORTE DE PASADA de punta a punta (no toca dinero: conector de mentira).

Arma una watchlist donde:
  - una accion pasa todos los filtros y ENTRA con la Orden 1, y CIERRA en el nivel 1,
  - varias se saltean, cada una por un filtro distinto (spread, volumen, spread%precio).
Despues confirma que el reporte conto bien cada cosa y arma el texto sin romperse.

    python examples/demo_reporte_pasada.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import (  # noqa: E402
    EngineConfig,
    ExitLevel,
    OffsetUnit,
    OrderConfig,
)
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402
from tradingbot.core.reporte import render_pasada, render_resumen_dia  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def main() -> int:
    broker = FakeBroker()
    # BUENA: spread 0.10 sobre 100 (0.10%), volumen ok -> entra con Orden 1 y cierra nivel 1
    broker.set_quote("BUENA", 100.00, 100.10, volume=50_000)
    # CARA_SPREAD: spread 0.60 -> supera el spread maximo (0.30)
    broker.set_quote("ANCHA", 100.00, 100.60, volume=50_000)
    # POCO_VOL: volumen 100 por debajo del minimo (1000)
    broker.set_quote("SECA", 100.00, 100.10, volume=100)
    # ILIQUIDA: spread 0.20 sobre 1.10 = 18% del precio -> supera el 5%
    broker.set_quote("CHICA", 1.00, 1.20, volume=50_000)

    cfg = EngineConfig(
        side=Side.BUY,
        quantity=10,
        # entra al ask: offset 0.10 = bid + 0.10 -> se llena al instante
        order1=OrderConfig(offset=0.10, unit=OffsetUnit.DOLLARS, timeout_s=1.0),
        order2=None,
        spread_max=0.30,
        volume_min=1_000,
        max_spread_pct_precio=5.0,
        # una salida: cruzar el spread -> cierra al instante en el nivel 1
        exit_levels=[ExitLevel(offset=0.0, unit=OffsetUnit.DOLLARS, timeout_s=1.0,
                               cross=True)],
        loop_watchlist=False,
        pause_on_fill=False,
    )

    engine = BotEngine(broker, cfg, clock=FakeClock(), log=lambda m: None)
    engine.run_watchlist(["ANCHA", "SECA", "CHICA", "BUENA"])
    rep = engine.reporte
    rep.fin = rep.inicio + 12      # simulo 12s de pasada para el texto
    rep.neto = 3.45                # simulo el neto que pondria la pantalla
    rep.neto_disponible = True

    print("== conteos ==")
    print("entradas Orden 1:", rep.llenados_orden1)
    print("salidas por nivel:", dict(rep.salidas_por_nivel), "cruzar:", rep.salidas_cruzar)
    print("filtros:", dict(rep.filtros))
    print()

    checks = {
        "entro 1 con Orden 1": rep.llenados_orden1 == 1,
        "0 con Orden 2": rep.llenados_orden2 == 0,
        "cerro 1 en el nivel 1": rep.salidas_por_nivel.get(1) == 1,
        "esa salida fue cruzando": rep.salidas_cruzar == 1,
        "salteo 1 por spread maximo": rep.filtros.get("spread_max") == 1,
        "salteo 1 por volumen dia min": rep.filtros.get("volumen_dia_min") == 1,
        "salteo 1 por spread % precio": rep.filtros.get("spread_pct_precio") == 1,
    }
    ok = all(checks.values())
    for nombre, paso in checks.items():
        print(f"  {'OK ' if paso else '*** FALLO'} {nombre}")

    # que el texto se arme sin romperse
    texto = render_pasada(rep)
    resumen = render_resumen_dia([rep, rep])
    assert "REPORTE DE PASADA" in texto and "Neto de la pasada: +3.45" in texto
    assert "RESUMEN DEL DIA" in resumen
    print("\n----- ejemplo de reporte -----")
    print(texto)

    print("OK: el reporte de pasada funciona." if ok else "*** FALLO en algun conteo.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
