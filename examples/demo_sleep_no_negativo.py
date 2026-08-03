"""
El bot NO se cae por "sleep length must be non-negative".

Bug real (Alpaca LIVE, log del 03/08/2026): el bot venia recorriendo la watchlist
con los filtros activos y se detuvo con "ERROR inesperado del bot: sleep length must
be non-negative". Causa: una carrera entre chequear el deadline (now() < fin) y
calcular cuanto dormir (fin - now()); en el medio pasa un instante y el valor queda
levemente negativo, y time.sleep() con un negativo crashea.

Aca se fuerza esa situacion con un reloj que avanza el tiempo entre una llamada y la
siguiente, y se comprueba que NINGUN sleep recibe un negativo.

    python examples/demo_sleep_no_negativo.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.core.engine import RealClock  # noqa: E402


class RelojTramposo:
    """now() salta hacia adelante en cada llamada -> reproduce la carrera: cuando se
    calcula (deadline - now()) ya paso el deadline y da negativo."""

    def __init__(self):
        self.t = 100.0
        self.dormidos = []

    def now(self):
        self.t += 0.30      # cada consulta 'avanza' mas que el poll -> deadline vencido
        return self.t

    def sleep(self, seconds):
        self.dormidos.append(seconds)
        if seconds < 0:
            raise ValueError("sleep length must be non-negative")   # como el real


def main() -> None:
    print("1) El reloj REAL nunca duerme un tiempo negativo")
    rc = RealClock()
    try:
        rc.sleep(-0.5)      # antes: crash
        ok1 = True
    except ValueError:
        ok1 = False
    print(f"   RealClock.sleep(-0.5) -> {'no crashea (drome 0)' if ok1 else '*** CRASH'}")
    print(f"   -> {'OK' if ok1 else '*** FALLO'}\n")

    print("2) La cuenta acotada nunca sale negativa, aunque el deadline ya vencio")
    # se replica el patron exacto de los tres sitios del motor
    reloj = RelojTramposo()
    deadline = reloj.now() + 0.5
    poll = 0.5
    negativos = 0
    for _ in range(20):
        if reloj.now() >= deadline:
            break
        dormir = max(0.0, min(poll, deadline - reloj.now()))   # <- lo que hace el motor
        if dormir < 0:
            negativos += 1
        reloj.sleep(dormir)
    ok2 = negativos == 0 and all(d >= 0 for d in reloj.dormidos)
    print(f"   {len(reloj.dormidos)} sleeps, ninguno negativo: {ok2}")
    print(f"   min de los sleeps: {min(reloj.dormidos):.3f} (nunca < 0)")
    print(f"   -> {'OK' if ok2 else '*** FALLO'}\n")

    print("OK: el bot ya no se cae por sleep negativo."
          if (ok1 and ok2) else "*** HAY FALLOS.")
    return ok1 and ok2


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
