"""
Streaming de market data de Tradier por WebSocket (SOLO LECTURA de precios).

Mecanica:
  1. POST a /v1/markets/events/session con el token de PRODUCCION -> sessionid.
  2. Conectar al WebSocket wss://ws.tradier.com/v1/markets/events.
  3. Enviar {"symbols": [...], "sessionid": ..., "filter": ["quote"], "linebreak": true}.
  4. Por cada mensaje 'quote' -> on_quote(symbol, bid, ask, bidsz, asksz).
  5. Si se corta, reconecta solo.

IMPORTANTE: este token (produccion) se usa SOLO para leer precios en vivo.
NUNCA se mandan ordenes con el (las ordenes van al sandbox por otro lado).
Corre en su propio hilo.
"""
from __future__ import annotations

import configparser
import json
import os
import threading
import time
from typing import Callable

import requests
import websocket

SESSION_URL = "https://api.tradier.com/v1/markets/events/session"
WS_URL = "wss://ws.tradier.com/v1/markets/events"


class TradierMarketStream:
    def __init__(self, token: str) -> None:
        self._token = token
        self._symbols: list[str] = []
        self._on_quote: Callable | None = None
        self._ws = None
        self._sessionid = None
        self._thread = None
        self._stop = False
        self._conectado = False

    @classmethod
    def from_credentials(cls, path: str | None = None) -> "TradierMarketStream":
        if path is None:
            root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            path = os.path.join(root, "config", "credentials.ini")
        cfg = configparser.ConfigParser()
        if not cfg.read(path):
            raise FileNotFoundError(f"No encontre el archivo de credenciales: {path}")
        token = cfg["tradier"].get("production_token", "").strip()
        if not token or token.startswith("PEGA_"):
            raise ValueError("No hay token de produccion cargado para el streaming.")
        return cls(token)

    # ---------- control ----------
    def start(self, symbols, on_quote: Callable) -> None:
        self._symbols = list(symbols)
        self._on_quote = on_quote
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set_symbols(self, symbols) -> None:
        self._symbols = list(symbols)
        # Tradier permite cambiar los simbolos reenviando el payload (sin reconectar).
        if self._ws is not None:
            try:
                self._ws.send(self._payload())
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
        """True si el WebSocket esta conectado (aunque no lleguen datos: la accion
        puede estar simplemente quieta). False si la conexion se cayo/reconectando."""
        return self._conectado

    # ---------- interno ----------
    def _create_session(self) -> str:
        r = requests.post(
            SESSION_URL,
            headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["stream"]["sessionid"]

    def _payload(self) -> str:
        return json.dumps({
            "symbols": self._symbols,
            "sessionid": self._sessionid,
            "filter": ["quote"],
            "linebreak": True,
        })

    def _run(self) -> None:
        while not self._stop:
            try:
                self._sessionid = self._create_session()
                self._ws = websocket.create_connection(WS_URL, timeout=15)
                self._ws.send(self._payload())
                self._conectado = True
                while not self._stop:
                    try:
                        msg = self._ws.recv()
                    except websocket.WebSocketTimeoutException:
                        # No llegaron datos (accion quieta / mercado cerrado): confirmo
                        # que la conexion sigue viva con un ping. Si el ping falla, murio.
                        try:
                            self._ws.ping()
                            continue
                        except Exception:
                            break
                    if not msg:
                        continue
                    for line in str(msg).splitlines():
                        line = line.strip()
                        if line:
                            self._handle(line)
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
                time.sleep(2)  # esperar antes de reconectar

    def _handle(self, line: str) -> None:
        try:
            data = json.loads(line)
        except Exception:
            return
        if data.get("type") != "quote":
            return
        sym = data.get("symbol")
        if not sym or self._on_quote is None:
            return
        try:
            bid = float(data.get("bid") or 0)
            ask = float(data.get("ask") or 0)
            bidsz = float(data.get("bidsz") or 0)
            asksz = float(data.get("asksz") or 0)
        except (TypeError, ValueError):
            return
        self._on_quote(sym, bid, ask, bidsz, asksz)
