"""
Puente entre el streaming de Tradier (que corre en su propio hilo) y la pantalla.

Cada cotizacion que llega del stream se reemite como la senal Qt 'quote', que se
entrega en el hilo de la GUI (seguro en Qt). SOLO LECTURA de precios.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..connectors.tradier_stream import TradierMarketStream


class StreamWorker(QObject):
    quote = Signal(str, float, float, float, float)

    def __init__(self, stream: TradierMarketStream) -> None:
        super().__init__()
        self._stream = stream
        self._started = False

    @classmethod
    def from_credentials(cls) -> "StreamWorker":
        return cls(TradierMarketStream.from_credentials())

    def set_symbol(self, sym: str) -> None:
        if not sym:
            return
        if not self._started:
            self._stream.start([sym], self.quote.emit)
            self._started = True
        else:
            self._stream.set_symbols([sym])

    def esta_conectado(self) -> bool:
        return self._stream.esta_conectado()

    def estado(self) -> str:
        if not self._started:
            return "inactivo"
        return "conectado" if self._stream.esta_conectado() else "reconectando"

    def stop(self) -> None:
        self._stream.stop()
