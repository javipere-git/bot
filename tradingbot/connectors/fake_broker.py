"""
Conector 'de mentira' (simulado).

No se conecta a ningun broker ni toca dinero de ningun tipo. Vive en memoria.
Sirve para probar el cerebro: le mandas ordenes, moves la cotizacion a mano
con set_quote(), y simula los llenados igual que lo haria un broker real.

Modelo de llenado (simple, Level 1):
- Una COMPRA limite se llena cuando el ask baja hasta tu precio (o menos).
- Una VENTA limite se llena cuando el bid sube hasta tu precio (o mas).
- Una orden 'market' se llena enseguida contra el ask/bid actual.
"""
from __future__ import annotations

import itertools
from typing import Callable

from ..core.broker import Broker
from ..core.models import (
    Fill,
    Order,
    OrderRequest,
    OrderStatus,
    OrderType,
    Position,
    Quote,
    Side,
)

_BUY_SIDES = (Side.BUY, Side.BUY_TO_COVER)


class FakeBroker(Broker):
    def __init__(self, account_id: str = "PAPER-FAKE-001") -> None:
        self._account_id = account_id
        self._quotes: dict[str, Quote] = {}
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, Position] = {}
        self._ids = itertools.count(1)
        self._on_quote: Callable[[Quote], None] | None = None
        self._on_fill: Callable[[Fill], None] | None = None

    # ---------- Lectura ----------
    def get_account_id(self) -> str:
        return self._account_id

    def get_positions(self) -> list[Position]:
        return [p for p in self._positions.values() if p.quantity != 0]

    def get_open_orders(self) -> list[Order]:
        return [o for o in self._orders.values() if o.is_active]

    def get_closed_orders(self) -> list[Order]:
        return [o for o in self._orders.values() if not o.is_active]

    def get_order(self, order_id: str) -> Order:
        return self._orders[order_id]

    def get_quote(self, symbol: str) -> Quote:
        return self._quotes[symbol]

    # ---------- Ordenes ----------
    def place_order(self, request: OrderRequest) -> Order:
        order = Order(
            id=f"FAKE-{next(self._ids)}",
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            type=request.type,
            duration=request.duration,
            status=OrderStatus.OPEN,
        )
        self._orders[order.id] = order
        # Si ya es ejecutable contra la cotizacion actual, se llena enseguida.
        self._try_fill(order)
        return order

    def modify_order(
        self,
        order_id: str,
        *,
        price: float | None = None,
        quantity: int | None = None,
    ) -> Order:
        order = self._orders[order_id]
        if not order.is_active:
            raise ValueError(f"La orden {order_id} ya no esta viva")
        if price is not None:
            order.price = price
        if quantity is not None:
            order.quantity = quantity
        self._try_fill(order)
        return order

    def cancel_order(self, order_id: str) -> None:
        order = self._orders[order_id]
        if order.is_active:
            order.status = OrderStatus.CANCELED

    # ---------- Streaming ----------
    def subscribe_quotes(
        self, symbols: list[str], on_quote: Callable[[Quote], None]
    ) -> None:
        self._on_quote = on_quote

    def subscribe_account(self, on_fill: Callable[[Fill], None]) -> None:
        self._on_fill = on_fill

    # ---------- Simulacion (exclusivo del conector falso) ----------
    def set_quote(
        self,
        symbol: str,
        bid: float,
        ask: float,
        bid_size: int = 100,
        ask_size: int = 100,
        volume: int = 0,
    ) -> None:
        """Mueve la cotizacion a mano (para los tests).

        Avisa al suscriptor de quotes y revisa si alguna orden viva se llena.
        """
        quote = Quote(symbol, bid, ask, bid_size, ask_size, volume)
        self._quotes[symbol] = quote
        if self._on_quote:
            self._on_quote(quote)
        for order in list(self._orders.values()):
            if order.is_active and order.symbol == symbol:
                self._try_fill(order)

    def _try_fill(self, order: Order) -> None:
        quote = self._quotes.get(order.symbol)
        if quote is None:
            return

        fill_price: float | None = None
        if order.side in _BUY_SIDES:
            # Compra: se llena si mi limite alcanza el ask.
            if order.type == OrderType.MARKET or order.price >= quote.ask:
                fill_price = quote.ask
        else:
            # Venta: se llena si mi limite alcanza el bid.
            if order.type == OrderType.MARKET or order.price <= quote.bid:
                fill_price = quote.bid

        if fill_price is None:
            return

        # En el simulador, llenado completo de una sola vez.
        qty = order.remaining_quantity
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.status = OrderStatus.FILLED
        self._apply_to_position(order, qty, fill_price)
        if self._on_fill:
            self._on_fill(
                Fill(order.id, order.symbol, order.side, qty, fill_price)
            )

    def _apply_to_position(self, order: Order, qty: int, price: float) -> None:
        signed = qty if order.side in _BUY_SIDES else -qty
        pos = self._positions.get(order.symbol)
        if pos is None:
            self._positions[order.symbol] = Position(order.symbol, signed, price)
            return

        new_qty = pos.quantity + signed
        if new_qty == 0:
            pos.quantity = 0
        elif (pos.quantity > 0) == (signed > 0):
            # Suma en la misma direccion: promedia el precio.
            total_cost = pos.avg_price * abs(pos.quantity) + price * abs(signed)
            pos.avg_price = total_cost / abs(new_qty)
            pos.quantity = new_qty
        else:
            # Reduce o da vuelta la posicion.
            pos.quantity = new_qty
