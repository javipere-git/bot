"""
Hace las llamadas al broker del LADDER fuera del hilo de la pantalla.

Por que existe: antes, un click en el ladder llamaba al broker ahi mismo, en el
hilo de la pantalla. Mientras el broker contestaba (100-400 ms, a veces mas), la
ventana quedaba CONGELADA: no repintaba, no respondia. Se sentia lento aunque la
orden saliera rapido.

Aca las llamadas corren en un hilo propio: el click vuelve al instante y la
pantalla nunca se traba. Lo que se manda al broker es exactamente lo mismo que
antes; no cambia ninguna orden ni se agrega ni una llamada a la API.

DOS GARANTIAS que se respetan a proposito:

1. EN ORDEN Y DE A UNA. Las peticiones viajan por conexiones en cola de Qt hacia
   UN solo hilo, asi que se ejecutan en el mismo orden en que hiciste los clicks y
   nunca dos a la vez. Si mandas dos ordenes seguidas, salen en ese orden.

2. LAS REDES DE SEGURIDAD SIGUEN ANTES, EN LA PANTALLA. La validacion de que una
   venta no abra un corto sin querer NO cuesta llamadas (usa datos que ya estan) y
   queda del lado de la pantalla, ANTES de encolar. Si no pasa, aca no llega nada.

Ademas, el broker del ladder es una instancia DEDICADA (main_window crea una
aparte para operar a mano), asi que este hilo es el unico que la toca: no se
comparte la conexion HTTP entre hilos (eso corrompe la capa SSL y tira la app).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from ..core.models import OrderRequest, OrderType


class LadderWorker(QObject):
    """Ejecuta mandar / mover / cancelar en su propio hilo.

    Cada peticion viaja con una CLAVE que la pantalla le pone antes de encolar, y
    el resultado vuelve con esa misma clave por la señal `resultado`. Eso es lo que
    permite el dibujo optimista: la escalera pinta la orden apenas haces click y,
    cuando llega el resultado, sabe EXACTAMENTE cual de las que dibujo confirmar o
    borrar. Sin la clave habria que adivinar.
    """

    log = Signal(str)
    # (clave, salio_bien, id_real_de_la_orden)  -- el id llega solo al mandar
    resultado = Signal(str, bool, str)

    def __init__(self, broker_provider) -> None:
        super().__init__()
        self._broker_provider = broker_provider

    def _broker(self):
        return self._broker_provider() if self._broker_provider else None

    @Slot(str, object, str, int, float, bool)
    def mandar(self, clave: str, side, symbol: str, qty: int, precio: float,
               extended: bool) -> None:
        broker = self._broker()
        if broker is None:
            self.log.emit("Ladder: no hay conexion para operar.")
            self.resultado.emit(clave, False, "")
            return
        try:
            orden = broker.place_order(
                OrderRequest(symbol, side, qty, round(precio, 2), OrderType.LIMIT,
                             extended=extended)
            )
            self.log.emit(f"Ladder: {side.value} {qty} {symbol} @ {precio:.2f} "
                          f"enviada (id {orden.id}).")
            self.resultado.emit(clave, True, str(orden.id))
        except Exception as e:  # noqa: BLE001
            self.log.emit(f"*** Ladder: no se pudo mandar la orden ({e}) ***")
            self.resultado.emit(clave, False, "")

    @Slot(str, object, float)
    def mover(self, clave: str, pares, nuevo: float) -> None:
        """`pares` son (id_de_orden, duracion) resueltos en la pantalla: la duracion
        sale de las ordenes que ya tiene cargadas, no se relee del broker."""
        broker = self._broker()
        if broker is None:
            self.log.emit("Ladder: no hay conexion para operar.")
            self.resultado.emit(clave, False, "")
            return
        ok = True
        for oid, dur in pares:
            try:
                # se respeta la duracion que YA tiene la orden: si es de horario
                # extendido (pre/post) y se manda "day", el broker la rechaza
                broker.modify_order(oid, price=round(nuevo, 2), duration=dur)
                self.log.emit(f"Ladder: orden {oid} movida a {nuevo:.2f}.")
            except Exception as e:  # noqa: BLE001
                self.log.emit(f"Ladder: no se pudo mover ({e})")
                ok = False
        self.resultado.emit(clave, ok, "")

    @Slot(str, object)
    def cancelar(self, clave: str, ids) -> None:
        broker = self._broker()
        if broker is None:
            self.log.emit("Ladder: no hay conexion para operar.")
            self.resultado.emit(clave, False, "")
            return
        ok = True
        for oid in ids:
            try:
                broker.cancel_order(oid)
                self.log.emit(f"Ladder: orden {oid} cancelada.")
            except Exception as e:  # noqa: BLE001
                self.log.emit(f"Ladder: error al cancelar ({e})")
                ok = False
        self.resultado.emit(clave, ok, "")

    @Slot(str)
    def cancelar_todas(self, clave: str) -> None:
        broker = self._broker()
        if broker is None:
            self.log.emit("Ladder: no hay conexion para operar.")
            self.resultado.emit(clave, False, "")
            return
        try:
            abiertas = broker.get_open_orders()
        except Exception as e:  # noqa: BLE001
            self.log.emit(f"Ladder: no pude leer las ordenes ({e})")
            self.resultado.emit(clave, False, "")
            return
        if not abiertas:
            self.log.emit("Ladder: no hay ordenes abiertas para cancelar.")
            self.resultado.emit(clave, True, "")
            return
        n = 0
        for o in abiertas:
            try:
                broker.cancel_order(o.id)
                n += 1
            except Exception:  # noqa: BLE001
                pass
        self.log.emit(f"Ladder: cancele {n} de {len(abiertas)} orden(es) abierta(s).")
        self.resultado.emit(clave, n == len(abiertas), "")
