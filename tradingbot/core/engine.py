"""
El cerebro del bot.

Tanda 1 (entrada): recorre la watchlist, filtra por spread, trabaja
Orden 1 -> Orden 2, detecta el llenado.
Tanda 2 (salida): cierre escalonado de hasta 4 niveles sobre la posicion
REAL, con un guardia de movimiento en contra.

Robustez (Fase 6): todas las llamadas al broker pasan por una capa que atrapa
errores (no se cae la app) y lleva un contador de "strikes":
  - Si una ORDEN (mandar/modificar) es rechazada o falla varias veces SEGUIDAS
    (max_strikes), el bot se DETIENE solo, deja la posicion como esta y avisa.
  - Si se pierde la conexion con el broker (muchas lecturas fallidas seguidas),
    tambien se detiene y avisa.
  - Cualquier exito reinicia los contadores.

Regla (primera etapa): una vez que el bot entra en una posicion, NO vuelve a la
watchlist hasta resolverla.

Usa la interfaz comun: funciona igual con el conector de mentira o el de Tradier.
"""
from __future__ import annotations

import math
import threading
import time
from enum import Enum
from typing import Callable

from .broker import Broker
from .config import (
    EngineConfig,
    ExitLevel,
    GuardAction,
    GuardReference,
    GuardUnit,
    OffsetUnit,
    OrderConfig,
)
from .models import Order, OrderRequest, OrderStatus, OrderType, Position, Quote, Side


class Outcome(str, Enum):
    NO_ENTRY = "no_entry"              # recorrio la watchlist y no entro en nada
    CLOSED = "closed"                 # entro y cerro la posicion automaticamente
    MANUAL_GUARD = "manual_guard"     # el guardia paso a manual (posicion abierta)
    MANUAL_NO_EXIT = "manual_no_exit"  # los niveles no cerraron (posicion abierta)
    STOPPED = "stopped"               # detenido por el usuario
    ABORTED = "aborted"               # detenido por errores del broker (robustez)


class RealClock:
    """Reloj de verdad (tiempo real)."""

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


# Palabras que indican que el rechazo es de ESE simbolo (no un problema del broker).
# (Ojo: "insufficient buying power / margin" es de la CUENTA -> NO va aca, debe frenar.)
_RECHAZO_SIMBOLO = (
    "not shortable", "no shortable", "not tradable", "not tradeable",
    "not found", "invalid symbol", "unknown symbol", "no encontrado",
    "halt", "hard to borrow", "not borrowable", "no borrow",
)


class BotEngine:
    MAX_READ_FAILS = 10  # lecturas fallidas seguidas que toman como "sin conexion"

    def __init__(
        self,
        broker: Broker,
        config: EngineConfig,
        clock: object | None = None,
        log: Callable[[str], None] | None = None,
        on_manual: Callable[[str], None] | None = None,
    ) -> None:
        self._broker = broker
        self._cfg = config
        self._clock = clock or RealClock()
        self._log = log or (lambda m: print(m))
        # aviso de "esta posicion queda en tus manos" (la pantalla lo usa para
        # cargar el simbolo en el ladder sola y, si fue el guardia, para la alarma)
        self._on_manual = on_manual or (lambda s, g: None)
        self._stopped = False
        self._resume = threading.Event()
        self._resume.set()  # set = corriendo; clear = en pausa
        # robustez
        self._order_strikes = 0
        self._read_fails = 0
        self._abort = False
        # bid (largo) / ask (corto) usado para CALCULAR la ultima orden de entrada;
        # es la referencia del guardia con GuardReference.ENTRY_CALC
        self._entry_ref: float | None = None

    # ===================== control =====================
    def stop(self) -> None:
        self._stopped = True
        self._resume.set()

    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    def _wait_if_paused(self) -> None:
        while not self._resume.is_set() and not self._stopped and not self._abort:
            time.sleep(0.05)

    # ===================== capa de robustez =====================
    def _safe_order(self, fn, desc):
        """Para operaciones de ORDEN (mandar/modificar). Cuenta strikes, SALVO que sea
        un rechazo especifico del simbolo (bloqueado/no shorteable), que solo se saltea."""
        try:
            r = fn()
            self._order_strikes = 0
            self._read_fails = 0
            return r, True
        except Exception as e:  # noqa: BLE001
            if self._es_rechazo_de_simbolo(str(e)):
                self._log(f"{desc}: simbolo no operable ({e}) -> lo salteo (no cuenta strike).")
                return None, False
            self._order_strikes += 1
            self._log(
                f"{desc}: sin aceptacion ({e})  [{self._order_strikes}/{self._cfg.max_strikes}]"
            )
            self._check_abort()
            return None, False

    def _safe_read(self, fn, desc):
        """Para lecturas (cotizaciones, ordenes, posiciones). No se cae si fallan."""
        try:
            r = fn()
            self._read_fails = 0
            return r, True
        except Exception as e:  # noqa: BLE001
            self._read_fails += 1
            if self._read_fails == 1 or self._read_fails % 5 == 0:
                self._log(f"{desc}: sin respuesta ({e})  [{self._read_fails}]")
            self._check_abort()
            return None, False

    def _check_abort(self) -> None:
        if self._abort:
            return
        if self._order_strikes >= self._cfg.max_strikes:
            self._abort = True
            self._resume.set()
            self._log(
                f"*** {self._order_strikes} ordenes seguidas SIN ACEPTACION -> BOT DETENIDO. "
                f"Dejo la posicion como esta; revisala a mano. ***"
            )
        elif self._read_fails >= self.MAX_READ_FAILS:
            self._abort = True
            self._resume.set()
            self._log(
                f"*** Sin conexion con el broker ({self._read_fails} intentos) -> BOT DETENIDO. "
                f"Revisa la posicion a mano. ***"
            )

    @staticmethod
    def _es_rechazo_de_simbolo(mensaje: str) -> bool:
        m = mensaje.lower()
        return any(k in m for k in _RECHAZO_SIMBOLO)


    # atajos
    def _get_quote(self, sym):
        return self._safe_read(lambda: self._broker.get_quote(sym), f"{sym}: cotizacion")

    def _get_order(self, oid):
        return self._safe_read(lambda: self._broker.get_order(oid), "consultar orden")

    def _get_positions(self):
        return self._safe_read(lambda: self._broker.get_positions(), "consultar posiciones")

    def _place(self, req: OrderRequest):
        return self._safe_order(lambda: self._broker.place_order(req), f"{req.symbol}: mandar orden")

    # ===================== flujo completo =====================
    def run_episode(self, symbols: list[str], max_cycles: int | None = None) -> Outcome:
        pos = self.scan_and_enter(symbols, max_cycles)
        if pos is None:
            if self._abort:
                return Outcome.ABORTED
            return Outcome.STOPPED if self._stopped else Outcome.NO_ENTRY
        self._log(
            f"{pos.symbol}: entramos. Trabajo la salida y NO sigo con la "
            f"watchlist hasta resolver esta posicion."
        )
        outcome = self.manage_exit(pos)
        self._announce(outcome, pos.symbol)
        return outcome

    def run_watchlist(self, symbols: list[str]) -> Outcome:
        """Recorre la watchlist operando, de forma continua y reanudable.

        - loop_watchlist=True: repite la lista hasta Detener. False: una pasada.
        - pause_on_fill=True: tras CERRAR, se auto-pausa (reanudable). False: sigue.
        - Si un cierre pasa a MANUAL, se PAUSA hasta que cierres a mano y reanudes.
        - Si saltan los strikes / se pierde la conexion, se DETIENE (ABORTED).
        """
        while not self._stopped and not self._abort:
            for sym in symbols:
                self._wait_if_paused()
                if self._stopped:
                    return Outcome.STOPPED
                if self._abort:
                    return Outcome.ABORTED

                pos = self._process_symbol(sym)
                if self._abort:
                    self._announce(Outcome.ABORTED, sym)
                    return Outcome.ABORTED
                if pos is None:
                    continue

                self._log(f"{sym}: en posicion. Trabajo la salida.")
                outcome = self.manage_exit(pos)

                if outcome == Outcome.ABORTED:
                    self._announce(outcome, sym)
                    return outcome

                if outcome in (Outcome.MANUAL_GUARD, Outcome.MANUAL_NO_EXIT):
                    self._announce(outcome, sym)
                    self._log(
                        f"{sym}: PAUSADO. Cerra la posicion a mano y apreta Reanudar "
                        f"para seguir con el siguiente simbolo."
                    )
                    self.pause()
                    self._wait_if_paused()
                    if self._stopped:
                        return Outcome.STOPPED
                    if self._abort:
                        return Outcome.ABORTED
                    while not self._is_flat(sym) and not self._stopped and not self._abort:
                        self._log(f"{sym}: la posicion sigue ABIERTA. Cerrala antes de reanudar.")
                        self.pause()
                        self._wait_if_paused()
                    if self._stopped:
                        return Outcome.STOPPED
                    if self._abort:
                        return Outcome.ABORTED
                    self._log(f"{sym}: posicion resuelta. Sigo con el siguiente simbolo.")
                    continue

                self._log(f"{sym}: posicion cerrada.")
                if self._cfg.pause_on_fill:
                    self._log(
                        f"{sym}: PAUSADO tras operar. Apreta Reanudar para seguir "
                        f"con el siguiente simbolo."
                    )
                    self.pause()
                    self._wait_if_paused()
                    if self._stopped:
                        return Outcome.STOPPED
                    if self._abort:
                        return Outcome.ABORTED

            if not self._cfg.loop_watchlist:
                self._log("Recorri toda la watchlist. Fin.")
                return Outcome.NO_ENTRY
        return Outcome.ABORTED if self._abort else Outcome.STOPPED

    # ===================== Tanda 1: entrada =====================
    def scan_and_enter(self, symbols: list[str], max_cycles: int | None = None) -> Position | None:
        cycle = 0
        while not self._stopped and not self._abort:
            cycle += 1
            for sym in symbols:
                self._wait_if_paused()
                if self._stopped or self._abort:
                    return None
                pos = self._process_symbol(sym)
                if pos is not None:
                    return pos
                if self._abort:
                    return None
            if max_cycles is not None and cycle >= max_cycles:
                self._log("Recorri la watchlist sin entrar en ninguna. Fin.")
                return None
        return None

    def _process_symbol(self, sym: str) -> Position | None:
        # SEGURIDAD: nunca abrir una posicion nueva si YA hay una abierta en la
        # cuenta (aunque la hayas abierto a mano). Avisa y se pausa.
        abiertas, ok = self._get_positions()
        if not ok:
            return None
        if abiertas:
            resumen = ", ".join(f"{p.symbol} {p.quantity}" for p in abiertas)
            self._log(
                f"*** Ya hay posicion abierta ({resumen}) -> NO abro otra. "
                f"PAUSADO: resolvela y apreta Reanudar. ***"
            )
            self.pause()
            return None

        self._entry_ref = None  # limpiar la referencia del simbolo anterior
        quote, ok = self._get_quote(sym)
        if not ok:
            return None
        # referencia del guardia (opcion "precio de calculo de la entrada")
        self._entry_ref = quote.bid if self._cfg.side == Side.BUY else quote.ask
        spread = round(quote.ask - quote.bid, 4)
        if not self._spread_ok(spread):
            self._log(f"{sym}: spread {spread:.2f} fuera de rango -> salteo")
            return None
        if not self._volume_ok(quote.volume):
            self._log(f"{sym}: volumen del dia {quote.volume:,} fuera de rango -> salteo")
            return None

        price1 = self._entry_price(quote, self._cfg.order1)
        self._log(
            f"{sym}: Orden 1  {self._cfg.side.value} {self._cfg.quantity} @ {price1:.2f}"
            f"  (spread {spread:.2f})"
        )
        order, ok = self._place(
            OrderRequest(sym, self._cfg.side, self._cfg.quantity, price1,
                         OrderType.LIMIT, self._cfg.duration)
        )
        if not ok:
            return None
        if self._entered_after_wait(order.id, self._cfg.order1.timeout_s):
            return self._on_entered(sym, order.id)

        if self._cfg.order2 is not None:
            quote, ok = self._get_quote(sym)  # el mercado pudo moverse
            if ok:
                # la Orden 2 se calcula con cotizacion fresca -> la referencia
                # del guardia se actualiza con ella (es el ultimo precio de calculo)
                self._entry_ref = quote.bid if self._cfg.side == Side.BUY else quote.ask
                price2 = self._entry_price(quote, self._cfg.order2)
                self._log(
                    f"{sym}: Orden 1 sin llenado -> Orden 2 @ {price2:.2f}"
                    f"  ({self._cfg.reprice_mode})"
                )
                order, filled = self._reprice(order, sym, price2)
                if order is None:
                    return None
                if filled or self._entered_after_wait(order.id, self._cfg.order2.timeout_s):
                    return self._on_entered(sym, order.id)

        if self._cancel_and_check_fill(order.id):
            self._log(f"{sym}: la orden se lleno JUSTO al cancelarla (orden fantasma) "
                      f"-> la tomo como entrada.")
            return self._on_entered(sym, order.id)
        self._log(f"{sym}: sin llenado -> siguiente simbolo")
        return None

    def _on_entered(self, sym: str, order_id: str) -> Position | None:
        self._safe_cancel(order_id)  # por si quedo remanente (llenado parcial)
        pos, ok = self._get_positions()
        if not ok:
            self._log(f"{sym}: entre pero no puedo leer la posicion -> FRENO por seguridad.")
            self._abort = True
            self._resume.set()
            return None
        p = next((x for x in pos if x.symbol == sym), None)
        if p is not None:
            lado = "LARGO" if p.is_long else "CORTO"
            self._log(f"{sym}: >>> LLENADO: {lado} {abs(p.quantity)} @ {p.avg_price:.2f}")
        return p

    # ===================== Tanda 2: salida =====================
    def manage_exit(self, pos: Position) -> Outcome:
        sym = pos.symbol
        if self._cfg.wait_before_exit_s > 0:
            self._log(f"{sym}: espero {self._cfg.wait_before_exit_s:.0f}s antes de cubrir...")
            self._clock.sleep(self._cfg.wait_before_exit_s)

        baseline = self._elegir_baseline(sym, pos)
        levels = [lv for lv in self._cfg.exit_levels if lv.enabled][:4]
        if not levels:
            self._log(f"{sym}: no hay niveles de salida activos -> dejo la posicion abierta")
            return Outcome.MANUAL_NO_EXIT

        exit_side = Side.SELL if pos.is_long else Side.BUY_TO_COVER
        qty = abs(pos.quantity)
        order: Order | None = None
        precio_orden: float | None = None   # precio al que esta la orden viva
        for i, level in enumerate(levels, 1):
            if self._stopped or self._abort:
                break
            q, ok = self._get_quote(sym)
            if not ok:
                continue
            # GUARDIA antes de mandar/repreciar ESTE nivel (usa la misma cotizacion
            # que ya pedimos para calcular el precio: no agrega llamadas ni demora).
            # Cubre la rendija del cambio de nivel: si el precio ya se escapo, no
            # mandamos la orden del nivel con el mercado caido.
            action = self._guard_action(q, pos, baseline)
            if action == GuardAction.MANUAL:
                if order is not None and self._cancel_and_check_fill(order.id) \
                        and self._is_flat(sym):
                    self._log(f"{sym}: la salida se lleno JUSTO al cancelarla (orden fantasma).")
                    return Outcome.CLOSED
                return Outcome.MANUAL_GUARD
            if action == GuardAction.FORCE_EXIT:
                self._force_exit(order.id if order is not None else None, sym, pos)
                return Outcome.CLOSED
            price = self._exit_price(pos, level, q)
            etiqueta = "CRUZAR el spread" if level.cross else f"@ {price:.2f}"
            self._log(f"{sym}: salida nivel {i} {etiqueta}  (timeout {level.timeout_s:.0f}s)")
            if order is None:
                order, ok = self._place(
                    OrderRequest(sym, exit_side, qty, price, OrderType.LIMIT, self._cfg.duration)
                )
                if not ok:
                    order = None
                    continue
                precio_orden = price
            elif not level.cross and price == precio_orden:
                # el tope al promedio dejo este nivel al MISMO precio que el anterior:
                # no repreciamos (ahorra una llamada, y en Alpaca evita una orden
                # nueva). Solo le damos su tiempo con el timeout del nivel.
                self._log(f"{sym}: nivel {i} queda al mismo precio ({price:.2f}) -> "
                          f"no reprecio, espero")
            else:
                devuelta, ok = self._safe_order(
                    lambda: self._broker.modify_order(order.id, price=price), f"{sym}: modificar salida"
                )
                if not ok and not self._ya_lleno(order.id):
                    continue
                if ok:
                    # si el broker reemplazo la orden por una nueva (Alpaca), seguimos
                    # esa: si no, la de cierre quedaria viva y sin control del bot
                    order = self._orden_vigente(order, devuelta)
                    precio_orden = price

            res = self._wait_exit_fill(order.id, level.timeout_s, sym, pos, baseline)
            if res == "filled":
                self._log(f"{sym}: salida completada en el nivel {i}.")
                return Outcome.CLOSED
            if res == "guard_manual":
                if self._cancel_and_check_fill(order.id) and self._is_flat(sym):
                    self._log(f"{sym}: la salida se lleno JUSTO al cancelarla (orden fantasma).")
                    return Outcome.CLOSED
                return Outcome.MANUAL_GUARD
            if res == "guard_force":
                self._force_exit(order.id, sym, pos)
                return Outcome.CLOSED

        if order is not None and self._cancel_and_check_fill(order.id):
            if self._is_flat(sym):
                self._log(f"{sym}: la salida se lleno JUSTO al cancelarla (orden fantasma).")
                return Outcome.CLOSED
            self._log(f"{sym}: llenado PARCIAL al cancelar la salida; queda posicion abierta.")
        if self._abort:
            return Outcome.ABORTED
        return Outcome.MANUAL_NO_EXIT

    def _exit_price(self, pos: Position, level: ExitLevel, q: Quote) -> float:
        if pos.is_long:
            if level.cross:
                return round(q.bid, 2)          # cruza: vende al bid (SIN tope)
            amount = self._amount(level.offset, level.unit, q)
            price = round(q.ask - amount, 2)    # vende cerca del ask, bajando
            if self._cfg.no_cerrar_bajo_promedio:
                # piso: no vender por DEBAJO del promedio. Redondeo el piso HACIA
                # ARRIBA al centavo para que nunca quede ni medio centavo peor.
                piso = math.ceil(pos.avg_price * 100) / 100.0
                price = max(price, piso)
            return price
        if level.cross:
            return round(q.ask, 2)              # cruza: compra al ask (SIN tope)
        amount = self._amount(level.offset, level.unit, q)
        price = round(q.bid + amount, 2)        # compra cerca del bid, subiendo
        if self._cfg.no_cerrar_bajo_promedio:
            # techo: no comprar por ENCIMA del promedio (redondeo hacia abajo)
            techo = math.floor(pos.avg_price * 100) / 100.0
            price = min(price, techo)
        return price

    def _elegir_baseline(self, sym: str, pos: Position):
        """Referencia del guardia segun la opcion elegida:
        - ENTRY_CALC (default): el bid/ask con el que se CALCULO la orden de
          entrada. Cubre el golpe que ocurre justo al entrar (el guardia lo ve).
        - EXIT_START: el bid/ask leido recien al arrancar el cierre (anterior).
        Si no hay referencia de entrada guardada (ej. no entramos en este ciclo),
        cae a la lectura al arrancar el cierre."""
        g = self._cfg.guard
        if g is None or not g.enabled:
            return None
        if g.reference == GuardReference.ENTRY_CALC and self._entry_ref is not None:
            self._log(
                f"{sym}: guardia mide desde {self._entry_ref:.2f} "
                f"(precio de calculo de la entrada)"
            )
            return self._entry_ref
        return self._guard_baseline(sym, pos)

    def _guard_baseline(self, sym: str, pos: Position):
        q, ok = self._get_quote(sym)
        if not ok:
            return None
        return q.bid if pos.is_long else q.ask

    def _check_guard(self, sym: str, pos: Position, baseline):
        g = self._cfg.guard
        if g is None or not g.enabled or baseline is None:
            return None
        q, ok = self._get_quote(sym)
        if not ok:
            return None
        return self._guard_action(q, pos, baseline)

    def _guard_action(self, q: Quote, pos: Position, baseline):
        """Evalua el guardia contra una cotizacion YA leida (no llama al broker)."""
        g = self._cfg.guard
        if g is None or not g.enabled or baseline is None:
            return None
        sym = pos.symbol
        adverse = (baseline - q.bid) if pos.is_long else (q.ask - baseline)
        threshold = g.threshold if g.unit == GuardUnit.DOLLARS else (g.threshold / 100.0) * baseline
        if adverse >= threshold:
            self._log(
                f"{sym}: GUARDIA -> movimiento en contra {adverse:.2f} >= umbral {threshold:.2f}"
            )
            return g.action
        return None

    def _wait_exit_fill(self, order_id, timeout_s, sym, pos, baseline) -> str:
        deadline = self._clock.now() + timeout_s
        while True:
            if self._is_flat(sym):
                return "filled"
            action = self._check_guard(sym, pos, baseline)
            if action == GuardAction.MANUAL:
                return "guard_manual"
            if action == GuardAction.FORCE_EXIT:
                return "guard_force"
            if self._stopped or self._abort or self._clock.now() >= deadline:
                return "timeout"
            self._clock.sleep(min(self._cfg.poll_interval_s, deadline - self._clock.now()))

    def _force_exit(self, order_id: str | None, sym: str, pos: Position) -> None:
        """Cruza el spread para salir YA. Si todavia no hay orden de salida viva
        (el guardia salto antes de mandar el primer nivel), la manda nueva."""
        q, ok = self._get_quote(sym)
        if not ok:
            return
        cross = q.bid if pos.is_long else q.ask
        self._log(f"{sym}: SALIDA FORZADA -> cruzo el spread a {cross:.2f}")
        if order_id is None:
            side = Side.SELL if pos.is_long else Side.BUY_TO_COVER
            _, ok = self._place(
                OrderRequest(sym, side, abs(pos.quantity), cross,
                             OrderType.LIMIT, self._cfg.duration)
            )
            if not ok:
                return
        else:
            self._safe_order(
                lambda: self._broker.modify_order(order_id, price=cross), f"{sym}: salida forzada"
            )
        deadline = self._clock.now() + 5
        while not self._is_flat(sym) and not self._stopped and self._clock.now() < deadline:
            self._clock.sleep(self._cfg.poll_interval_s)

    def _is_flat(self, sym: str) -> bool:
        pos, ok = self._get_positions()
        if not ok:
            return False  # conservador: si no se que pasa, NO asumo que cerro
        return all(p.symbol != sym for p in pos)

    def _announce(self, outcome: Outcome, sym: str) -> None:
        if outcome == Outcome.CLOSED:
            self._log(f"{sym}: posicion CERRADA. Volve a iniciar el bot para la proxima.")
        elif outcome == Outcome.MANUAL_GUARD:
            self._log(
                f"*** {sym}: GUARDIA DISPARADO -> PASO A MANUAL. "
                f"Posicion ABIERTA, cerrala vos. ***"
            )
            self._avisar_manual(sym, por_guardia=True)
        elif outcome == Outcome.MANUAL_NO_EXIT:
            self._log(
                f"*** {sym}: los niveles no cerraron -> PASO A MANUAL. Posicion ABIERTA. ***"
            )
            self._avisar_manual(sym)
        elif outcome == Outcome.ABORTED:
            self._log(
                f"*** {sym}: BOT DETENIDO por errores del broker. Revisa la posicion a mano. ***"
            )

    def _avisar_manual(self, sym: str, por_guardia: bool = False) -> None:
        """La posicion queda en manos del usuario: avisa a quien este escuchando
        (la pantalla lo usa para cargar el simbolo en el ladder automaticamente;
        por_guardia=True distingue el disparo del guardia, que es mas urgente).
        Si el aviso falla, el motor sigue igual: nunca frena por esto."""
        try:
            self._on_manual(sym, por_guardia)
        except Exception:  # noqa: BLE001
            pass

    # ===================== calculos comunes =====================
    def _entry_price(self, quote: Quote, oc: OrderConfig) -> float:
        amount = self._amount(oc.offset, oc.unit, quote)
        if self._cfg.side == Side.BUY:
            price = quote.bid + amount
        else:  # SELL_SHORT
            price = quote.ask - amount
        return round(price, 2)

    @staticmethod
    def _amount(offset: float, unit: OffsetUnit, quote: Quote) -> float:
        if unit == OffsetUnit.DOLLARS:
            return offset
        return (offset / 100.0) * quote.spread

    def _spread_ok(self, spread: float) -> bool:
        if self._cfg.spread_min is not None and spread < self._cfg.spread_min:
            return False
        if self._cfg.spread_max is not None and spread > self._cfg.spread_max:
            return False
        return True

    def _volume_ok(self, volume: int) -> bool:
        """Volumen TOTAL operado en el dia (acumulado hasta este momento)."""
        if self._cfg.volume_min is not None and volume < self._cfg.volume_min:
            return False
        if self._cfg.volume_max is not None and volume > self._cfg.volume_max:
            return False
        return True

    # ===================== ordenes (entrada) =====================
    def _wait_fill(self, order_id: str, timeout_s: float) -> bool:
        deadline = self._clock.now() + timeout_s
        while True:
            o, ok = self._get_order(order_id)
            if ok:
                if o.filled_quantity > 0 or o.status == OrderStatus.FILLED:
                    return True
                if o.status in (OrderStatus.CANCELED, OrderStatus.REJECTED):
                    return False
            if self._stopped or self._abort or self._clock.now() >= deadline:
                return False
            self._clock.sleep(min(self._cfg.poll_interval_s, deadline - self._clock.now()))

    def _entered_after_wait(self, order_id: str, timeout_s: float) -> bool:
        if self._wait_fill(order_id, timeout_s):
            return True
        return self._ya_lleno(order_id)

    def _ya_lleno(self, order_id: str) -> bool:
        o, ok = self._get_order(order_id)
        return bool(ok and (o.filled_quantity > 0 or o.status == OrderStatus.FILLED))

    def _reprice(self, order: Order, sym: str, new_price: float) -> tuple[Order | None, bool]:
        """Reprecia la orden. Devuelve (orden_o_None, ya_se_lleno)."""
        if self._cfg.reprice_mode == "modify":
            try:
                devuelta = self._broker.modify_order(order.id, price=new_price)
                self._order_strikes = 0
                self._read_fails = 0
                # si el broker reemplazo la orden por una nueva (Alpaca), seguimos esa
                return self._orden_vigente(order, devuelta), False
            except Exception as e:  # noqa: BLE001
                if self._ya_lleno(order.id):
                    self._log(f"{sym}: la orden ya se habia llenado al intentar modificar.")
                    return order, True
                self._order_strikes += 1
                self._log(
                    f"{sym}: no se pudo modificar ({e})"
                    f"  [{self._order_strikes}/{self._cfg.max_strikes}]"
                )
                self._check_abort()
                if self._abort:
                    return None, False
                self._log(f"{sym}: cancelo y mando nueva")
        # cancelar + mandar nueva
        if self._ya_lleno(order.id):
            return order, True
        self._safe_cancel(order.id)
        nueva, ok = self._place(
            OrderRequest(sym, self._cfg.side, self._cfg.quantity, new_price,
                         OrderType.LIMIT, self._cfg.duration)
        )
        if not ok:
            return None, False
        return nueva, False

    def _orden_vigente(self, anterior: Order, devuelta) -> Order:
        """Cual es la orden que hay que seguir despues de un 'modificar precio'.

        OJO, diferencia GRANDE entre brokers (comprobado el 22/07/2026):
          - Tradier MODIFICA la orden: conserva el mismo id.
          - Alpaca la REEMPLAZA: cancela la vieja y crea una NUEVA con OTRO id.
        Si nos quedamos con el id viejo en Alpaca, despues cancelamos una orden que
        ya estaba muerta y la NUEVA queda huerfana: viva, fuera del control del bot,
        congelando el poder de compra y -lo peor- pudiendo llenarse sola y dejar una
        posicion que nadie maneja. Por eso, si el broker devuelve un id distinto,
        seguimos ESE."""
        nuevo_id = getattr(devuelta, "id", None)
        if not nuevo_id or str(nuevo_id) == str(anterior.id):
            return anterior          # Tradier: mismo id, no cambia nada
        return Order(
            id=str(nuevo_id),
            symbol=anterior.symbol,
            side=anterior.side,
            quantity=anterior.quantity,
            price=getattr(devuelta, "price", 0.0) or anterior.price,
            type=anterior.type,
            duration=anterior.duration,
            status=OrderStatus.PENDING,
        )

    def _safe_cancel(self, order_id: str) -> None:
        """Cancelar es 'best effort': si falla (la orden ya no esta) no cuenta strike."""
        if not order_id:
            return
        try:
            o = self._broker.get_order(order_id)
            if o.is_active:
                self._broker.cancel_order(order_id)
        except Exception:
            pass

    def _cancel_and_check_fill(self, order_id: str) -> bool:
        """Cancela la orden y VERIFICA su estado final. Devuelve True si en
        realidad se llenó (total o parcialmente) justo al cancelarla: la
        'orden fantasma' (carrera cancelar/llenarse)."""
        if not order_id:
            return False
        if self._ya_lleno(order_id):
            return True
        self._safe_cancel(order_id)
        return self._ya_lleno(order_id)
