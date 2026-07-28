"""
Modelos de datos comunes (el 'idioma' que habla el cerebro).

Estos objetos son genericos: no saben nada de Tradier ni de ningun broker.
Cada conector traduce los datos del broker a estos modelos. Asi el cerebro
siempre trabaja con las mismas piezas, sin importar el broker de abajo.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class Side(str, Enum):
    """Lado de una orden."""
    BUY = "buy"                    # comprar (entrar largo)
    SELL = "sell"                  # vender (salir de largo)
    SELL_SHORT = "sell_short"      # vender en corto (entrar corto)
    BUY_TO_COVER = "buy_to_cover"  # recomprar para cerrar el corto


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class Duration(str, Enum):
    DAY = "day"
    PRE = "pre"    # pre-market (extended hours)
    POST = "post"  # post-market (extended hours)


class OrderStatus(str, Enum):
    PENDING = "pending"            # enviada, todavia sin confirmar
    OPEN = "open"                  # viva en el mercado, esperando llenarse
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"             # ejecutada por completo
    CANCELED = "canceled"
    REJECTED = "rejected"


@dataclass
class Quote:
    """Una cotizacion Level 1: mejor compra (bid) y mejor venta (ask)."""
    symbol: str
    bid: float
    ask: float
    bid_size: int = 0
    ask_size: int = 0
    volume: int = 0   # acciones operadas en el dia (acumulado hasta este momento)
    timestamp: float = field(default_factory=time.time)

    @property
    def spread(self) -> float:
        """Diferencia ask - bid, en dolares."""
        return round(self.ask - self.bid, 4)


@dataclass
class OrderRequest:
    """Lo que el cerebro pide cuando quiere mandar una orden."""
    symbol: str
    side: Side
    quantity: int
    price: float
    type: OrderType = OrderType.LIMIT
    duration: Duration = Duration.DAY


@dataclass
class Order:
    """Una orden tal como vive en el broker."""
    id: str
    symbol: str
    side: Side
    quantity: int
    price: float
    type: OrderType = OrderType.LIMIT
    duration: Duration = Duration.DAY
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    create_date: str = ""          # cuando se creo/envio (ISO de Tradier)
    transaction_date: str = ""     # ultima transaccion (ejecucion / cancelacion)

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity

    @property
    def is_active(self) -> bool:
        """True si la orden sigue viva (puede llenarse o cancelarse)."""
        return self.status in (
            OrderStatus.PENDING,
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
        )


@dataclass
class Position:
    """Una posicion abierta. quantity positivo = largo, negativo = corto."""
    symbol: str
    quantity: int
    avg_price: float

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0


@dataclass
class DayPnL:
    """Resultado del DIA: lo ya cerrado (realizado) + lo que esta abierto."""
    realizado: float       # ganancia/perdida de las posiciones cerradas HOY
    no_realizado: float    # de las posiciones todavia abiertas (precio actual)

    @property
    def total(self) -> float:
        return self.realizado + self.no_realizado


@dataclass
class Fill:
    """Aviso de que (parte de) una orden se ejecuto."""
    order_id: str
    symbol: str
    side: Side
    quantity: int
    price: float
    timestamp: float = field(default_factory=time.time)
