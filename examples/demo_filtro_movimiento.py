"""
Filtro de MOVIMIENTO del bid/ask: saltear las acciones nerviosas.

Idea: antes de entrarle a una accion importa saber si esta quieta o si el precio se
mueve todo el tiempo. No la magnitud, sino CUANTAS VECES se movio el bid o el ask en
los ultimos segundos.

Lo que se verifica aca:
  1. Cuenta solo cambios de PRECIO (si cambia el tamano, no cuenta).
  1b. Cuenta el BID y el ASK por SEPARADO (cada uno con su tope y su ventana).
  2. VENTANA DESLIZANTE: mide los ultimos X segundos contados desde AHORA, o sea
     justo antes de operar ese simbolo. Si el bot llega al simbolo 30 a las 12:20:00
     con ventana de 30s, mira desde las 12:19:30, NO desde que arranco la watchlist.
  3. Deja pasar el que esta quieto y saltea el nervioso.
  4. Si todavia no hay ventana completa (recien arranco), ESPERA lo que falte.

    python examples/demo_filtro_movimiento.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import (  # noqa: E402
    EngineConfig,
    OffsetUnit,
    OrderConfig,
)
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402
from tradingbot.core.observador_movimiento import ObservadorMovimiento  # noqa: E402


class RelojFalso:
    """Reloj controlable, para simular que pasan minutos sin esperarlos."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s


def main() -> None:
    reloj = RelojFalso()

    print("=" * 72)
    print("1) Cuenta cambios de PRECIO, no de tamano")
    print("=" * 72)
    obs = ObservadorMovimiento(ahora=reloj)
    obs.anotar("AAPL", 100.00, 100.50)
    obs.anotar("AAPL", 100.00, 100.50)          # mismo precio -> no cuenta
    obs.anotar("AAPL", 100.00, 100.50)
    solo_tamano = obs.cambios_bid("AAPL", 30) + obs.cambios_ask("AAPL", 30)
    obs.anotar("AAPL", 100.10, 100.60)          # cambio de precio -> cuenta
    obs.anotar("AAPL", 100.20, 100.70)
    con_precio = obs.cambios_bid("AAPL", 30)
    ok1 = solo_tamano == 0 and con_precio == 2
    print(f"   3 quotes con el MISMO precio -> {solo_tamano} cambios (esperado 0)")
    print(f"   +2 quotes con precio distinto -> {con_precio} cambios (esperado 2)")
    print(f"   -> {'OK' if ok1 else '*** FALLO'}\n")

    print("=" * 72)
    print("1b) El BID y el ASK se cuentan POR SEPARADO")
    print("=" * 72)
    obs = ObservadorMovimiento(ahora=reloj)
    obs.anotar("MSFT", 200.00, 200.50)
    for i in range(1, 6):                        # se mueve SOLO el ask, 5 veces
        obs.anotar("MSFT", 200.00, 200.50 + i * 0.01)
    cb, ca = obs.cambios_bid("MSFT", 30), obs.cambios_ask("MSFT", 30)
    ok1b = cb == 0 and ca == 5
    print("   el ask se movio 5 veces y el bid ninguna:")
    print(f"      cambios del bid: {cb} (esperado 0)")
    print(f"      cambios del ask: {ca} (esperado 5)")
    print(f"   -> {'OK' if ok1b else '*** FALLO'}\n")

    print("=" * 72)
    print("2) VENTANA DESLIZANTE: el caso del simbolo 30, 20 minutos despues")
    print("=" * 72)
    obs = ObservadorMovimiento(ahora=reloj)
    obs.observar(["ZZZ"])
    print("   12:00:00 arranca la watchlist. ZZZ se mueve MUCHO al principio:")
    for i in range(40):                          # 40 cambios ahora
        obs.anotar("ZZZ", 50.00 + i * 0.01, 50.50 + i * 0.01)
    print(f"      cambios en los ultimos 30s: {obs.cambios_bid('ZZZ', 30)}")

    print("   ... pasan 20 minutos (el bot recorre los otros 29 simbolos) ...")
    reloj.avanzar(20 * 60)
    print("   12:20:00 le toca ZZZ. En los ultimos 30s estuvo QUIETO:")
    obs.anotar("ZZZ", 50.40, 50.90)              # un solo cambio reciente
    reciente = obs.cambios_bid("ZZZ", 30)
    ok2 = reciente == 1
    print(f"      cambios en los ultimos 30s: {reciente} (esperado 1)")
    print("      los 40 cambios viejos NO cuentan: la ventana mira desde 12:19:30")
    print(f"   -> {'OK' if ok2 else '*** FALLO'}\n")

    print("=" * 72)
    print("3) El bot saltea el nervioso y deja pasar el quieto")
    print("=" * 72)
    obs = ObservadorMovimiento(ahora=reloj)
    b = FakeBroker()
    b.set_quote("QUIETA", bid=10.00, ask=10.05, volume=5_000_000)
    b.set_quote("NERVIOSA", bid=20.00, ask=20.05, volume=5_000_000)
    cfg = EngineConfig(
        quantity=10, side=Side.BUY,
        order1=OrderConfig(offset=50, unit=OffsetUnit.PERCENT_SPREAD, timeout_s=1),
        order2=OrderConfig(offset=50, unit=OffsetUnit.PERCENT_SPREAD, timeout_s=1),
        exit_levels=[], guard=None,
        max_cambios_bid=5, ventana_bid_s=30,
        max_cambios_ask=5, ventana_ask_s=30,
    )
    motor = BotEngine(b, cfg, log=lambda m: print(f"      {m}"), observador=obs)

    obs.observar(["QUIETA", "NERVIOSA"])
    reloj.avanzar(40)                            # ya hay ventana completa
    for i in range(3):                           # QUIETA: 3 cambios (tope 5) -> pasa
        obs.anotar("QUIETA", 10.00 + i * 0.01, 10.05 + i * 0.01)
    for i in range(12):                          # NERVIOSA: 12 cambios -> saltea
        obs.anotar("NERVIOSA", 20.00 + i * 0.01, 20.05 + i * 0.01)

    print("   QUIETA (3 cambios, tope 5):")
    pasa = motor._movimiento_ok("QUIETA")
    print("   NERVIOSA (12 cambios, tope 5):")
    saltea = motor._movimiento_ok("NERVIOSA")
    ok3 = pasa and not saltea
    print(f"   -> {'OK: dejo pasar la quieta y salteo la nerviosa' if ok3 else '*** FALLO'}\n")

    print("=" * 72)
    print("4) Sin ventana completa todavia: ESPERA lo que falta")
    print("=" * 72)
    esperas = []

    class ClockEspia:
        """Reloj del motor: anota cuanto durmio en total."""
        def now(self):
            return reloj.t

        def sleep(self, s):
            esperas.append(s)
            reloj.avanzar(s)

    obs2 = ObservadorMovimiento(ahora=reloj)
    motor2 = BotEngine(b, cfg, log=lambda m: print(f"      {m}"),
                       observador=obs2, clock=ClockEspia())
    obs2.observar(["NUEVA"])                     # recien empieza a observar
    obs2.anotar("NUEVA", 30.00, 30.05)
    print("   el bot llega a NUEVA con solo 0s observados (ventana 30s):")
    motor2._movimiento_ok("NUEVA")
    total = sum(esperas)
    ok4 = 29 <= total <= 31
    print(f"   espero {total:.0f}s en total (esperado ~30)")
    print(f"   -> {'OK: no decide con datos incompletos' if ok4 else '*** FALLO'}\n")

    print("=" * 72)
    print("5) Filtro apagado (campo vacio) = todo pasa, como antes")
    print("=" * 72)
    cfg_off = EngineConfig(
        quantity=10, side=Side.BUY,
        order1=OrderConfig(offset=50, unit=OffsetUnit.PERCENT_SPREAD, timeout_s=1),
        order2=OrderConfig(offset=50, unit=OffsetUnit.PERCENT_SPREAD, timeout_s=1),
        exit_levels=[], guard=None,
        max_cambios_bid=None, max_cambios_ask=None,
    )
    m3 = BotEngine(b, cfg_off, log=lambda m: None, observador=obs)
    ok5 = m3._movimiento_ok("NERVIOSA")
    print(f"   NERVIOSA con el filtro apagado -> pasa: {ok5} (esperado True)")
    print(f"   -> {'OK' if ok5 else '*** FALLO'}\n")

    todo = ok1 and ok1b and ok2 and ok3 and ok4 and ok5
    print("=" * 72)
    print("OK: el filtro de movimiento funciona con ventana deslizante."
          if todo else "*** HAY FALLOS.")


if __name__ == "__main__":
    main()
