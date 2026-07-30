"""
Observador de movimiento del bid/ask: cuenta CUANTAS VECES se movio el precio de
cada simbolo en los ultimos segundos.

Para que sirve: antes de entrarle a una accion conviene saber si esta quieta o
nerviosa. Una accion que hace 10 minutos esta clavada en 100.00 x 100.50 no es lo
mismo que una que hace 2 segundos estaba en 100.20 x 100.80. No importa tanto la
magnitud del movimiento como la CANTIDAD de cambios.

Como se alimenta: del STREAMING, que ya manda cada cambio de precio sin gastar
llamadas a la API. Preguntarlo por REST seria imposible (harian falta ~50 consultas
por simbolo para mirar 10 segundos, y el cupo de Tradier es 120/min).

Que cuenta: SOLO cambios de PRECIO del bid o del ask. Si cambia unicamente el tamano
(la cantidad ofrecida) no cuenta, porque el precio no se movio.

VENTANA DESLIZANTE: `cambios(sym, 30)` devuelve los cambios de los ultimos 30
segundos contados HACIA ATRAS DESDE AHORA, no desde que arranco la watchlist. Si el
bot llega al ultimo simbolo a las 12:20:00, mira desde las 12:19:30.

Es seguro entre hilos: el streaming escribe desde su hilo y el bot lee desde el suyo.
"""
from __future__ import annotations

import threading
import time


class ObservadorMovimiento:
    RECORDAR_S = 300.0     # se descartan los cambios mas viejos que esto (5 minutos)

    def __init__(self, ahora=None) -> None:
        self._ahora = ahora or time.monotonic     # inyectable para los tests
        self._lock = threading.Lock()
        self._ultimo: dict[str, tuple] = {}       # sym -> (bid, ask) del ultimo quote
        self._cambios: dict[str, list] = {}       # sym -> [instantes de cada cambio]
        self._desde: dict[str, float] = {}        # sym -> desde cuando lo observamos

    # ---------- lo llama el streaming ----------
    def anotar(self, sym: str, bid: float, ask: float) -> None:
        """Un quote nuevo. Solo cuenta si el PRECIO cambio (no el tamano)."""
        if not sym:
            return
        clave = (round(float(bid or 0), 4), round(float(ask or 0), 4))
        ahora = self._ahora()
        with self._lock:
            self._desde.setdefault(sym, ahora)
            anterior = self._ultimo.get(sym)
            self._ultimo[sym] = clave
            if anterior is None or anterior == clave:
                return                            # primer dato, o el precio no se movio
            lista = self._cambios.setdefault(sym, [])
            lista.append(ahora)
            corte = ahora - self.RECORDAR_S       # no acumular para siempre
            if lista[0] < corte:
                self._cambios[sym] = [t for t in lista if t >= corte]

    def observar(self, symbols) -> None:
        """Marca desde cuando se observa cada simbolo (para saber si ya hay ventana
        completa). Se llama al suscribir la watchlist, aunque todavia no llegue nada."""
        ahora = self._ahora()
        with self._lock:
            for s in symbols:
                if s:
                    self._desde.setdefault(s.upper(), ahora)

    # ---------- lo consulta el bot ----------
    def cambios(self, sym: str, segundos: float) -> int:
        """Cuantas veces se movio el bid/ask en los ultimos `segundos` (hasta AHORA)."""
        if not sym or segundos <= 0:
            return 0
        desde = self._ahora() - segundos
        with self._lock:
            return sum(1 for t in self._cambios.get(sym.upper(), ()) if t >= desde)

    def observando_hace(self, sym: str) -> float:
        """Segundos que lleva observando ese simbolo. 0 si nunca lo vio."""
        if not sym:
            return 0.0
        with self._lock:
            desde = self._desde.get(sym.upper())
        return 0.0 if desde is None else max(0.0, self._ahora() - desde)

    def limpiar(self) -> None:
        with self._lock:
            self._ultimo.clear()
            self._cambios.clear()
            self._desde.clear()
