"""
Puente entre los avisos de CUENTA del broker y la pantalla.

Cada vez que el broker avisa que una orden cambio (se puso, se ejecuto, se
cancelo, la rechazaron), se emite la senal 'cambio'. La ventana la usa para
refrescar el monitoreo y el ladder EN EL MOMENTO, en vez de esperar el sondeo
de cada 4 segundos.

Medido: los avisos llegan en ~200 ms. El sondeo tardaba hasta 4000 ms.

Los dos brokers tienen este canal, con formatos distintos; aca se unifican:
  - Tradier: TradierAccountStream (evento con id + estado)
  - Alpaca : AlpacaTradeStream (evento con la orden completa)
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AccountWorker(QObject):
    cambio = Signal()          # "algo cambio en las ordenes: refresca ya"
    # CAMINO RAPIDO: (id, estado, orden_completa_o_None) sacados del propio aviso.
    # Antes se tiraba lo que el aviso traia y se le volvia a preguntar al broker;
    # con esto la pantalla se actualiza al instante y sin gastar una llamada.
    orden = Signal(object, object, object)

    def __init__(self, stream, tipo: str, broker=None) -> None:
        super().__init__()
        self._stream = stream
        self._tipo = tipo      # "tradier" | "alpaca" | "tastytrade"
        self._broker = broker  # el que sabe traducir SU formato de aviso
        self._started = False

    def _avisar(self, evento) -> None:
        """Un aviso del broker: se emite el dato rapido (si el conector lo entiende)
        y SIEMPRE el 'cambio', que dispara la lectura de respaldo."""
        if self._broker is not None:
            try:
                oid, estado, orden = self._broker.orden_de_aviso(evento)
                if oid is not None:
                    self.orden.emit(oid, estado, orden)
            except Exception:  # noqa: BLE001
                pass           # un aviso raro nunca corta el camino normal
        self.cambio.emit()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        if self._tipo == "alpaca":
            # el aviso de Alpaca trae (orden, evento, cantidad_de_posicion)
            self._stream.start(on_update=lambda o, ev, pq: self._avisar(o))
        else:
            self._stream.start(self._avisar)

    def esta_conectado(self) -> bool:
        try:
            return bool(self._stream.esta_conectado())
        except Exception:  # noqa: BLE001
            return False

    def stop(self) -> None:
        try:
            self._stream.stop()
        except Exception:  # noqa: BLE001
            pass
