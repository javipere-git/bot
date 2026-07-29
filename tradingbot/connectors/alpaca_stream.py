"""
Streaming de market data de Alpaca por WebSocket (SOLO LECTURA de precios).

Mecanica:
  1. Conectar a wss://stream.data.alpaca.markets/v2/{feed}  (feed = iex o sip).
  2. Autenticar: {"action":"auth","key":...,"secret":...} -> espera "authenticated".
  3. Suscribir: {"action":"subscribe","quotes":[SIMBOLO]}.
  4. Por cada mensaje de quote (T="q") -> on_quote(symbol, bid, ask, bidsz, asksz).
  5. Si se corta, reconecta solo.

feed:
  - "iex"  (plan gratuito): UN solo exchange -> NO es el NBBO real.
  - "sip"  (plan Algo Trader Plus): NBBO consolidado real.

Mismo "contrato" que TradierMarketStream (start/set_symbols/stop/esta_conectado),
asi la pantalla lo usa igual sin saber cual es. Corre en su propio hilo.
"""
from __future__ import annotations

import configparser
import json
import os
import threading
import time
from datetime import datetime
from typing import Callable

import websocket


def _epoch(iso) -> float:
    """Hora ISO de Alpaca -> segundos desde 1970 (para mostrarla en hora local)."""
    try:
        txt = str(iso)
        if "." in txt:                       # recorta los nanosegundos
            cabeza, resto = txt.split(".", 1)
            txt = f"{cabeza}.{resto[:6].rstrip('Z')}+00:00"
        else:
            txt = txt.replace("Z", "+00:00")
        return datetime.fromisoformat(txt).timestamp()
    except Exception:  # noqa: BLE001
        return time.time()


class AlpacaMarketStream:
    def __init__(self, key: str, secret: str, feed: str = "iex") -> None:
        self._key = key
        self._secret = secret
        self._feed = feed
        self._url = f"wss://stream.data.alpaca.markets/v2/{feed}"
        self._symbols: list[str] = []
        self._on_quote: Callable | None = None
        self._on_trade: Callable | None = None   # Time & Sales (operaciones)
        self._ws = None
        self._thread = None
        self._stop = False
        self._conectado = False

    @classmethod
    def from_credentials(
        cls, path: str | None = None, environment: str = "paper"
    ) -> "AlpacaMarketStream":
        if path is None:
            root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            path = os.path.join(root, "config", "credentials.ini")
        cfg = configparser.ConfigParser()
        if not cfg.read(path):
            raise FileNotFoundError(f"No encontre el archivo de credenciales: {path}")
        sec = cfg["alpaca"]
        if environment == "live":
            key = sec.get("live_key_id", "").strip()
            secret = sec.get("live_secret", "").strip()
        else:
            key = sec.get("paper_key_id", "").strip()
            secret = sec.get("paper_secret", "").strip()
        if not key or not secret:
            raise ValueError("Faltan las claves de Alpaca para el streaming.")
        feed = sec.get("data_feed", "iex").strip().lower() or "iex"
        return cls(key, secret, feed)

    # ---------- control (mismo contrato que Tradier) ----------
    def start(self, symbols, on_quote: Callable, on_trade: Callable | None = None) -> None:
        self._symbols = list(symbols)
        self._on_quote = on_quote
        self._on_trade = on_trade
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set_symbols(self, symbols) -> None:
        nuevos = list(symbols)
        anteriores = self._symbols
        self._symbols = nuevos
        if self._ws is None:
            return
        try:
            # dar de baja los viejos y de alta los nuevos
            quitar = [s for s in anteriores if s not in nuevos]
            if quitar:
                self._ws.send(json.dumps(self._msg("unsubscribe", quitar)))
            if nuevos:
                self._ws.send(json.dumps(self._msg("subscribe", nuevos)))
        except Exception:
            pass

    def stop(self) -> None:
        self._stop = True
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass

    def esta_conectado(self) -> bool:
        return self._conectado

    # ---------- interno ----------
    def _msg(self, accion: str, simbolos: list) -> dict:
        """Mensaje de (des)suscripcion. Solo pide 'trades' si alguien escucha el
        Time & Sales, para no recibir mensajes al pedo."""
        m = {"action": accion, "quotes": list(simbolos)}
        if self._on_trade:
            m["trades"] = list(simbolos)
        return m

    def _run(self) -> None:
        while not self._stop:
            try:
                self._ws = websocket.create_connection(self._url, timeout=15)
                # 1) mensaje de bienvenida ("connected"); 2) auth; 3) esperar "authenticated"
                self._ws.recv()
                self._ws.send(json.dumps(
                    {"action": "auth", "key": self._key, "secret": self._secret}
                ))
                if not self._espera_auth():
                    raise RuntimeError("Alpaca stream: autenticacion rechazada")
                if self._symbols:
                    self._ws.send(json.dumps(self._msg("subscribe", self._symbols)))
                self._conectado = True
                while not self._stop:
                    try:
                        msg = self._ws.recv()
                    except websocket.WebSocketTimeoutException:
                        try:
                            self._ws.ping()
                            continue
                        except Exception:
                            break
                    if msg:
                        self._handle(msg)
            except Exception:
                pass
            finally:
                self._conectado = False
                try:
                    if self._ws is not None:
                        self._ws.close()
                except Exception:
                    pass
                self._ws = None
            if not self._stop:
                time.sleep(2)

    def _espera_auth(self) -> bool:
        """Lee mensajes hasta ver 'authenticated' (o falla)."""
        for _ in range(5):
            try:
                msg = self._ws.recv()
            except Exception:
                return False
            for item in self._items(msg):
                if item.get("T") == "success" and item.get("msg") == "authenticated":
                    return True
                if item.get("T") == "error":
                    return False
        return False

    @staticmethod
    def _items(msg) -> list[dict]:
        try:
            data = json.loads(msg)
        except Exception:
            return []
        return data if isinstance(data, list) else [data]

    def _handle(self, msg) -> None:
        for item in self._items(msg):
            tipo = item.get("T")
            sym = item.get("S")
            if not sym:
                continue
            if tipo == "q" and self._on_quote is not None:
                try:
                    bid = float(item.get("bp") or 0)
                    ask = float(item.get("ap") or 0)
                    bidsz = float(item.get("bs") or 0)
                    asksz = float(item.get("as") or 0)
                except (TypeError, ValueError):
                    continue
                self._on_quote(sym, bid, ask, bidsz, asksz)
            elif tipo == "t" and self._on_trade is not None:
                # operacion ejecutada: {"T":"t","S":sym,"p":precio,"s":cant,
                #  "x":exchange,"t":"2026-07-29T02:35:54.123Z"}
                try:
                    precio = float(item.get("p") or 0)
                    cant = float(item.get("s") or 0)
                except (TypeError, ValueError):
                    continue
                if precio <= 0:
                    continue
                self._on_trade(sym, precio, cant, str(item.get("x") or ""),
                               _epoch(item.get("t")))
