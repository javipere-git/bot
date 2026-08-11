"""
Corre el motor del bot en un hilo aparte, para que la pantalla no se congele.

Se comunica con la pantalla por SENALES (signals) de Qt: cada mensaje del motor
se emite como 'log', y al terminar emite 'finished'. Emitir senales desde el
hilo del bot hacia la pantalla es seguro en Qt (se entregan en el hilo de la GUI).
"""
from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal, Slot

from ..core.engine import BotEngine


class BotRunner(QObject):
    log = Signal(str)
    finished = Signal(str)
    manual = Signal(str, bool)  # posicion en manos del usuario (simbolo, fue_el_guardia)
    pausado = Signal(bool)      # True = quedo pausado, False = siguio

    def __init__(self, broker, config, symbols, observador=None) -> None:
        super().__init__()
        self._symbols = symbols
        # El motor escribe sus mensajes emitiendo la senal 'log', avisa por 'manual'
        # cuando una posicion queda para cerrar a mano, y por 'pausado' cada vez que
        # se pausa o sigue (incluidas las pausas que se toma SOLO).
        self.engine = BotEngine(
            broker, config, log=self.log.emit, on_manual=self.manual.emit,
            observador=observador, on_pausa=self.pausado.emit,
        )

    @Slot()
    def run(self) -> None:
        try:
            outcome = self.engine.run_watchlist(self._symbols)
            self._cerrar_reporte()
            self.finished.emit(outcome.value)
        except Exception as e:  # noqa: BLE001
            self._cerrar_reporte()
            self.log.emit(f"ERROR inesperado del bot: {e}")
            self.finished.emit("error")

    def _cerrar_reporte(self) -> None:
        """Marca la hora de fin de la pasada (el neto lo completa la pantalla)."""
        rep = self.engine.reporte
        if rep is not None and rep.fin is None:
            rep.fin = time.time()

    def stop(self) -> None:
        self.engine.stop()

    def pause(self) -> None:
        self.engine.pause()

    def resume(self) -> None:
        self.engine.resume()
