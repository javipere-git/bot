"""
Observador de movimiento: mira como se comporto cada simbolo en los ultimos segundos.
Dos cosas, las dos alimentadas por el streaming:

  - CUANTAS VECES se movio el bid y cuantas el ask (los dos lados por separado).
  - Cual fue el SPREAD MAS ANCHO en ese rato (para el filtro de spread maximo).

Para que sirve: antes de entrarle a una accion conviene saber si esta quieta o
nerviosa. Una accion que hace 10 minutos esta clavada en 100.00 x 100.50 no es lo
mismo que una que hace 2 segundos estaba en 100.20 x 100.80. No importa tanto la
magnitud del movimiento como la CANTIDAD de cambios.

Como se alimenta: del STREAMING, que ya manda cada cambio de precio sin gastar
llamadas a la API. Preguntarlo por REST seria imposible (harian falta ~50 consultas
por simbolo para mirar 10 segundos, y el cupo de Tradier es 120/min).

Que cuenta: SOLO cambios de PRECIO. Si cambia unicamente el tamano (la cantidad
ofrecida) no cuenta, porque el precio no se movio. Y si se mueve solo el bid, cuenta
en el bid y no en el ask.

VENTANA DESLIZANTE: `cambios_bid(sym, 30)` devuelve los cambios de los ultimos 30
segundos contados LITERALMENTE HACIA ATRAS DESDE AHORA. Si el bot llega al ultimo
simbolo a las 12:20:00, mira desde las 12:19:30. El reloj de la ventana es
independiente de los movimientos: un cambio no la reinicia ni la corre.

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
        self._ultimo_bid: dict[str, float] = {}
        self._ultimo_ask: dict[str, float] = {}
        self._cambios_bid: dict[str, list] = {}   # sym -> [instantes de cada cambio]
        self._cambios_ask: dict[str, list] = {}
        self._spreads: dict[str, list] = {}       # sym -> [(instante, spread)]
        self._desde: dict[str, float] = {}        # sym -> desde cuando lo observamos

    # ---------- lo llama el streaming ----------
    def anotar(self, sym: str, bid: float, ask: float) -> None:
        """Un quote nuevo. Cada lado cuenta aparte, y solo si su PRECIO cambio."""
        if not sym:
            return
        sym = sym.upper()
        b = round(float(bid or 0), 4)
        a = round(float(ask or 0), 4)
        ahora = self._ahora()
        with self._lock:
            self._desde.setdefault(sym, ahora)
            ant_b = self._ultimo_bid.get(sym)
            ant_a = self._ultimo_ask.get(sym)
            self._ultimo_bid[sym] = b
            self._ultimo_ask[sym] = a
            if ant_b is not None and ant_b != b:
                self._anotar_cambio(self._cambios_bid, sym, ahora)
            if ant_a is not None and ant_a != a:
                self._anotar_cambio(self._cambios_ask, sym, ahora)
            # historial del spread (para el filtro de spread maximo)
            if b > 0 and a > 0:
                hist = self._spreads.setdefault(sym, [])
                hist.append((ahora, round(a - b, 4)))
                corte = ahora - self.RECORDAR_S
                if hist[0][0] < corte:
                    self._spreads[sym] = [x for x in hist if x[0] >= corte]

    def _anotar_cambio(self, donde: dict, sym: str, ahora: float) -> None:
        """Agrega el instante y poda lo viejo (no acumular para siempre)."""
        lista = donde.setdefault(sym, [])
        lista.append(ahora)
        corte = ahora - self.RECORDAR_S
        if lista[0] < corte:
            donde[sym] = [t for t in lista if t >= corte]

    def observar(self, symbols) -> None:
        """Marca desde cuando se observa cada simbolo (para saber si ya hay ventana
        completa). Se llama al suscribir la watchlist, aunque todavia no llegue nada."""
        ahora = self._ahora()
        with self._lock:
            for s in symbols:
                if s:
                    self._desde.setdefault(s.upper(), ahora)

    # ---------- lo consulta el bot ----------
    def cambios_bid(self, sym: str, segundos: float) -> int:
        """Cuantas veces se movio el BID en los ultimos `segundos` (hasta AHORA)."""
        return self._contar(self._cambios_bid, sym, segundos)

    def cambios_ask(self, sym: str, segundos: float) -> int:
        """Cuantas veces se movio el ASK en los ultimos `segundos` (hasta AHORA)."""
        return self._contar(self._cambios_ask, sym, segundos)

    def _contar(self, donde: dict, sym: str, segundos: float) -> int:
        if not sym or segundos <= 0:
            return 0
        desde = self._ahora() - segundos
        with self._lock:
            return sum(1 for t in donde.get(sym.upper(), ()) if t >= desde)

    def spread_maximo(self, sym: str, segundos: float):
        """El spread MAS ANCHO que tuvo el simbolo en los ultimos `segundos`.
        None si no hay datos todavia."""
        if not sym or segundos <= 0:
            return None
        desde = self._ahora() - segundos
        with self._lock:
            vistos = [sp for t, sp in self._spreads.get(sym.upper(), ()) if t >= desde]
        return max(vistos) if vistos else None

    def observando_hace(self, sym: str) -> float:
        """Segundos que lleva observando ese simbolo. 0 si nunca lo vio."""
        if not sym:
            return 0.0
        with self._lock:
            desde = self._desde.get(sym.upper())
        return 0.0 if desde is None else max(0.0, self._ahora() - desde)

    def limpiar(self) -> None:
        with self._lock:
            self._ultimo_bid.clear()
            self._ultimo_ask.clear()
            self._cambios_bid.clear()
            self._cambios_ask.clear()
            self._spreads.clear()
            self._desde.clear()
