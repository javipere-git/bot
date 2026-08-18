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

    def catalogo(self) -> list[dict]:
        """Todo lo que el broker sabe de cada simbolo que lista, en una pasada.

        Sirve para dos cosas: saber cuales tiene BLOQUEADAS para abrir posicion (y
        no gastar una orden que va a rechazar), y bajarlo a un archivo para mirarlo
        con calma.

        Cada fila trae las mismas claves en todos los brokers, con None donde ese
        broker no informa el dato:
            symbol, bloqueada, operable, prestable, costo_prestamo,
            iliquida, marca_fraude, overnight_bloqueada, mercado

        Medido el 15/08/2026: Alpaca paper 14.234 simbolos en 1,8 s (una llamada,
        863 bloqueadas), Tastytrade produccion 13.194 en 7,5 s (14 paginas, 394
        bloqueadas). Tradier no lo ofrece.

        Si el conector tuvo que sacar la lista de otro lado que el esperable, lo
        deja escrito en self.catalogo_origen para que la pantalla lo muestre (le
        pasa a Tasty: su sandbox no marca ninguna bloqueada).

        Lista vacia = este broker no lo tiene."""
        return []

    #: explicacion de DONDE salio el ultimo catalogo, cuando no es lo obvio.
    #: None = del broker al que estas conectado, como corresponde.
    catalogo_origen: str | None = None

    def operaciones(self, desde: str, hasta: str) -> list[dict]:
        """Todas las EJECUCIONES de la cuenta entre dos fechas (YYYY-MM-DD).

        Ojo con la diferencia: una ORDEN es lo que pediste, una EJECUCION es lo que
        de verdad se hizo. Una orden puede llenarse en varios pedazos, a precios
        distintos, o no llenarse nunca. Esto devuelve lo segundo, que es lo que sirve
        para revisar como te fue.

        Cada fila trae las mismas claves en todos los brokers, con None donde ese
        broker no informa el dato:
            fecha_hora (hora de NY), symbol, lado, cantidad, precio, importe,
            comision, tasas, neto, order_id, id_ejecucion, notas

        Medido el 17/08/2026 sobre 30 dias: Alpaca 3.008 ejecuciones en 6,9 s (31
        paginas), Tradier 3.526 en 1,6 s (una llamada), Tastytrade 252 en 0,6 s.

        Lista vacia = este broker no lo tiene."""
        return []

    def ordenes_historicas(self, desde: str, hasta: str) -> list[dict]:
        """Todas las ORDENES entre dos fechas (YYYY-MM-DD), con su estado final.

        Distinto de operaciones(): aca esta lo que PEDISTE, se haya hecho o no.
        Sirve para ver que se cancelo, que se rechazo y por que.

        Cada fila trae las mismas claves en todos los brokers, con None donde ese
        broker no informa el dato:
            fecha_hora (hora de NY), symbol, lado, cantidad, cantidad_ejecutada,
            precio_limite, precio_promedio, estado, motivo_rechazo, duracion,
            order_id, notas

        'estado' es siempre uno de: Ejecutada, Cancelada, Rechazada, Reemplazada,
        Vencida, Viva. Cada broker los nombra distinto y el conector traduce.

        Medido el 17/08/2026 sobre 30 dias: Alpaca 500 por pagina, Tastytrade 5.883
        (100 por pagina, con el MOTIVO del rechazo escrito). TRADIER NO LO OFRECE:
        su endpoint de ordenes solo guarda las del DIA.

        Lista vacia = este broker no lo tiene."""
        return []

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
