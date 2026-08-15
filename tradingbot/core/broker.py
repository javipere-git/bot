"""
La 'interfaz comun': el enchufe generico contra el que habla el cerebro.

El cerebro NUNCA le habla a Tradier directo. Le habla a esta interfaz.
Cada broker real (Tradier, y en el futuro Alpaca, IBKR...) se implementa
como una clase que hereda de Broker y completa estos metodos.

Para agregar un broker nuevo: se escribe un conector nuevo. Nada mas.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from .models import DayPnL, Fill, Order, OrderRequest, OrderStatus, Position, Quote


class Broker(ABC):

    # ---------- Lectura (no toca dinero) ----------
    @abstractmethod
    def get_account_id(self) -> str:
        """Devuelve el identificador de la cuenta."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Lista las posiciones abiertas."""

    @abstractmethod
    def get_open_orders(self) -> list[Order]:
        """Lista las ordenes vivas (todavia no ejecutadas ni canceladas)."""

    @abstractmethod
    def get_closed_orders(self) -> list[Order]:
        """Lista las ordenes del dia ya cerradas (ejecutadas, canceladas, rechazadas)."""

    def get_orders(self, limit: int | None = None) -> list[Order]:
        """Ordenes del dia (vivas + cerradas) en una sola consulta.

        limit=N devuelve solo las N MAS RECIENTES (mucho mas rapido en dias con
        cientos/miles de ordenes). Sin limit devuelve TODAS.
        Por defecto junta las dos listas; un conector puede sobreescribirlo si
        el broker permite traer todo de una (Tradier lo hace, con paginas)."""
        todas = self.get_open_orders() + self.get_closed_orders()
        return todas[-limit:] if limit else todas

    @abstractmethod
    def get_order(self, order_id: str) -> Order:
        """Devuelve una orden por su id, con su estado actual (open/filled/...)."""

    def orden_de_aviso(self, evento) -> tuple[str | None, "OrderStatus | None", Order | None]:
        """Traduce un aviso del canal de cuenta a datos de una orden.

        Cuando el broker avisa que una orden cambio, ese aviso YA trae informacion
        que hasta ahora tirabamos para despues volver a preguntarsela. Esto la
        aprovecha: la pantalla puede confirmar la orden al instante y sin gastar
        una sola llamada.

        Devuelve (id, estado, orden_completa). Cada broker manda distinto:
          - Alpaca y Tastytrade -> la orden ENTERA (los tres datos)
          - Tradier             -> solo id y estado (no manda ni el simbolo ni el
                                   lado), asi que sirve para actualizar una orden
                                   que ya conocemos, no para armar una de cero.

        Por defecto no entiende ningun aviso: el que no lo implemente sigue
        funcionando como siempre, con la lectura de respaldo."""
        return (None, None, None)

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        """Ultima cotizacion conocida de un simbolo."""

    def get_buying_power(self) -> float | None:
        """Poder de compra disponible AHORA. None = el broker no lo informa.

        Ojo: las ordenes limite puestas (aunque no se hayan llenado) CONGELAN su
        costo, y al cancelarlas el broker puede tardar en devolverlo. Por eso este
        numero puede ser menor que el efectivo de la cuenta."""
        return None

    def lista_etb(self) -> list[str]:
        """Simbolos EASY TO BORROW: los que este broker deja vender en corto.

        OJO, es del broker donde se OPERA, no del que da los precios: con el perfil
        hibrido (opera en Alpaca, precios de Tradier) tiene que devolver la lista de
        ALPACA, que es quien va a aceptar o rechazar el short.

        Lista vacia = el broker no lo informa.
        """
        return []

    def distingue_venta_en_corto(self) -> bool:
        """True si el broker distingue 'sell' de 'sell_short'.

        Tradier SI: una 'sell' de mas que la posicion la RECHAZA, lo que funciona como
        red de seguridad. Alpaca NO: solo tiene buy/sell, asi que una venta estando sin
        posicion abre un CORTO en silencio. Cuando esto es False, la app pone la red de
        seguridad por su cuenta (ver LadderPanel._mandar)."""
        return True

    def puede_operar_en_corto(self) -> bool | None:
        """Si la cuenta admite ventas en corto. None = el broker no lo informa.

        Sirve para avisar ANTES de arrancar, en vez de comerse una orden rechazada
        atras de otra (ej. las cuentas de Alpaca sin margen no permiten shortear)."""
        return None

    def get_day_pnl(self) -> DayPnL | None:
        """Resultado del DIA segun el broker (realizado + no realizado).

        Devuelve None si el broker no lo informa; en ese caso la pantalla cae a
        calcular solo el no realizado con las posiciones abiertas."""
        return None

    # ---------- Ordenes (en desarrollo: SIEMPRE sandbox) ----------
    @abstractmethod
    def place_order(self, request: OrderRequest) -> Order:
        """Manda una orden nueva."""

    @abstractmethod
    def modify_order(
        self,
        order_id: str,
        *,
        price: float | None = None,
        quantity: int | None = None,
        duration=None,
    ) -> Order:
        """Modifica (re-precia) una orden viva. Esto es el 'replace'.

        `duration`: la duracion que YA tiene la orden (day / pre / post). Hay brokers
        que la exigen al modificar y rechazan la orden si se les manda otra distinta
        (Tradier: "pre and post market orders cannot modify duration"). Los que no la
        necesitan la ignoran.

        Se usa para pasar de la Orden 1 a la Orden 2, para los escalones de
        salida, y para arrastrar una orden a otro nivel en el ladder.
        """

    @abstractmethod
    def cancel_order(self, order_id: str) -> None:
        """Cancela una orden viva."""

    # ---------- Streaming (avisos en vivo) ----------
    @abstractmethod
    def subscribe_quotes(
        self, symbols: list[str], on_quote: Callable[[Quote], None]
    ) -> None:
        """Se suscribe a cotizaciones en vivo. Llama a on_quote por cada una."""

    @abstractmethod
    def subscribe_account(self, on_fill: Callable[[Fill], None]) -> None:
        """Se suscribe a avisos de la cuenta (ejecuciones). Llama a on_fill."""
