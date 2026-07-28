"""
Corre el motor del bot en un hilo aparte, para que la pantalla no se congele.

Se comunica con la pantalla por SENALES (signals) de Qt: cada mensaje del motor
se emite como 'log', y al terminar emite 'finished'. Emitir senales desde el
hilo del bot hacia la pantalla es seguro en Qt (se entregan en el hilo de la GUI).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from ..core.engine import BotEngine


class BotRunner(QObject):
    log = Signal(str)
    finished = Signal(str)
    manual = Signal(str, bool)  # posicion en manos del usuario (simbolo, fue_el_guardia)

    def __init__(self, broker, config, symbols) -> None:
        super().__init__()
        self._symbols = symbols
        # El motor escribe sus mensajes emitiendo la senal 'log', y avisa por
        # 'manual' cuando una posicion queda para cerrar a mano.
        self.engine = BotEngine(
            broker, config, log=self.log.emit, on_manual=self.manual.emit
        )

    @Slot()
    def run(self) -> None:
        try:
            outcome = self.engine.run_watchlist(self._symbols)
            self.finished.emit(outcome.value)
        except Exception as e:  # noqa: BLE001
            self.log.emit(f"ERROR inesperado del bot: {e}")
            self.finished.emit("error")

    def stop(self) -> None:
        self.engine.stop()

    def pause(self) -> None:
        self.engine.pause()

    def resume(self) -> None:
        self.engine.resume()
