"""
Stream de AVISOS DE CUENTA de Alpaca (trade updates) por WebSocket.

En vez de preguntarle a Alpaca "¿ya se lleno?" cada medio segundo (lo que agota
el limite de 200 llamadas/min), Alpaca nos AVISA al instante cada vez que una
orden cambia de estado (se llena, se cancela, se rechaza...).

Mecanica:
  1. Conectar a wss://{paper-api|api}.alpaca.markets/stream
  2. auth: {"action":"auth","key":...,"secret":...}
  3. listen: {"action":"listen","data":{"streams":["trade_updates"]}}
  4. Por cada evento -> on_update(order_dict, event, position_qty)

Detalle: el contenido SIEMPRE es JSON, pero el endpoint de PAPER lo manda en frames
binarios (bytes con el JSON en UTF-8) y el de PRODUCCION en frames de texto. Este
modulo decodifica los dos casos (comprobado en vivo el 22/07/2026).

Corre en su propio hilo. SOLO escucha: nunca manda ordenes.
"""
from __future__ import annotations

import configparser
import json
import os
import threading
import time
from typing import Callable

import websocket

PAPER_STREAM = "wss://paper-api.alpaca.markets/stream"
LIVE_STREAM = "wss://api.alpaca.markets/stream"


class AlpacaTradeStream:
    def __init__(self, key: str, secret: str, url: str) -> None:
        self._key = key
        self._secret = secret
        self._url = url
        self._on_update: Callable | None = None
        self._on_reset: Callable | None = None   # se llama al (re)conectar: resembrar
        self._ws = None
        self._thread = None
        self._stop = False
        self._conectado = False

    @classmethod
    def from_credentials(
        cls, path: str | None = None, environment: str = "paper"
    ) -> "AlpacaTradeStream":
        if path is None:
            root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            path = os.path.join(root, "config", "credentials.ini")
        cfg = configparser.ConfigParser()
        cfg.read(path)
        sec = cfg["alpaca"]
        if environment == "live":
            key = sec.get("live_key_id", "").strip()
            secret = sec.get("live_secret", "").strip()
            url = LIVE_STREAM
        else:
            key = sec.get("paper_key_id", "").strip()
            secret = sec.get("paper_secret", "").strip()
            url = PAPER_STREAM
        if not key or not secret:
            raise ValueError("Faltan las claves de Alpaca para el stream de cuenta.")
        return cls(key, secret, url)

    # ---------- control ----------
    def start(self, on_update: Callable, on_reset: Callable | None = None) -> None:
        self._on_update = on_update
        self._on_reset = on_reset
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

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
    @staticmethod
    def _decodificar(msg) -> list[dict]:
        """El contenido es JSON; el paper lo manda en bytes, produccion en texto."""
        try:
            if isinstance(msg, (bytes, bytearray)):
                msg = msg.decode("utf-8")
            data = json.loads(msg)
        except Exception:
            return []
        return data if isinstance(data, list) else [data]

    def _run(self) -> None:
        while not self._stop:
            try:
                self._ws = websocket.create_connection(self._url, timeout=20)
                self._ws.send(json.dumps(
                    {"action": "auth", "key": self._key, "secret": self._secret}
                ))
                if not self._esperar_auth():
                    raise RuntimeError("Alpaca trade stream: auth rechazada")
                self._ws.send(json.dumps(
                    {"action": "listen", "data": {"streams": ["trade_updates"]}}
                ))
                self._conectado = True
                # avisar que (re)conectamos: quien nos use resiembra el estado por REST
                if self._on_reset is not None:
                    try:
                        self._on_reset()
                    except Exception:
                        pass
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
                        self._procesar(msg)
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

    def _esperar_auth(self) -> bool:
        for _ in range(5):
            try:
                msg = self._ws.recv()
            except Exception:
                return False
            for item in self._decodificar(msg):
                if item.get("stream") == "authorization":
                    return (item.get("data") or {}).get("status") == "authorized"
        return False

    def _procesar(self, msg) -> None:
        if self._on_update is None:
            return
        for item in self._decodificar(msg):
            if item.get("stream") != "trade_updates":
                continue
            data = item.get("data") or {}
            evento = data.get("event")
            orden = data.get("order") or {}
            pos_qty = data.get("position_qty")
            try:
                self._on_update(orden, evento, pos_qty)
            except Exception:
                pass
