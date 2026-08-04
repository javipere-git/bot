"""
Conector de Alpaca (cuenta PAPER: dinero simulado).

Traduce la interfaz comun (Broker) a las llamadas REST de Alpaca. Igual que el
conector de Tradier, pero con las manas propias de Alpaca:
  - Autenticacion por DOS headers (key id + secret), no un Bearer token.
  - Las ordenes van como JSON (Tradier las pide como formulario).
  - Dos direcciones distintas: una para operar (paper-api) y otra para precios
    (data.alpaca.markets).
  - Alpaca NO distingue "vender en corto" de "vender": para el lado usa solo
    buy/sell. La traduccion lo resuelve (sell_short -> sell, buy_to_cover -> buy).
  - El precio y el volumen del dia vienen del "snapshot" (feed IEX en el plan
    gratuito; SIP requiere suscripcion).

ALCANCE: cuenta PAPER solamente. La cuenta real de Alpaca (live) NO se cablea
aca: seria una decision explicita aparte, con salvaguardas, igual que Tradier.
"""
from __future__ import annotations

import configparser
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from ..core.broker import Broker
from ..core.horarios import es_sesion_overnight, inicio_dia_operativo
from .alpaca_trade_stream import AlpacaTradeStream
from ..core.models import (
    DayPnL,
    Duration,
    Fill,
    Order,
    OrderRequest,
    OrderStatus,
    OrderType,
    Position,
    Quote,
    Side,
)

PAPER_TRADING_BASE = "https://paper-api.alpaca.markets"  # operar (dinero simulado)
LIVE_TRADING_BASE = "https://api.alpaca.markets"         # operar (DINERO REAL)
DATA_BASE = "https://data.alpaca.markets"                # precios (market data)

# Alpaca usa muchos nombres de estado; los llevamos a los nuestros.
_STATUS_MAP = {
    "new": OrderStatus.OPEN,
    "accepted": OrderStatus.OPEN,
    "pending_new": OrderStatus.PENDING,
    "accepted_for_bidding": OrderStatus.OPEN,
    "held": OrderStatus.OPEN,
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    "filled": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELED,
    "cancelled": OrderStatus.CANCELED,
    "expired": OrderStatus.CANCELED,
    "done_for_day": OrderStatus.CANCELED,
    "replaced": OrderStatus.CANCELED,   # la reemplazo una nueva: esta ya no vive
    "rejected": OrderStatus.REJECTED,
    "suspended": OrderStatus.PENDING,
    "pending_cancel": OrderStatus.OPEN,
    "pending_replace": OrderStatus.OPEN,
    "calculated": OrderStatus.PENDING,
    "stopped": OrderStatus.OPEN,
}

# nuestro lado -> lado de Alpaca (solo buy/sell)
_SIDE_A_ALPACA = {
    Side.BUY: "buy",
    Side.BUY_TO_COVER: "buy",
    Side.SELL: "sell",
    Side.SELL_SHORT: "sell",
}


# ---------------------------------------------------------------------------
# Hub de AVISOS DE CUENTA compartido: un solo trade stream + cache por cuenta.
# Asi, en vez de preguntarle a Alpaca "¿ya se lleno?" cada 0.5s (agota el limite
# de 200/min), el stream nos avisa y el bot lee el estado de un cache local.
# SEGURIDAD: si el stream no esta conectado, get_order/get_positions vuelven solos
# a preguntar por REST (el comportamiento de siempre). El stream es una mejora que,
# si falla, degrada a lo seguro; nunca deja al bot operando con datos viejos.
# ---------------------------------------------------------------------------
def _parse_order_dict(o: dict) -> Order:
    """Traduce una orden de Alpaca (de REST o del stream) a nuestro modelo."""
    try:
        side = Side(o["side"])   # Alpaca manda 'buy'/'sell', que existen en Side
    except (ValueError, KeyError):
        side = Side.BUY
    try:
        otype = OrderType(o.get("type", "limit"))
    except ValueError:
        otype = OrderType.LIMIT
    status = _STATUS_MAP.get(str(o.get("status", "")).lower(), OrderStatus.PENDING)
    return Order(
        id=str(o["id"]),
        symbol=o["symbol"],
        side=side,
        quantity=int(float(o.get("qty") or 0)),
        price=float(o.get("limit_price") or 0.0),
        type=otype,
        duration=Duration.DAY,      # Alpaca no usa pre/post: lo dice en extended_hours
        extended=bool(o.get("extended_hours")),
        status=status,
        filled_quantity=int(float(o.get("filled_qty") or 0)),
        avg_fill_price=float(o.get("filled_avg_price") or 0.0),
        create_date=str(o.get("created_at") or o.get("submitted_at") or ""),
        transaction_date=str(o.get("updated_at") or o.get("filled_at") or ""),
    )


_HUBS: dict[str, "_FillsHub"] = {}
_HUBS_LOCK = threading.Lock()


def detener_streams_de_cuenta() -> None:
    """Para todos los streams de avisos abiertos (llamar al cerrar la app)."""
    with _HUBS_LOCK:
        for hub in _HUBS.values():
            hub.stop()
        _HUBS.clear()


class _FillsHub:
    """Un solo stream de avisos + cache de ESTADO DE ORDENES por cuenta. El bot lee
    de aca en vez de preguntar '¿ya se lleno?' por REST. Solo cachea ORDENES (no
    posiciones): las posiciones se siguen leyendo por REST para conservar el precio
    promedio y el P/L, y su polling intenso solo ocurre en salidas esporadicas."""

    def __init__(self, environment: str) -> None:
        self.ordenes: dict[str, Order] = {}   # id -> Order (estado en vivo)
        self._lock = threading.Lock()
        self._stream = AlpacaTradeStream.from_credentials(environment=environment)
        self._stream.start(self._on_update)

    def vivo(self) -> bool:
        return self._stream.esta_conectado()

    def stop(self) -> None:
        self._stream.stop()

    def _on_update(self, orden: dict, evento: str, pos_qty) -> None:
        oid = str(orden.get("id") or "")
        if not oid:
            return
        try:
            parseada = _parse_order_dict(orden)
        except Exception:  # noqa: BLE001
            return
        with self._lock:
            self.ordenes[oid] = parseada

    def get_order(self, oid: str):
        with self._lock:
            return self.ordenes.get(str(oid))


class AlpacaBroker(Broker):
    ORDENES_POR_PAGINA = 500  # maximo que Alpaca da por pagina

    def __init__(
        self,
        key_id: str,
        secret: str,
        trading_base: str = PAPER_TRADING_BASE,
        feed: str = "iex",
    ) -> None:
        self._key = key_id
        self._secret = secret
        self._trading_base = trading_base   # paper o live (dinero real)
        self._es_live = trading_base == LIVE_TRADING_BASE
        self._feed = feed  # 'iex' (gratis) o 'sip' (suscripcion)
        self._cache_volumen: dict[str, tuple] = {}  # volumen de la rueda (overnight)
        self._account_id = ""
        self._environment = "live" if self._es_live else "paper"
        self._session = requests.Session()
        self._session.headers.update(
            {
                "APCA-API-KEY-ID": key_id,
                "APCA-API-SECRET-KEY": secret,
                "Accept": "application/json",
            }
        )
        self.last_rate_limit: dict[str, str] = {}
        self._hub = self._obtener_hub()

    def _obtener_hub(self) -> "_FillsHub":
        """Stream de avisos de cuenta COMPARTIDO por todos los conectores de esta
        cuenta (una sola conexion). Alimenta el cache de estado de ordenes; si el
        stream se cae, get_order vuelve solo a preguntar por REST."""
        clave = f"{self._key}@{self._environment}"
        with _HUBS_LOCK:
            hub = _HUBS.get(clave)
            if hub is None:
                try:
                    hub = _FillsHub(self._environment)
                    _HUBS[clave] = hub
                except Exception:  # noqa: BLE001
                    hub = None       # sin stream: se opera por REST, como siempre
        return hub

    @classmethod
    def from_credentials(
        cls, path: str | None = None, environment: str = "paper"
    ) -> "AlpacaBroker":
        """Crea el conector leyendo config/credentials.ini (seccion [alpaca]).

        environment='paper' (simulado) usa paper_key_id/paper_secret.
        environment='live' (DINERO REAL) usa live_key_id/live_secret; solo funciona
        si esas claves estan cargadas (gatillo final, lo pega el usuario)."""
        if environment not in ("paper", "live"):
            raise ValueError("environment debe ser 'paper' o 'live'")
        if path is None:
            root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            path = os.path.join(root, "config", "credentials.ini")
        cfg = configparser.ConfigParser()
        if not cfg.read(path):
            raise FileNotFoundError(f"No encontre el archivo de credenciales: {path}")
        if not cfg.has_section("alpaca"):
            raise ValueError("Falta la seccion [alpaca] en config/credentials.ini")

        if environment == "paper":
            key = cfg["alpaca"].get("paper_key_id", "").strip()
            secret = cfg["alpaca"].get("paper_secret", "").strip()
            base = PAPER_TRADING_BASE
            if not key or not secret:
                raise ValueError(
                    "Faltan las claves de Alpaca paper (paper_key_id / paper_secret) "
                    "en config/credentials.ini"
                )
        else:  # live -- DINERO REAL
            key = cfg["alpaca"].get("live_key_id", "").strip()
            secret = cfg["alpaca"].get("live_secret", "").strip()
            base = LIVE_TRADING_BASE
            if not key or not secret:
                raise ValueError(
                    "Alpaca LIVE deshabilitado: faltan live_key_id / live_secret en "
                    "config/credentials.ini (son las claves de tu cuenta REAL de Alpaca; "
                    "las pega el usuario, nunca el asistente)."
                )
        feed = cfg["alpaca"].get("data_feed", "iex").strip().lower() or "iex"
        return cls(key, secret, trading_base=base, feed=feed)

    # ---------- helpers internos ----------
    def _send(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_body: dict | None = None,
        base: str | None = None,
    ) -> Any:
        if base is None:
            base = self._trading_base   # paper o live, segun este conector
        resp = self._session.request(
            method, f"{base}{path}", params=params, json=json_body, timeout=15
        )
        self._capturar_cupo(resp)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Alpaca {method} {path} -> HTTP {resp.status_code}: {resp.text[:300]}"
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def _get(self, path: str, params: dict | None = None, base: str | None = None):
        return self._send("GET", path, params=params, base=base)

    def _capturar_cupo(self, resp) -> None:
        """Guarda el cupo de llamadas que Alpaca informa en cada respuesta."""
        self.last_rate_limit = {
            k: resp.headers[k]
            for k in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset")
            if k in resp.headers
        }

    # ---------- Lectura ----------
    def get_account_id(self) -> str:
        if not self._account_id:
            data = self._get("/v2/account")
            self._account_id = str(data.get("account_number", ""))
        return self._account_id

    def get_positions(self) -> list[Position]:
        data = self._get("/v2/positions")
        out: list[Position] = []
        for p in data or []:
            qty_abs = abs(int(float(p.get("qty", 0))))
            signed = qty_abs if p.get("side") == "long" else -qty_abs
            avg = float(p.get("avg_entry_price") or 0.0)
            out.append(Position(symbol=p["symbol"], quantity=signed, avg_price=round(avg, 4)))
        return out

    def get_buying_power(self) -> float | None:
        acc = self._get("/v2/account") or {}
        try:
            return float(acc.get("buying_power"))
        except (TypeError, ValueError):
            return None

    def lista_etb(self) -> list[str]:
        """Easy To Borrow de Alpaca: sale del campo easy_to_borrow de cada activo.
        Una sola llamada trae los ~14.000 activos; se filtran los que ademas son
        shortable (Alpaca SOLO deja shortear ETB, y sin costo de prestamo)."""
        data = self._get("/v2/assets",
                         params={"status": "active", "asset_class": "us_equity"})
        if not isinstance(data, list):
            return []
        return sorted({
            str(a.get("symbol", "")).upper() for a in data
            if a.get("easy_to_borrow") and a.get("shortable") and a.get("symbol")
        })

    def distingue_venta_en_corto(self) -> bool:
        """NO: Alpaca solo tiene buy/sell. Vender estando sin posicion abre un corto
        sin avisar (le paso al usuario: quedo corto sin querer)."""
        return False

    def puede_operar_en_corto(self) -> bool | None:
        acc = self._get("/v2/account") or {}
        valor = acc.get("shorting_enabled")
        return bool(valor) if valor is not None else None

    def get_day_pnl(self) -> DayPnL | None:
        """Resultado del dia en Alpaca:
          total del dia = equity actual - equity del cierre anterior (last_equity)
          no realizado  = suma del unrealized_intraday_pl de las posiciones
          realizado     = total - no realizado"""
        acc = self._get("/v2/account") or {}
        try:
            equity = float(acc.get("equity") or 0.0)
            last_equity = float(acc.get("last_equity") or 0.0)
        except (TypeError, ValueError):
            return None
        if not last_equity:
            return None
        total = equity - last_equity
        no_realizado = 0.0
        for p in (self._get("/v2/positions") or []):
            try:
                no_realizado += float(
                    p.get("unrealized_intraday_pl") or p.get("unrealized_pl") or 0.0
                )
            except (TypeError, ValueError):
                pass
        return DayPnL(realizado=total - no_realizado, no_realizado=no_realizado)

    @staticmethod
    def _after_hoy() -> str:
        """Desde cuando pedirle las ordenes a Alpaca (Tradier ya filtra por dia,
        Alpaca NO -> devolvia tambien las de ayer).

        Es el inicio del DIA OPERATIVO (04:00 ET), no la medianoche: asi la sesion
        overnight queda incluida. Antes se usaba 'hoy a las 05:00 UTC', que durante
        el overnight caia en el FUTURO y escondia todas las ordenes."""
        return inicio_dia_operativo().strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_orders(self, limit: int | None = None) -> list[Order]:
        """Ordenes de HOY (vivas + cerradas). Alpaca da hasta 500 por pagina; si hay
        mas, pagina hacia atras por fecha (como el fix de Tradier). Una orden con
        formato raro se saltea sin romper la lista.

        limit=N -> las N MAS RECIENTES en una sola llamada (direction=desc)."""
        if limit:
            lote = self._get("/v2/orders", params={
                "status": "all", "limit": min(limit, self.ORDENES_POR_PAGINA),
                "direction": "desc", "nested": "false", "after": self._after_hoy(),
            }) or []
            recientes: list[Order] = []
            for o in lote:
                try:
                    recientes.append(self._parse_order(o))
                except Exception:  # noqa: BLE001
                    continue
            return recientes

        out: list[Order] = []
        until: str | None = None
        for _ in range(20):  # salvavidas: hasta 10.000 ordenes
            params = {
                "status": "all",
                "limit": self.ORDENES_POR_PAGINA,
                "direction": "desc",
                "nested": "false",
                "after": self._after_hoy(),   # solo las de hoy
            }
            if until:
                params["until"] = until
            lote = self._get("/v2/orders", params=params) or []
            if not lote:
                break
            for o in lote:
                try:
                    out.append(self._parse_order(o))
                except Exception:  # noqa: BLE001
                    continue
            if len(lote) < self.ORDENES_POR_PAGINA:
                break
            until = lote[-1].get("submitted_at") or lote[-1].get("created_at")
            if not until:
                break
        return out

    def get_open_orders(self) -> list[Order]:
        # Las VIVAS de cualquier dia (status=open, SIN filtro de fecha): asi
        # "Cancelar todo" no deja afuera una orden viva que hubiera quedado de antes.
        lote = self._get("/v2/orders", params={
            "status": "open", "limit": self.ORDENES_POR_PAGINA,
            "direction": "desc", "nested": "false",
        }) or []
        out: list[Order] = []
        for o in lote:
            try:
                out.append(self._parse_order(o))
            except Exception:  # noqa: BLE001
                continue
        return out

    def get_closed_orders(self) -> list[Order]:
        return [o for o in self.get_orders() if not o.is_active]

    def get_order(self, order_id: str) -> Order:
        # Si el stream de avisos esta vivo y ya nos conto de esta orden, la leemos
        # del cache (0 llamadas a la API). Si no -stream caido o orden que el stream
        # aun no vio-, preguntamos por REST, como siempre. La seguridad manda: ante
        # la duda, REST.
        if self._hub is not None and self._hub.vivo():
            cacheada = self._hub.get_order(order_id)
            if cacheada is not None:
                return cacheada
        data = self._get(f"/v2/orders/{order_id}")
        if not data:
            raise ValueError(f"No encontre la orden {order_id}")
        return self._parse_order(data)

    def feed_actual(self) -> str:
        """Que feed de datos corresponde AHORA.

        En la sesion overnight (20:00-04:00 ET) el consolidado (SIP) no publica
        nada: hay que pedir el feed de Blue Ocean ('boats'). En el resto del dia,
        el feed configurado (sip o iex)."""
        if self._feed != "iex" and es_sesion_overnight():
            return "boats"
        return self._feed

    def get_quote(self, symbol: str) -> Quote:
        # el snapshot trae la cotizacion Y el volumen del dia en una sola llamada
        feed = self.feed_actual()
        data = self._get(
            f"/v2/stocks/{symbol}/snapshot",
            params={"feed": feed}, base=DATA_BASE,
        )
        lq = (data or {}).get("latestQuote") or {}
        db = (data or {}).get("dailyBar") or {}
        volumen = int(float(db.get("v") or 0))
        if feed == "boats":
            # De noche el feed de Blue Ocean solo cuenta el volumen de la sesion
            # nocturna: SPY daba 35.530 en vez de 67.002.681. Con el filtro de
            # volumen puesto, eso saltearia TODOS los simbolos. El volumen del dia
            # se pide al feed de la rueda regular (que de noche ya no cambia, asi
            # que se cachea). Los PRECIOS siguen saliendo de boats, igual que antes.
            volumen = self._volumen_rueda(symbol) or volumen
        return Quote(
            symbol=symbol,
            bid=float(lq.get("bp") or 0.0),
            ask=float(lq.get("ap") or 0.0),
            bid_size=int(lq.get("bs") or 0),
            ask_size=int(lq.get("as") or 0),
            volume=volumen,
        )

    CACHE_VOL_S = 300.0    # de noche la rueda esta cerrada: el volumen no cambia

    def _volumen_rueda(self, symbol: str) -> int:
        """Volumen del dia de la RUEDA REGULAR, para usar durante el overnight."""
        ahora = time.monotonic()
        guardado = self._cache_volumen.get(symbol)
        if guardado is not None and ahora - guardado[0] < self.CACHE_VOL_S:
            return guardado[1]
        try:
            data = self._get(
                f"/v2/stocks/{symbol}/snapshot",
                params={"feed": self._feed}, base=DATA_BASE,
            )
            vol = int(float(((data or {}).get("dailyBar") or {}).get("v") or 0))
        except Exception:  # noqa: BLE001
            return 0       # si falla, se usa lo que haya (nunca frena la lectura)
        self._cache_volumen[symbol] = (ahora, vol)
        return vol

    def _parse_order(self, o: dict) -> Order:
        return _parse_order_dict(o)

    # ---------- Ordenes ----------
    def place_order(self, request: OrderRequest) -> Order:
        body = {
            "symbol": request.symbol,
            "qty": str(request.quantity),
            "side": _SIDE_A_ALPACA[request.side],
            "type": request.type.value,
            "time_in_force": "day",   # el bot opera siempre en DAY
        }
        if request.type == OrderType.LIMIT:
            body["limit_price"] = f"{request.price:.2f}"
        if request.extended:
            # habilita pre-market, post-market y overnight (Blue Ocean).
            # Alpaca exige que sea limite; sin esto la orden espera a la apertura.
            body["extended_hours"] = True
        data = self._send("POST", "/v2/orders", json_body=body)
        return Order(
            id=str((data or {}).get("id", "")),
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            type=request.type,
            duration=request.duration,
            status=OrderStatus.PENDING,
        )

    def modify_order(
        self, order_id: str, *, price: float | None = None, quantity: int | None = None,
        duration=None,
    ) -> Order:
        # `duration` se acepta por compatibilidad con la interfaz comun pero no se usa:
        # Alpaca conserva el horario extendido de la orden al reemplazarla (a Tradier
        # SI hay que repetirsela, si no rechaza las de pre/post market).
        # A diferencia de Tradier, Alpaca SI permite cambiar la cantidad al reemplazar.
        body: dict[str, str] = {}
        if price is not None:
            body["limit_price"] = f"{price:.2f}"
        if quantity is not None:
            body["qty"] = str(quantity)
        data = self._send("PATCH", f"/v2/orders/{order_id}", json_body=body)
        # Alpaca crea una orden NUEVA al reemplazar (id nuevo); devolvemos esa.
        node = data or {}
        return Order(
            id=str(node.get("id", order_id)),
            symbol=str(node.get("symbol", "")),
            side=Side.BUY,
            quantity=int(float(node.get("qty") or (quantity or 0))),
            price=float(node.get("limit_price") or (price or 0.0)),
            status=OrderStatus.PENDING,
        )

    def cancel_order(self, order_id: str) -> None:
        self._send("DELETE", f"/v2/orders/{order_id}")

    # ---------- Streaming: se cablea en un segundo paso ----------
    def subscribe_quotes(
        self, symbols: list[str], on_quote: Callable[[Quote], None]
    ) -> None:
        raise NotImplementedError(
            "El streaming de Alpaca se cablea despues; por ahora el ladder usa "
            "lectura por REST (snapshot)."
        )

    def subscribe_account(self, on_fill: Callable[[Fill], None]) -> None:
        raise NotImplementedError("El streaming de cuenta de Alpaca se cablea despues.")
