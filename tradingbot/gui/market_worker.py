"""
Lee periodicamente del broker (posiciones y ordenes abiertas) en un hilo aparte
y manda los datos a la pantalla por senales. SOLO LECTURA: no opera nada.

Corre todo el tiempo que la app este abierta (independiente del bot), asi el
monitoreo se ve siempre, no solo cuando el bot opera.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal, Slot

from ..core.models import DayPnL


class MarketWorker(QObject):
    positions = Signal(list)
    orders = Signal(list)
    closed_orders = Signal(list)
    day_pnl = Signal(object)   # DayPnL (realizado + no realizado) del broker
    quote = Signal(str, float, float, float, float)
    error = Signal(str)

    ORDENES_RECIENTES = 400   # cuantas ordenes nuevas se piden en cada refresco
    MIN_REFRESCO = 0.4        # segundos minimos entre refrescos disparados por avisos

    def __init__(
        self, broker, interval: float = 3.0, intervalo_completo: float = 60.0
    ) -> None:
        super().__init__()
        self._broker = broker
        self._interval = interval
        # Las ordenes se refrescan SEGUIDO pero pidiendo solo las mas RECIENTES
        # (rapido). Cada tanto se pide la lista COMPLETA como red de seguridad, por
        # si quedo viva una orden vieja (con miles de ordenes en el dia, esa no
        # entraria en las recientes). Las dos se combinan en la misma tabla.
        self._intervalo_completo = intervalo_completo
        self._ultimo_completo = 0.0
        self._cache_ordenes: dict[str, object] = {}
        self._stop = False
        self._ladder_symbol = None
        self._ladder_ya = False   # pedir el precio del ladder YA (cambio de simbolo)
        # Refresco inmediato disparado por un aviso del broker (orden puesta,
        # ejecutada, cancelada...). Con freno: como maximo uno cada MIN_REFRESCO
        # segundos, para que una rafaga de avisos del bot no dispare decenas de
        # llamadas y agote el cupo de la API.
        self._refrescar_ya = False
        self._ultimo_refresco = 0.0

    @Slot()
    def run(self) -> None:
        while not self._stop:
            try:
                pos = self._broker.get_positions()
                self.positions.emit(pos)
                self.day_pnl.emit(self._resultado_del_dia(pos))
            except Exception as e:  # noqa: BLE001
                self.error.emit(f"Monitoreo (posiciones): {e}")
            self._emitir_ordenes()
            self._emitir_quote_ladder()
            # dormir en tramos cortos para poder cortar rapido al cerrar
            slept = 0.0
            while slept < self._interval and not self._stop:
                time.sleep(0.1)
                slept += 0.1
                # Si acaban de cargar un simbolo en el ladder, pedir su precio YA.
                # Importante en acciones poco liquidas: el streaming solo manda datos
                # cuando el precio CAMBIA, asi que sin esto la escalera puede quedar
                # vacia minutos (comprobado: 45s sin un solo quote en KPLT y SFBC).
                if self._ladder_ya:
                    self._ladder_ya = False
                    self._emitir_quote_ladder()
                # aviso del broker: refrescar ordenes YA (con el freno de MIN_REFRESCO)
                if self._refrescar_ya:
                    if time.monotonic() - self._ultimo_refresco >= self.MIN_REFRESCO:
                        self._refrescar_ya = False
                        self._emitir_ordenes()
                        try:
                            self.positions.emit(self._broker.get_positions())
                        except Exception:  # noqa: BLE001
                            pass

    def _emitir_ordenes(self) -> None:
        """Lee las ordenes y las manda a la pantalla (abiertas / cerradas)."""
        try:
            ahora = time.monotonic()
            if ahora - self._ultimo_completo >= self._intervalo_completo:
                self._ultimo_completo = ahora
                # pasada COMPLETA (lenta, cada tanto): rearma todo desde cero
                self._cache_ordenes = {o.id: o for o in self._broker.get_orders()}
            else:
                # refresco rapido: solo las mas recientes, encima de lo que hay
                for o in self._broker.get_orders(limit=self.ORDENES_RECIENTES):
                    self._cache_ordenes[o.id] = o
            todas = list(self._cache_ordenes.values())
            self.orders.emit([o for o in todas if o.is_active])
            self.closed_orders.emit([o for o in todas if not o.is_active])
            self._ultimo_refresco = time.monotonic()
        except Exception as e:  # noqa: BLE001
            self.error.emit(f"Monitoreo (ordenes): {e}")

    def refrescar_ya(self) -> None:
        """Lo llama la ventana cuando el broker avisa que una orden cambio."""
        self._refrescar_ya = True

    def _resultado_del_dia(self, posiciones):
        """Resultado del DIA (realizado + abierto) tal como lo informa el broker.
        Si el broker no lo da, cae a calcular solo lo abierto con las posiciones."""
        try:
            dia = self._broker.get_day_pnl()
            if dia is not None:
                return dia
        except Exception:  # noqa: BLE001
            pass
        return DayPnL(realizado=0.0, no_realizado=self._pnl_no_realizado(posiciones))

    def _emitir_quote_ladder(self) -> None:
        """Precio del simbolo del ladder por REST. Es el respaldo del streaming:
        lo mantiene fresco aunque la accion no se mueva."""
        sym = self._ladder_symbol
        if not sym:
            return
        try:
            q = self._broker.get_quote(sym)
            self.quote.emit(sym, float(q.bid or 0), float(q.ask or 0),
                            float(q.bid_size or 0), float(q.ask_size or 0))
        except Exception as e:  # noqa: BLE001
            self.error.emit(f"Ladder (quote {sym}): {e}")

    def _pnl_no_realizado(self, posiciones) -> float:
        """Suma (precio actual - promedio) * cantidad de cada posicion abierta.
        Usa el punto medio del spread como 'precio actual'."""
        total = 0.0
        for p in posiciones:
            try:
                q = self._broker.get_quote(p.symbol)
                if q.bid and q.ask:
                    mid = (q.bid + q.ask) / 2
                else:
                    mid = q.bid or q.ask or p.avg_price
                total += (mid - p.avg_price) * p.quantity
            except Exception:
                pass
        return total

    def set_ladder_symbol(self, sym) -> None:
        self._ladder_symbol = (sym or "").upper() or None
        self._ladder_ya = True    # que lo pida en el acto, sin esperar el ciclo

    def stop(self) -> None:
        self._stop = True
