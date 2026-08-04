"""
Broker HIBRIDO: opera en un broker pero toma los PRECIOS de otro.

Motivo: el feed de datos gratuito de Alpaca (IEX) es UN solo exchange, asi que su
bid/ask NO es el NBBO real (puede estar muy corrido, o faltar un lado). Para no
calcular ordenes con precios malos, se ejecuta en Alpaca pero se leen los precios
de Tradier (NBBO consolidado, en tiempo real con el token de produccion).

Todo lo de la CUENTA y las ORDENES (posiciones, mandar, modificar, cancelar) va al
broker de operativa. SOLO las cotizaciones (get_quote) salen del broker de datos.

Es un simple "traductor que reparte": no agrega logica de trading.
"""
from __future__ import annotations

from typing import Callable

from ..core.broker import Broker
from ..core.models import DayPnL, Fill, Order, OrderRequest, Position, Quote


class BrokerHibrido(Broker):
    def __init__(self, operativa: Broker, datos: Broker) -> None:
        self._op = operativa      # donde se opera (ej. Alpaca)
        self._datos = datos       # de donde salen los precios (ej. Tradier)

    # ---------- cuenta / ordenes -> broker de OPERATIVA ----------
    def get_account_id(self) -> str:
        return self._op.get_account_id()

    def get_positions(self) -> list[Position]:
        return self._op.get_positions()

    def get_open_orders(self) -> list[Order]:
        return self._op.get_open_orders()

    def get_closed_orders(self) -> list[Order]:
        return self._op.get_closed_orders()

    def get_orders(self, limit: int | None = None) -> list[Order]:
        return self._op.get_orders(limit=limit)

    def get_order(self, order_id: str) -> Order:
        return self._op.get_order(order_id)

    def get_day_pnl(self) -> DayPnL | None:
        # el resultado es de la CUENTA donde se opera
        return self._op.get_day_pnl()

    def distingue_venta_en_corto(self) -> bool:
        return self._op.distingue_venta_en_corto()

    def puede_operar_en_corto(self) -> bool | None:
        return self._op.puede_operar_en_corto()

    def get_buying_power(self) -> float | None:
        return self._op.get_buying_power()

    def place_order(self, request: OrderRequest) -> Order:
        return self._op.place_order(request)

    def modify_order(self, order_id: str, *, price=None, quantity=None,
                     duration=None) -> Order:
        return self._op.modify_order(order_id, price=price, quantity=quantity,
                                     duration=duration)

    def cancel_order(self, order_id: str) -> None:
        self._op.cancel_order(order_id)

    def subscribe_account(self, on_fill: Callable[[Fill], None]) -> None:
        self._op.subscribe_account(on_fill)

    # ---------- precios -> broker de DATOS ----------
    def get_quote(self, symbol: str) -> Quote:
        return self._datos.get_quote(symbol)

    def subscribe_quotes(
        self, symbols: list[str], on_quote: Callable[[Quote], None]
    ) -> None:
        self._datos.subscribe_quotes(symbols, on_quote)
