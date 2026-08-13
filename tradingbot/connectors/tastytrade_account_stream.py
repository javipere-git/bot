"""
Avisos de CUENTA de Tastytrade (su "Account Streamer").

Para que sirve: sin esto, la pantalla se entera de que una orden se puso, se
movio, se lleno o se cancelo recien en el proximo sondeo, que es cada 4 segundos.
Con Tasty se notaba muchisimo: mandabas una orden desde el ladder y tardaba en
aparecer, y la posicion despues de un llenado tambien. Con este canal el aviso
llega al instante (en Tradier medimos ~200 ms).

Mismo contrato que el de Tradier y el de Alpaca, asi que AccountWorker lo usa sin
enterarse de con cual habla:  start(on_event)   stop()   esta_conectado()

COMO FUNCIONA (developer.tastytrade.com/streaming-account-data):

  1. Se abre el websocket (produccion wss://streamer.tastyworks.com, sandbox
     wss://streamer.cert.tastyworks.com).
  2. Se manda 'connect' con la lista de cuentas y el token de acceso. OJO: el
     token va con 'Bearer ' adelante, igual que en las llamadas REST.
  3. Hay que mandar 'heartbeat' cada pocos segundos (entre 2 s y 1 min) o el
     servidor da la conexion por muerta.
  El ORDEN importa: si se manda 'heartbeat' antes del 'connect', responden un
  error de "not implemented".

Cada aviso trae el objeto COMPLETO (la orden entera, no un pedacito), con un
campo 'type' que dice de que es: Order, AccountBalance, CurrentPosition...
"""
from __future__ import annotations

import json
import threading
import time
from typing import Callable

import websocket

URL_PRODUCCION = "wss://streamer.tastyworks.com"
URL_SANDBOX = "wss://streamer.cert.tastyworks.com"
LATIDO_S = 20        # el rango que acepta Tasty es 2 s a 1 min


class TastytradeAccountStream:
    def __init__(self, proveedor_token: Callable[[], str], cuentas: list[str],
                 sandbox: bool = False) -> None:
        """`proveedor_token` devuelve un access token FRESCO cada vez que se lo
        pide: los de Tasty duran 15 minutos, asi que al reconectar hace falta uno
        nuevo (por eso es una funcion y no un texto fijo)."""
        self._proveedor_token = proveedor_token
        self._cuentas = [c for c in cuentas if c]
        self._url = URL_SANDBOX if sandbox else URL_PRODUCCION
        self._on_event: Callable | None = None
        self._ws = None
        self._thread = None
        self._stop = False
        self._conectado = False
        self._lock = threading.Lock()
        self._pedido = 0

    @classmethod
    def from_credentials(cls, environment: str = "production") -> "TastytradeAccountStream":
        from .tastytrade import TastytradeBroker

        broker = TastytradeBroker.from_credentials(environment=environment)

        def token() -> str:
            return broker._access_token()      # se renueva solo si vencio

        return cls(token, [broker.get_account_id()],
                   sandbox=(environment == "sandbox"))

    # ---------- control (mismo contrato que Tradier y Alpaca) ----------
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
            except Exception:  # noqa: BLE001
                pass

    def esta_conectado(self) -> bool:
        return self._conectado

    # ---------- interno ----------
    def _enviar(self, mensaje: dict) -> None:
        self._pedido += 1
        mensaje["request-id"] = self._pedido
        with self._lock:
            self._ws.send(json.dumps(mensaje))

    def _run(self) -> None:
        while not self._stop:
            try:
                token = self._proveedor_token()
                self._ws = websocket.create_connection(self._url, timeout=10)
                # 1) connect PRIMERO (si no, el heartbeat da "not implemented")
                self._enviar({"action": "connect", "value": self._cuentas,
                              "auth-token": f"Bearer {token}"})
                self._conectado = True
                ultimo_latido = time.monotonic()
                while not self._stop:
                    if time.monotonic() - ultimo_latido >= LATIDO_S:
                        # el token pudo vencer entre medio: se pide de nuevo
                        self._enviar({"action": "heartbeat",
                                      "auth-token": f"Bearer {self._proveedor_token()}"})
                        ultimo_latido = time.monotonic()
                    try:
                        crudo = self._ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue          # sin novedades: el latido de arriba alcanza
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
        # las respuestas a connect/heartbeat traen 'status'; no son novedades
        if msg.get("status") is not None:
            return
        tipo = msg.get("type")
        if not tipo:
            return
        # Order / AccountBalance / CurrentPosition: cualquiera de los tres cambia
        # algo que la pantalla muestra, asi que se avisa igual
        if self._on_event is not None:
            try:
                self._on_event(msg)
            except Exception:  # noqa: BLE001
                pass          # un aviso raro no corta el canal
