"""
Avisos de CUENTA de Tradier por WebSocket (cambios de estado de las ordenes).

Para que sirve: sin esto, la app se enteraba de que una orden se puso, se ejecuto
o se cancelo recien en el proximo sondeo (cada 4 segundos). Con esto, Tradier avisa
al instante (medido: ~200 ms) y la pantalla se refresca en el momento.

Mecanica:
  1. POST a /v1/accounts/events/session con el token -> sessionid.
  2. Conectar a wss://ws.tradier.com/v1/accounts/events
  3. Enviar {"events": ["order"], "sessionid": ..., "excludeAccounts": []}
  4. Por cada mensaje de orden -> on_event(dict)
  5. Si se corta, reconecta solo.

OJO: el aviso de Tradier trae el id y el estado de la orden, pero NO el simbolo ni
el lado. Por eso se usa como DISPARADOR ("algo cambio, refresca ya") y los datos
completos se leen despues, en vez de intentar reconstruir la orden desde el aviso.

SOLO LECTURA: este canal escucha, nunca manda ordenes. Corre en su propio hilo.
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

SESSION_URL = "https://api.tradier.com/v1/accounts/events/session"
WS_URL = "wss://ws.tradier.com/v1/accounts/events"


class TradierAccountStream:
    def __init__(self, token: str) -> None:
        self._token = token
        self._on_event: Callable | None = None
        self._ws = None
        self._sessionid = None
        self._thread = None
        self._stop = False
        self._conectado = False

    @classmethod
    def from_credentials(
        cls, path: str | None = None, environment: str = "production"
    ) -> "TradierAccountStream":
        if environment != "production":
            raise ValueError(
                "El sandbox de Tradier no ofrece avisos de cuenta por streaming."
            )
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
            raise ValueError("No hay token de produccion para los avisos de cuenta.")
        return cls(token)

    # ---------- control ----------
    def start(self, on_event: Callable) -> None:
        self._on_event = on_event
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
    def _create_session(self) -> str:
        r = requests.post(
            SESSION_URL,
            headers={"Authorization": f"Bearer {self._token}",
                     "Accept": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["stream"]["sessionid"]

    def _run(self) -> None:
        while not self._stop:
            try:
                self._sessionid = self._create_session()
                self._ws = websocket.create_connection(WS_URL, timeout=20)
                self._ws.send(json.dumps({
                    "events": ["order"],
                    "sessionid": self._sessionid,
                    "excludeAccounts": [],
                }))
                self._conectado = True
                while not self._stop:
                    try:
                        msg = self._ws.recv()
                    except websocket.WebSocketTimeoutException:
                        try:
                            self._ws.ping()   # distingue "sin novedades" de "caido"
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

    def _handle(self, msg) -> None:
        if self._on_event is None:
            return
        for linea in str(msg).splitlines():
            linea = linea.strip()
            if not linea:
                continue
            try:
                data = json.loads(linea)
            except Exception:
                continue
            if data.get("event") == "order":
                try:
                    self._on_event(data)
                except Exception:
                    pass
