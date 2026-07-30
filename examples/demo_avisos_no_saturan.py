"""
Los avisos instantaneos NO deben saturar la API cuando el bot escanea la watchlist.

El problema (visto en un log real, Alpaca LIVE 30/07/2026): con el bot metiendo
place+modify muy rapido por toda la watchlist, cada aviso del broker disparaba un
refresco (get_orders + get_positions). La tormenta de avisos -> tormenta de llamadas
-> HTTP 429 rate limit -> el bot freno por seguridad.

El arreglo, en linea con lo que pidio el usuario ("cuando va con el bot la velocidad
la maneja el"): mientras el bot ESCANEA, se apagan los refrescos por aviso (el
monitoreo periodico alcanza). Al pasar a MANUAL, se vuelven a encender (ahi el
usuario opera y necesita ver las ordenes al instante).

    python examples/demo_avisos_no_saturan.py
"""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.gui.market_worker import MarketWorker  # noqa: E402


class BrokerContando:
    def __init__(self):
        self.consultas = 0

    def get_positions(self):
        return []

    def get_day_pnl(self):
        return None

    def get_quote(self, sym):
        raise RuntimeError("sin quote")

    def get_orders(self, limit=None):
        self.consultas += 1
        return []


def main() -> None:
    b = BrokerContando()
    w = MarketWorker(b, interval=999)          # sin sondeo periodico: aislo los avisos
    hilo = threading.Thread(target=w.run, daemon=True)
    hilo.start()
    time.sleep(0.3)

    print("1) BOT ESCANEANDO: una rafaga de avisos NO dispara llamadas")
    w.set_bot_escaneando(True)
    base = b.consultas
    for _ in range(60):                        # 60 avisos, como el bot operando fuerte
        w.refrescar_ya()
        time.sleep(0.01)
    time.sleep(0.6)
    durante_bot = b.consultas - base
    ok1 = durante_bot == 0
    print(f"   60 avisos con el bot escaneando -> {durante_bot} llamadas (esperado 0)")
    print(f"   -> {'OK: no satura' if ok1 else '*** FALLO: se dispararon llamadas'}\n")

    print("2) MANUAL: un aviso SI refresca al instante")
    w.set_bot_escaneando(False)
    base = b.consultas
    t0 = time.time()
    w.refrescar_ya()
    while b.consultas == base and time.time() - t0 < 2:
        time.sleep(0.02)
    tardo = time.time() - t0
    ok2 = b.consultas > base and tardo < 0.6
    print(f"   refresco en {tardo*1000:.0f} ms (avisos activos en manual)")
    print(f"   -> {'OK' if ok2 else '*** FALLO'}\n")

    print("3) MANUAL con rafaga: el freno de MIN_REFRESCO igual limita")
    base = b.consultas
    for _ in range(40):
        w.refrescar_ya()
        time.sleep(0.01)
    time.sleep(0.6)
    usadas = b.consultas - base
    ok3 = usadas <= 3
    print(f"   40 avisos en manual -> {usadas} llamadas (esperado <= 3, por el freno)")
    print(f"   -> {'OK' if ok3 else '*** FALLO'}\n")

    w.stop()
    print("OK: durante el bot no satura; en manual refresca al instante."
          if (ok1 and ok2 and ok3) else "*** HAY FALLOS.")


if __name__ == "__main__":
    main()
