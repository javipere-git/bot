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

    def __init__(self, stream, tipo: str) -> None:
        super().__init__()
        self._stream = stream
        self._tipo = tipo      # "tradier" | "alpaca"
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        if self._tipo == "alpaca":
            # el aviso de Alpaca trae (orden, evento, cantidad_de_posicion)
            self._stream.start(on_update=lambda o, ev, pq: self.cambio.emit())
        else:
            self._stream.start(lambda data: self.cambio.emit())

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
