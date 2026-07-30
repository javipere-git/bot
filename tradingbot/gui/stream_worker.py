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
    # Time & Sales: simbolo, precio, cantidad, exchange, hora (epoch)
    trade = Signal(str, float, float, str, float)

    def __init__(self, stream: TradierMarketStream) -> None:
        super().__init__()
        self._stream = stream
        self._started = False
        self._ladder = None
        self._watchlist = []

    @classmethod
    def from_credentials(cls) -> "StreamWorker":
        return cls(TradierMarketStream.from_credentials())

    def set_symbol(self, sym: str) -> None:
        """Simbolo del ladder. Se suscribe junto con los de la watchlist (si hay)."""
        self._ladder = (sym or "").upper() or None
        self._resuscribir()

    def set_watchlist(self, symbols) -> None:
        """Simbolos de la watchlist del bot: se suscriben para poder medir cuantas
        veces se mueve el bid/ask de cada uno (filtro de movimiento). Sin esto, el
        streaming solo traeria el simbolo del ladder."""
        self._watchlist = [s.upper() for s in (symbols or []) if s]
        self._resuscribir()

    def _resuscribir(self) -> None:
        syms = list(dict.fromkeys(
            ([self._ladder] if self._ladder else []) + list(self._watchlist)
        ))
        if not syms:
            return
        if not self._started:
            self._stream.start(syms, self.quote.emit, self.trade.emit)
            self._started = True
        else:
            self._stream.set_symbols(syms)

    def esta_conectado(self) -> bool:
        return self._stream.esta_conectado()

    def estado(self) -> str:
        if not self._started:
            return "inactivo"
        return "conectado" if self._stream.esta_conectado() else "reconectando"

    def stop(self) -> None:
        self._stream.stop()
