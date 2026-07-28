"""
Conector real de Tradier.

Traduce la interfaz comun (Broker) a las llamadas REST de Tradier.

ALCANCE ACTUAL (Fase 2): SOLO LECTURA -> cuenta, posiciones, ordenes y
cotizacion. Mandar / modificar / cancelar ordenes y el streaming se
implementan en fases siguientes (por ahora avisan que todavia no estan).

Apunta al SANDBOX por defecto (dinero simulado).
"""
from __future__ import annotations

import configparser
import os
from typing import Any, Callable

import requests

from ..core.broker import Broker
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

SANDBOX_BASE = "https://sandbox.tradier.com/v1"      # dinero simulado
PRODUCTION_BASE = "https://api.tradier.com/v1"       # cuenta real (solo lectura mas adelante)

# Tradier usa nombres de estado que no calzan 1 a 1 con los nuestros.
_STATUS_MAP = {
    "open": OrderStatus.OPEN,
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    "filled": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELED,
    "cancelled": OrderStatus.CANCELED,
    "expired": OrderStatus.CANCELED,
    "rejected": OrderStatus.REJECTED,
    "error": OrderStatus.REJECTED,
    "pending": OrderStatus.PENDING,
}


def _as_list(node: Any, key: str) -> list[dict]:
    """Tradier devuelve 'null' (texto) si no hay nada, un dict si hay uno,
    o una lista si hay varios. Esto lo normaliza siempre a una lista."""
    if not node or node == "null":
        return []
    inner = node.get(key)
    if inner is None:
        return []
    return inner if isinstance(inner, list) else [inner]


class TradierBroker(Broker):
    def __init__(self, token: str, account_id: str, base_url: str = SANDBOX_BASE) -> None:
        self._token = token
        self._account_id = account_id
        self._base = base_url
        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        )
        self.last_rate_limit: dict[str, str] = {}

    @classmethod
    def from_credentials(
        cls, path: str | None = None, environment: str = "sandbox"
    ) -> "TradierBroker":
        """Crea el conector leyendo config/credentials.ini."""
        if path is None:
            root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            path = os.path.join(root, "config", "credentials.ini")
        cfg = configparser.ConfigParser()
        if not cfg.read(path):
            raise FileNotFoundError(f"No encontre el archivo de credenciales: {path}")

        if environment == "sandbox":
            token = cfg["tradier"]["sandbox_token"]
            account_id = cfg["tradier"]["sandbox_account_id"]
            base = SANDBOX_BASE
        elif environment == "production":
            token = cfg["tradier"].get("production_token", "")
            account_id = cfg["tradier"].get("production_account_id", "")
            base = PRODUCTION_BASE
            if not token:
                raise ValueError("No hay token de produccion cargado.")
            if not account_id:
                raise ValueError(
                    "Falta production_account_id en config/credentials.ini "
                    "(tu numero de cuenta REAL). Es el gatillo final del modo LIVE: "
                    "lo pega el usuario, nunca el asistente."
                )
        else:
            raise ValueError("environment debe ser 'sandbox' o 'production'")

        return cls(token, account_id, base)

    # ---------- helpers internos ----------
    def _send(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        data: dict | None = None,
        timeout: float = 15,
    ) -> dict:
        resp = self._session.request(
            method, f"{self._base}{path}", params=params, data=data, timeout=timeout
        )
        self._capture_rate_limit(resp)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Tradier {method} {path} -> HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json()

    def _get(self, path: str, params: dict | None = None, timeout: float = 15) -> dict:
        return self._send("GET", path, params=params, timeout=timeout)

    def _capture_rate_limit(self, resp: requests.Response) -> None:
        """Guarda el cupo de rate limit que Tradier informa en cada respuesta."""
        self.last_rate_limit = {
            k: resp.headers[k]
            for k in (
                "X-Ratelimit-Allowed",
                "X-Ratelimit-Used",
                "X-Ratelimit-Available",
            )
            if k in resp.headers
        }

    # ---------- Lectura ----------
    def get_account_id(self) -> str:
        return self._account_id

    def get_positions(self) -> list[Position]:
        data = self._get(f"/accounts/{self._account_id}/positions")
        out: list[Position] = []
        for p in _as_list(data.get("positions"), "position"):
            qty = int(float(p["quantity"]))
            cost = float(p.get("cost_basis", 0.0))
            avg = abs(cost / qty) if qty else 0.0
            out.append(Position(symbol=p["symbol"], quantity=qty, avg_price=round(avg, 4)))
        return out

    # Tradier corta la lista de ordenes en paginas de 1500 (confirmado en vivo el
    # 17/07/2026 con 1541 ordenes en el dia: la web y la app de Tradier solo
    # muestran la pagina 1, y las ordenes 1501+ quedan "invisibles" pero VIVAS).
    # Por eso aca pedimos TODAS las paginas.
    ORDENES_POR_PAGINA = 1500
    MAX_PAGINAS = 10  # salvavidas: hasta 15.000 ordenes por dia

    def get_orders(self, limit: int | None = None) -> list[Order]:
        """Ordenes del dia (vivas + cerradas). Una orden con formato inesperado se
        saltea sin romper la lista entera.

        limit=N -> las N MAS RECIENTES en UNA sola llamada (parametros limit + sort=desc,
        verificados en vivo el 21/07/2026). Es ~10x mas rapido: con 1200 ordenes en el
        dia tarda 0.2s contra 2.3s de traerlas todas. Se usa para refrescar la pantalla
        seguido sin saturar (los timeouts/504 venian de pedir todo cada 4 segundos).
        Sin limit -> TODAS, recorriendo las paginas (para no perder ninguna)."""
        if limit:
            data = self._get(
                f"/accounts/{self._account_id}/orders",
                params={"limit": limit, "sort": "desc"},
                timeout=20,
            )
            recientes: list[Order] = []
            for o in _as_list(data.get("orders"), "order"):
                try:
                    recientes.append(self._parse_order(o))
                except Exception:  # noqa: BLE001
                    continue
            return recientes

        out: list[Order] = []
        for page in range(1, self.MAX_PAGINAS + 1):
            # La lista completa del dia es PESADA (cientos/miles de ordenes) y en
            # momentos de carga Tradier tarda mucho -> mas margen que el resto.
            data = self._get(
                f"/accounts/{self._account_id}/orders", params={"page": page},
                timeout=40,
            )
            lote = _as_list(data.get("orders"), "order")
            for o in lote:
                try:
                    out.append(self._parse_order(o))
                except Exception:  # noqa: BLE001
                    continue  # orden rara -> la salteo, no rompo el monitoreo
            if len(lote) < self.ORDENES_POR_PAGINA:
                break  # ultima pagina
        return out

    def get_open_orders(self) -> list[Order]:
        return [o for o in self.get_orders() if o.is_active]

    def get_closed_orders(self) -> list[Order]:
        return [o for o in self.get_orders() if not o.is_active]

    def get_buying_power(self) -> float | None:
        data = self._get(f"/accounts/{self._account_id}/balances")
        bal = data.get("balances") or {}
        margen = bal.get("margin") or {}
        cash = bal.get("cash") or {}
        for valor in (margen.get("stock_buying_power"),
                      cash.get("cash_available"),
                      bal.get("total_cash")):
            if valor is not None:
                try:
                    return float(valor)
                except (TypeError, ValueError):
                    continue
        return None

    def get_day_pnl(self) -> DayPnL | None:
        """Resultado del dia que informa Tradier en 'balances':
          close_pl = realizado de las posiciones CERRADAS hoy
          open_pl  = no realizado de las posiciones abiertas
        (Verificado el 21/07/2026 contra el calculo propio de las ejecuciones
        del dia: close_pl es del DIA, no acumulado.)"""
        data = self._get(f"/accounts/{self._account_id}/balances")
        bal = data.get("balances") or {}
        if not bal:
            return None
        return DayPnL(
            realizado=float(bal.get("close_pl") or 0.0),
            no_realizado=float(bal.get("open_pl") or 0.0),
        )

    def get_order(self, order_id: str) -> Order:
        data = self._get(f"/accounts/{self._account_id}/orders/{order_id}")
        node = data.get("order")
        if not node:
            raise ValueError(f"No encontre la orden {order_id}")
        return self._parse_order(node)

    def get_quote(self, symbol: str) -> Quote:
        data = self._get("/markets/quotes", params={"symbols": symbol})
        quotes = _as_list(data.get("quotes"), "quote")
        if not quotes:
            raise ValueError(f"Tradier no devolvio cotizacion para {symbol}")
        q = quotes[0]
        return Quote(
            symbol=q["symbol"],
            bid=float(q.get("bid") or 0.0),
            ask=float(q.get("ask") or 0.0),
            bid_size=int(q.get("bidsize") or 0),
            ask_size=int(q.get("asksize") or 0),
            volume=int(float(q.get("volume") or 0)),  # volumen operado en el dia
        )

    def _parse_order(self, o: dict) -> Order:
        try:
            side = Side(o["side"])
        except ValueError:
            side = Side.BUY
        try:
            otype = OrderType(o.get("type", "limit"))
        except ValueError:
            otype = OrderType.LIMIT
        try:
            duration = Duration(o.get("duration", "day"))
        except ValueError:
            duration = Duration.DAY
        status = _STATUS_MAP.get(str(o.get("status", "")).lower(), OrderStatus.PENDING)
        return Order(
            id=str(o["id"]),
            symbol=o["symbol"],
            side=side,
            quantity=int(float(o.get("quantity", 0))),
            price=float(o.get("price") or 0.0),
            type=otype,
            duration=duration,
            status=status,
            filled_quantity=int(float(o.get("exec_quantity", 0))),
            avg_fill_price=float(o.get("avg_fill_price") or 0.0),
            create_date=str(o.get("create_date") or ""),
            transaction_date=str(o.get("transaction_date") or ""),
        )

    # ---------- Ordenes (SIEMPRE sandbox durante el desarrollo) ----------
    def place_order(self, request: OrderRequest) -> Order:
        data = {
            "class": "equity",
            "symbol": request.symbol,
            "side": request.side.value,
            "quantity": str(request.quantity),
            "type": request.type.value,
            "duration": request.duration.value,
        }
        if request.type == OrderType.LIMIT:
            data["price"] = f"{request.price:.2f}"
        js = self._send("POST", f"/accounts/{self._account_id}/orders", data=data)
        node = js.get("order", {})
        # La respuesta solo confirma "recibida" (status 'ok') y trae el id.
        # El estado real (open/filled/rejected) se consulta despues.
        return Order(
            id=str(node.get("id")),
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            type=request.type,
            duration=request.duration,
            status=OrderStatus.PENDING,
        )

    def modify_order(
        self, order_id: str, *, price: float | None = None, quantity: int | None = None
    ) -> Order:
        # Tradier permite cambiar precio/type/duration, pero NO la cantidad.
        if quantity is not None:
            raise NotImplementedError(
                "Tradier no permite cambiar la cantidad de una orden viva; "
                "para eso hay que cancelar y mandar una nueva."
            )
        # Incluimos type y duration porque el endpoint de Tradier suele pedirlos.
        # Por ahora el bot solo usa ordenes limit/day; cuando sumemos horario
        # extendido, se pasara la duracion real.
        data: dict[str, str] = {"type": "limit", "duration": "day"}
        if price is not None:
            data["price"] = f"{price:.2f}"
        self._send("PUT", f"/accounts/{self._account_id}/orders/{order_id}", data=data)
        # El endpoint no devuelve la orden completa; el estado real se reconsulta.
        return Order(
            id=str(order_id),
            symbol="",
            side=Side.BUY,
            quantity=0,
            price=price or 0.0,
            status=OrderStatus.PENDING,
        )

    def cancel_order(self, order_id: str) -> None:
        self._send("DELETE", f"/accounts/{self._account_id}/orders/{order_id}")

    # ---------- Streaming: se implementa en la Fase 4 ----------
    def subscribe_quotes(
        self, symbols: list[str], on_quote: Callable[[Quote], None]
    ) -> None:
        raise NotImplementedError("El streaming de precios se implementa en la Fase 4.")

    def subscribe_account(self, on_fill: Callable[[Fill], None]) -> None:
        raise NotImplementedError("El streaming de cuenta se implementa en la Fase 4.")
