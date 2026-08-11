"""
Streaming de precios de TASTYTRADE (protocolo DXLink de dxFeed).

Mismo contrato que los otros streams de la app (Tradier y Alpaca), asi que la
pantalla y el bot lo usan sin enterarse de con cual hablan:

    start(symbols, on_quote, on_trade)   set_symbols(symbols)   stop()

    on_quote(simbolo, bid, ask, bid_size, ask_size)
    on_trade(simbolo, precio, cantidad, exchange, epoch)      <- Time & Sales

COMO FUNCIONA (documentado en developer.tastytrade.com/streaming-market-data):

  1. Se le pide un token al broker: GET /api-quote-tokens devuelve el token y la
     direccion del websocket. Dura 24 h, asi que se pide en cada conexion.
  2. Sobre el websocket va una conversacion con un orden OBLIGATORIO:
        SETUP -> (llega AUTH_STATE: UNAUTHORIZED) -> AUTH
              -> (llega AUTH_STATE: AUTHORIZED)   -> CHANNEL_REQUEST
              -> (llega CHANNEL_OPENED)           -> FEED_SETUP
              -> FEED_SUBSCRIPTION
     Si se manda algo antes de tiempo, DXLink lo rechaza.
  3. Hay que mandar KEEPALIVE cada 30 s o cortan a los 60.

FORMATO DE LOS DATOS: se pide "COMPACT", que ahorra mucho ancho de banda pero
viene sin nombres: por cada tipo de evento llega una lista PLANA con los valores,
uno atras del otro, en el mismo orden en que se pidieron los campos en FEED_SETUP.
Por eso aca se cortan de a N (N = cantidad de campos de ese evento). Ejemplo real:

    ["Trade", ["Trade","SPY",559.36,1.37e7,100.0, "Trade","AAPL",210.5,...]]

Los valores que faltan vienen como el texto "NaN".
"""
from __future__ import annotations

import json
import threading
import time
from typing import Callable

import websocket

# Campos que se piden por evento. El ORDEN importa: asi vienen los valores.
CAMPOS_QUOTE = ["eventType", "eventSymbol", "bidPrice", "askPrice", "bidSize", "askSize"]
CAMPOS_TRADE = ["eventType", "eventSymbol", "price", "size", "dayVolume"]

CANAL = 3          # numero de canal (lo elegimos nosotros)
KEEPALIVE_S = 30   # cortan a los 60 s sin señales de vida


def _num(v) -> float:
    """Los faltantes vienen como el texto 'NaN'."""
    try:
        f = float(v)
        return 0.0 if f != f else f      # NaN != NaN
    except (TypeError, ValueError):
        return 0.0


class TastytradeMarketStream:
    def __init__(self, proveedor_token: Callable[[], tuple[str, str]]) -> None:
        """`proveedor_token` devuelve (token, url) pidiendoselos al broker."""
        self._proveedor_token = proveedor_token
        self._symbols: list[str] = []
        self._on_quote: Callable | None = None
        self._on_trade: Callable | None = None
        self._ws = None
        self._thread = None
        self._stop = False
        self._conectado = False
        self._lock = threading.Lock()

    @classmethod
    def from_credentials(cls, environment: str = "production") -> "TastytradeMarketStream":
        from .tastytrade import TastytradeBroker

        def traer_token() -> tuple[str, str]:
            b = TastytradeBroker.from_credentials(environment=environment)
            js = b._pedir("GET", "/api-quote-tokens")
            d = js.get("data", {})
            token = str(d.get("token") or "")
            url = str(d.get("dxlink-url") or "")
            if not token or not url:
                raise RuntimeError("Tastytrade no dio el token de cotizaciones.")
            return token, url

        return cls(traer_token)

    # ---------- control (mismo contrato que Tradier y Alpaca) ----------
    def start(self, symbols, on_quote: Callable, on_trade: Callable | None = None) -> None:
        self._symbols = [s.upper() for s in symbols if s]
        self._on_quote = on_quote
        self._on_trade = on_trade
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set_symbols(self, symbols) -> None:
        nuevos = [s.upper() for s in symbols if s]
        anteriores = self._symbols
        self._symbols = nuevos
        if self._ws is None or not self._conectado:
            return
        quitar = [s for s in anteriores if s not in nuevos]
        agregar = [s for s in nuevos if s not in anteriores]
        try:
            if quitar:
                self._enviar({"type": "FEED_SUBSCRIPTION", "channel": CANAL,
                              "remove": self._suscripciones(quitar)})
            if agregar:
                self._enviar({"type": "FEED_SUBSCRIPTION", "channel": CANAL,
                              "add": self._suscripciones(agregar)})
        except Exception:  # noqa: BLE001
            pass

    def stop(self) -> None:
        self._stop = True
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:  # noqa: BLE001
                pass

    def esta_conectado(self) -> bool:
        return self._conectado

    # ---------- interno ----------
    def _enviar(self, mensaje: dict) -> None:
        """Los envios se serializan: el keepalive sale del mismo hilo que el resto,
        pero set_symbols puede llegar desde la pantalla."""
        with self._lock:
            self._ws.send(json.dumps(mensaje))

    def _suscripciones(self, symbols) -> list[dict]:
        tipos = ["Quote"] + (["Trade"] if self._on_trade else [])
        return [{"type": t, "symbol": s} for s in symbols for t in tipos]

    def _esperar(self, tipo: str, condicion=None, segundos: float = 15.0) -> dict | None:
        """Espera un mensaje de cierto tipo (DXLink exige respetar el orden)."""
        fin = time.monotonic() + segundos
        while time.monotonic() < fin and not self._stop:
            try:
                crudo = self._ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            if not crudo:
                continue
            try:
                msg = json.loads(crudo)
            except ValueError:
                continue
            if msg.get("type") == tipo and (condicion is None or condicion(msg)):
                return msg
        return None

    def _saludo(self, token: str) -> None:
        """La conversacion inicial, en el orden que exige DXLink."""
        self._enviar({"type": "SETUP", "channel": 0, "version": "0.1-bot-trading/1.0",
                      "keepaliveTimeout": 60, "acceptKeepaliveTimeout": 60})
        # espera a que diga que NO estamos autorizados y recien ahi manda el token
        if self._esperar("AUTH_STATE", lambda m: m.get("state") == "UNAUTHORIZED") is None:
            raise RuntimeError("DXLink no pidio autorizacion")
        self._enviar({"type": "AUTH", "channel": 0, "token": token})
        if self._esperar("AUTH_STATE", lambda m: m.get("state") == "AUTHORIZED") is None:
            raise RuntimeError("DXLink rechazo el token")

        self._enviar({"type": "CHANNEL_REQUEST", "channel": CANAL, "service": "FEED",
                      "parameters": {"contract": "AUTO"}})
        if self._esperar("CHANNEL_OPENED") is None:
            raise RuntimeError("DXLink no abrio el canal")

        campos = {"Quote": CAMPOS_QUOTE}
        if self._on_trade:
            campos["Trade"] = CAMPOS_TRADE
        self._enviar({"type": "FEED_SETUP", "channel": CANAL,
                      "acceptAggregationPeriod": 0.1,
                      "acceptDataFormat": "COMPACT",
                      "acceptEventFields": campos})
        if self._symbols:
            self._enviar({"type": "FEED_SUBSCRIPTION", "channel": CANAL, "reset": True,
                          "add": self._suscripciones(self._symbols)})

    def _run(self) -> None:
        while not self._stop:
            try:
                token, url = self._proveedor_token()
                self._ws = websocket.create_connection(url, timeout=10)
                self._saludo(token)
                self._conectado = True
                ultimo_keepalive = time.monotonic()
                while not self._stop:
                    if time.monotonic() - ultimo_keepalive >= KEEPALIVE_S:
                        self._enviar({"type": "KEEPALIVE", "channel": 0})
                        ultimo_keepalive = time.monotonic()
                    try:
                        crudo = self._ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue          # sin datos: el keepalive de arriba alcanza
                    if crudo:
                        self._handle(crudo)
            except Exception:  # noqa: BLE001
                pass                      # se reintenta abajo
            finally:
                self._conectado = False
                try:
                    if self._ws is not None:
                        self._ws.close()
                except Exception:  # noqa: BLE001
                    pass
            if not self._stop:
                time.sleep(2)             # esperar antes de reconectar

    def _handle(self, crudo: str) -> None:
        try:
            msg = json.loads(crudo)
        except ValueError:
            return
        if msg.get("type") != "FEED_DATA":
            return
        datos = msg.get("data") or []
        # puede venir como ["Quote", [...]] o como varios grupos seguidos
        grupos = [datos] if (datos and isinstance(datos[0], str)) else datos
        for grupo in grupos:
            try:
                nombre, valores = grupo[0], grupo[1]
            except (IndexError, TypeError):
                continue
            campos = CAMPOS_QUOTE if nombre == "Quote" else (
                CAMPOS_TRADE if nombre == "Trade" else None)
            if campos is None or not isinstance(valores, list):
                continue
            n = len(campos)
            # la lista viene PLANA: varios eventos pegados, de a n valores
            for i in range(0, len(valores) - n + 1, n):
                self._evento(nombre, valores[i:i + n])

    def _evento(self, nombre: str, v: list) -> None:
        sym = str(v[1] or "").upper()
        if not sym:
            return
        try:
            if nombre == "Quote" and self._on_quote is not None:
                # eventType, eventSymbol, bidPrice, askPrice, bidSize, askSize
                self._on_quote(sym, _num(v[2]), _num(v[3]), _num(v[4]), _num(v[5]))
            elif nombre == "Trade" and self._on_trade is not None:
                # eventType, eventSymbol, price, size, dayVolume
                # DXLink no manda el exchange en este evento: va vacio
                self._on_trade(sym, _num(v[2]), _num(v[3]), "", time.time())
        except Exception:  # noqa: BLE001
            pass          # un evento raro no corta el stream
