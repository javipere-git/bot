"""
Conector de TASTYTRADE contra nuestra interfaz comun (core/broker.py).

Se conecta con OAuth2 usando el "grant personal": con el CLIENT SECRET y el
REFRESH TOKEN que da la web, saca solo los tokens de acceso (duran 15 minutos y
se renuevan sin que hagas nada). No hace falta ningun navegador.

Verificado en vivo contra el SANDBOX el 07/08/2026 (cuenta 5WN45295).

DIFERENCIAS con los otros brokers, importantes de tener presentes:

  - MOVER una orden la REEMPLAZA POR UNA NUEVA, con OTRO id (igual que Alpaca,
    distinto de Tradier, que conserva el id). Comprobado: la 1288615 paso a ser
    la 1288616 y la vieja quedo 'Cancelled'. El motor ya lo cubre: mira el id que
    devuelve el modify y sigue ESE (ver _orden_vigente en core/engine.py).

  - SI distingue venta de venta en corto: tiene acciones separadas
    'Sell to Close' (cerrar largo) y 'Sell to Open' (abrir corto). O sea que el
    propio broker rechaza una venta de mas -> no necesita la red de seguridad
    que la app pone para Alpaca (distingue_venta_en_corto() = True).

  - HORARIO EXTENDIDO: se pide con time-in-force 'Ext' en vez de 'Day'. Tasty
    solo lo acepta entre las 6:00 y las 19:00 hora Central; fuera de esa franja
    devuelve 422 'tif_no_after_hours_orders'.

  - COTIZACIONES: el endpoint REST /market-data/by-type existe SOLO en produccion
    y para cuentas CON FONDOS ("we do not provide REST endpoints for delayed
    quotes"). En el sandbox devuelve 502. Por eso, en sandbox, get_quote avisa
    con un mensaje claro en vez de fallar de forma rara: ahi conviene el perfil
    hibrido (ordenes por Tasty, precios por Tradier/Alpaca).

Todo pedido lleva un User-Agent obligatorio: sin el, Tasty rechaza la llamada.
"""
from __future__ import annotations

import threading
import time
from datetime import timedelta
from typing import Callable

import requests

from ..core.broker import Broker
from ..core.horarios import ahora_et, inicio_dia_operativo
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

BASE_SANDBOX = "https://api.cert.tastyworks.com"
BASE_PRODUCCION = "https://api.tastyworks.com"
USER_AGENT = "bot-trading/1.0"     # obligatorio y de formato <producto>/<version>

# Nuestro lado -> la accion que entiende Tasty.
_ACCION = {
    Side.BUY: "Buy to Open",
    Side.SELL: "Sell to Close",
    Side.SELL_SHORT: "Sell to Open",
    Side.BUY_TO_COVER: "Buy to Close",
}
_LADO = {v: k for k, v in _ACCION.items()}

# En una compra sale plata (Debit); en una venta entra (Credit).
_EFECTO = {
    Side.BUY: "Debit",
    Side.BUY_TO_COVER: "Debit",
    Side.SELL: "Credit",
    Side.SELL_SHORT: "Credit",
}

# Estados de Tasty -> los nuestros.
_ESTADO = {
    "Received": OrderStatus.OPEN,
    "Routed": OrderStatus.OPEN,
    "In Flight": OrderStatus.OPEN,
    "Live": OrderStatus.OPEN,
    "Cancel Requested": OrderStatus.OPEN,
    "Replace Requested": OrderStatus.OPEN,
    "Contingent": OrderStatus.OPEN,
    "Filled": OrderStatus.FILLED,
    "Cancelled": OrderStatus.CANCELED,
    "Canceled": OrderStatus.CANCELED,
    "Expired": OrderStatus.CANCELED,
    "Rejected": OrderStatus.REJECTED,
    "Removed": OrderStatus.CANCELED,
}


def _fecha(valor) -> str:
    """Normaliza una fecha de Tasty a ISO, que es lo que espera la pantalla.

    Tasty mezcla dos formatos: 'received-at' viene en ISO
    ('2026-08-10T19:40:05.176+00:00') pero 'updated-at' viene como MILISEGUNDOS
    (1786390805386). Sin convertirlo, la pantalla no podia leerlo y mostraba los
    primeros digitos crudos ('17866414' en la tabla de ordenes).
    """
    if valor in (None, "", "None"):
        return ""
    texto = str(valor)
    if texto.isdigit():                     # milisegundos desde 1970
        try:
            from datetime import datetime, timezone
            return datetime.fromtimestamp(int(texto) / 1000, timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            return ""
    return texto


def _f(valor, por_defecto: float = 0.0) -> float:
    """Tasty manda los numeros como TEXTO ('100.5'); a veces vienen vacios o 'None'."""
    try:
        if valor is None or valor == "" or valor == "None":
            return por_defecto
        return float(valor)
    except (TypeError, ValueError):
        return por_defecto


class _SesionPorHilo:
    """Una sesion HTTP POR HILO.

    Compartir una requests.Session entre hilos corrompe la capa SSL y puede matar
    el proceso de golpe (paso de verdad en otra app). La app usa el conector desde
    varios lados (monitoreo, ladder, bot), asi que cada hilo se lleva la suya.
    """

    def __init__(self) -> None:
        self._local = threading.local()
        self._headers: dict[str, str] = {}

    def configurar(self, headers: dict[str, str]) -> None:
        self._headers = dict(headers)

    @property
    def actual(self) -> requests.Session:
        s = getattr(self._local, "sesion", None)
        if s is None:
            s = requests.Session()
            s.headers.update(self._headers)
            self._local.sesion = s
        return s


class TastytradeBroker(Broker):
    """Conector de tastytrade. Por defecto apunta al SANDBOX."""

    MARGEN_RENOVACION = 60      # renueva el token 60 s antes de que venza

    def __init__(
        self,
        client_secret: str,
        refresh_token: str,
        account_number: str | None = None,
        sandbox: bool = True,
        client_id: str | None = None,
    ) -> None:
        self._secret = (client_secret or "").strip()
        self._refresh = (refresh_token or "").strip()
        self._client_id = (client_id or "").strip() or None
        self._sandbox = bool(sandbox)
        self._base = BASE_SANDBOX if sandbox else BASE_PRODUCCION
        self._sesion = _SesionPorHilo()
        self._sesion.configurar({"User-Agent": USER_AGENT,
                                 "Content-Type": "application/json"})
        self._token = ""
        self._token_vence = 0.0
        self._token_lock = threading.Lock()
        # referencia para medir el resultado realizado (ver get_day_pnl)
        self._ancla_realizado: float | None = None
        self._account = (account_number or "").strip()
        if not self._account:
            self._account = self._resolver_cuenta()

    @classmethod
    def from_credentials(cls, environment: str = "sandbox") -> "TastytradeBroker":
        """Arma el conector leyendo config/credentials.ini (seccion [tastytrade])."""
        import configparser
        import os
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cfg = configparser.ConfigParser()
        cfg.read(os.path.join(raiz, "config", "credentials.ini"))
        if not cfg.has_section("tastytrade"):
            raise RuntimeError("Falta la seccion [tastytrade] en config/credentials.ini")
        s = cfg["tastytrade"]
        pre = "sandbox" if environment == "sandbox" else "production"
        secret = s.get(f"{pre}_client_secret", "").strip()
        refresh = s.get(f"{pre}_refresh_token", "").strip()
        if not secret or not refresh:
            raise RuntimeError(
                f"Faltan las credenciales de Tastytrade ({pre}): completa "
                f"{pre}_client_secret y {pre}_refresh_token en config/credentials.ini"
            )
        return cls(
            client_secret=secret,
            refresh_token=refresh,
            account_number=s.get(f"{pre}_account_number", "").strip() or None,
            client_id=s.get(f"{pre}_client_id", "").strip() or None,
            sandbox=(environment == "sandbox"),
        )

    # ---------------- OAuth ----------------
    def _access_token(self) -> str:
        """Devuelve un token valido, renovandolo si esta por vencer.

        El candado evita que dos hilos pidan el token a la vez (Tasty da uno nuevo
        por pedido; sin esto se harian llamadas de mas al arrancar)."""
        with self._token_lock:
            if self._token and time.monotonic() < self._token_vence:
                return self._token
            r = requests.post(
                f"{self._base}/oauth/token",
                data={"grant_type": "refresh_token",
                      "refresh_token": self._refresh,
                      "client_secret": self._secret},
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            if r.status_code != 200:
                raise RuntimeError(
                    f"Tastytrade no dio el token de acceso (HTTP {r.status_code}). "
                    f"Revisa el client secret y el refresh token. {r.text[:200]}"
                )
            js = r.json()
            self._token = js.get("access_token", "")
            # dura 15 min; se renueva un poco antes para no quedar justo
            self._token_vence = (time.monotonic()
                                 + max(60, int(js.get("expires_in", 900)))
                                 - self.MARGEN_RENOVACION)
            return self._token

    def _pedir(self, metodo: str, ruta: str, params: dict | None = None,
               cuerpo: dict | None = None, timeout: float = 20) -> dict:
        s = self._sesion.actual
        s.headers["Authorization"] = f"Bearer {self._access_token()}"
        r = s.request(metodo, f"{self._base}{ruta}", params=params, json=cuerpo,
                      timeout=timeout)
        if r.status_code == 401:      # token vencido justo: uno nuevo y reintento
            self._token = ""
            s.headers["Authorization"] = f"Bearer {self._access_token()}"
            r = s.request(metodo, f"{self._base}{ruta}", params=params, json=cuerpo,
                          timeout=timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"Tastytrade {metodo} {ruta}: HTTP {r.status_code} "
                               f"{self._motivo(r)}")
        if not r.content:
            return {}
        try:
            return r.json()
        except ValueError:
            return {}

    @staticmethod
    def _motivo(r) -> str:
        """Saca el mensaje de error de Tasty (viene anidado en 'error')."""
        try:
            err = r.json().get("error", {})
            partes = [str(err.get("message", ""))]
            for e in (err.get("errors") or [])[:3]:
                partes.append(str(e.get("message", e)))
            return " | ".join(p for p in partes if p)[:300]
        except Exception:  # noqa: BLE001
            return r.text[:200]

    def _resolver_cuenta(self) -> str:
        """Si no dieron el numero de cuenta, lo busca solo (usa la primera abierta)."""
        js = self._pedir("GET", "/customers/me/accounts")
        for it in js.get("data", {}).get("items", []):
            cuenta = it.get("account", it)
            if not cuenta.get("is-closed"):
                return str(cuenta.get("account-number") or "")
        raise RuntimeError("Tastytrade: no encontre ninguna cuenta abierta.")

    # ---------------- Lectura ----------------
    def get_account_id(self) -> str:
        return self._account

    def get_positions(self) -> list[Position]:
        js = self._pedir("GET", f"/accounts/{self._account}/positions")
        out: list[Position] = []
        for p in js.get("data", {}).get("items", []):
            cantidad = int(_f(p.get("quantity")))
            if cantidad == 0:
                continue
            # el signo viene aparte, en 'quantity-direction' (Long / Short)
            if str(p.get("quantity-direction", "")).lower() == "short":
                cantidad = -cantidad
            out.append(Position(
                symbol=str(p.get("symbol") or ""),
                quantity=cantidad,
                avg_price=_f(p.get("average-open-price")),
            ))
        return out

    def orden_de_aviso(self, evento):
        """El aviso de Tasty viene como {'type': 'Order', 'data': {...la orden...}}.
        Trae la orden entera, asi que se aprovecha completa."""
        if not isinstance(evento, dict) or evento.get("type") != "Order":
            return (None, None, None)     # AccountBalance / CurrentPosition: no es orden
        try:
            orden = self._parse_order(evento.get("data") or {})
        except Exception:  # noqa: BLE001
            return (None, None, None)
        return (str(orden.id), orden.status, orden)

    def _parse_order(self, o: dict) -> Order:
        legs = o.get("legs") or [{}]
        leg = legs[0]
        accion = str(leg.get("action") or "")
        tif = str(o.get("time-in-force") or "Day")
        extended = "ext" in tif.lower()
        # lo ejecutado se informa por pata, en 'fills'
        llenado = 0
        suma = 0.0
        for f in (leg.get("fills") or []):
            q = _f(f.get("quantity"))
            llenado += int(q)
            suma += q * _f(f.get("fill-price"))
        return Order(
            id=str(o.get("id") or ""),
            symbol=str(leg.get("symbol") or ""),
            side=_LADO.get(accion, Side.BUY),
            quantity=int(_f(leg.get("quantity"))),
            price=_f(o.get("price")),
            type=(OrderType.LIMIT if str(o.get("order-type")) == "Limit"
                  else OrderType.MARKET),
            duration=Duration.DAY,
            status=_ESTADO.get(str(o.get("status") or ""), OrderStatus.PENDING),
            filled_quantity=llenado,
            avg_fill_price=(suma / llenado) if llenado else 0.0,
            create_date=_fecha(o.get("received-at")),
            transaction_date=_fecha(o.get("updated-at")),
            extended=extended,
        )

    # /accounts/.../orders acepta como MUCHO 200 por pagina (250 ya da HTTP 400).
    ORDENES_POR_PAGINA = 200
    MAX_PAGINAS = 25            # salvavidas: hasta 5.000 ordenes en el dia

    def _desde_hoy(self) -> str:
        """Corte para pedirle a Tasty SOLO las ordenes del dia operativo en curso.

        Tasty, como Alpaca, NO filtra por dia: devuelve el historico entero. Medido
        el 14/08/2026 en la cuenta real: sin filtro daba **1.881** ordenes (1.593 de
        ayer) y con el filtro **288**. Sin esto, las tablas se llenan de ordenes
        viejas y, como se ordenan por hora, las de ayer quedan arriba de todo.

        El corte son las 04:00 ET (ver inicio_dia_operativo): a medianoche escondria
        el overnight, que es la continuacion del dia que ya venia corriendo."""
        return inicio_dia_operativo().strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_orders(self, limit: int | None = None) -> list[Order]:
        """Ordenes del dia (vivas + cerradas), de la MAS NUEVA a la mas vieja.

        limit=N trae solo las N mas recientes (rapido: la pantalla refresca seguido).
        Sin limit recorre las paginas hasta traerlas todas.
        Nota: 'sort' va con mayuscula ('Desc'); en minuscula Tasty responde 400."""
        out: list[Order] = []
        for pagina in range(self.MAX_PAGINAS):
            faltan = (limit - len(out)) if limit else self.ORDENES_POR_PAGINA
            if limit and faltan <= 0:
                break
            js = self._pedir(
                "GET", f"/accounts/{self._account}/orders",
                params={"per-page": min(self.ORDENES_POR_PAGINA, max(1, faltan)),
                        "page-offset": pagina, "sort": "Desc",
                        "start-at": self._desde_hoy()},
                timeout=40,
            )
            items = js.get("data", {}).get("items", [])
            for o in items:
                try:
                    out.append(self._parse_order(o))
                except Exception:  # noqa: BLE001
                    continue      # una orden rara no rompe la lista entera
            if len(items) < self.ORDENES_POR_PAGINA:
                break             # ultima pagina
        return out

    def get_open_orders(self) -> list[Order]:
        js = self._pedir("GET", f"/accounts/{self._account}/orders/live")
        out: list[Order] = []
        for o in js.get("data", {}).get("items", []):
            try:
                orden = self._parse_order(o)
            except Exception:  # noqa: BLE001
                continue
            if orden.is_active:          # 'live' trae tambien canceladas: filtrar
                out.append(orden)
        return out

    def get_closed_orders(self) -> list[Order]:
        return [o for o in self.get_orders() if not o.is_active]

    def get_order(self, order_id: str) -> Order:
        js = self._pedir("GET", f"/accounts/{self._account}/orders/{order_id}")
        return self._parse_order(js.get("data", {}))

    def get_quote(self, symbol: str) -> Quote:
        """Cotizacion por REST. SOLO produccion y cuentas con fondos: Tasty no da
        precios demorados por REST, por eso en sandbox esto no existe."""
        sym = symbol.upper().strip()
        try:
            js = self._pedir("GET", "/market-data/by-type", params={"equity": sym})
        except RuntimeError as e:
            if self._sandbox:
                raise RuntimeError(
                    "Tastytrade SANDBOX no da cotizaciones por REST (solo produccion "
                    "con cuenta con fondos). Usa el perfil hibrido: ordenes por "
                    "Tastytrade y precios por Tradier o Alpaca."
                ) from e
            raise
        items = js.get("data", {}).get("items", [])
        d = next((x for x in items if str(x.get("symbol", "")).upper() == sym),
                 items[0] if items else {})
        return Quote(
            symbol=sym,
            bid=_f(d.get("bid")),
            ask=_f(d.get("ask")),
            bid_size=int(_f(d.get("bid-size"))),
            ask_size=int(_f(d.get("ask-size"))),
            volume=int(_f(d.get("volume"))),
        )

    def get_buying_power(self) -> float | None:
        js = self._pedir("GET", f"/accounts/{self._account}/balances")
        d = js.get("data", {})
        valor = d.get("equity-buying-power")
        return _f(valor) if valor is not None else None

    def get_day_pnl(self) -> DayPnL | None:
        """Resultado del DIA (realizado + lo que esta abierto).

        EL DATO BUENO es 'intraday-equities-cash-amount': cuanto se movio el
        efectivo HOY por operar acciones, con su signo en
        'intraday-equities-cash-effect' (Debit = salio plata). Ojo, ese numero
        solo no alcanza: si compraste algo y sigue ABIERTO, incluye lo que
        pagaste (medido: 3073.116 con 10 AAPL compradas). Sumandole el COSTO de
        lo abierto, esa parte se cancela y queda el resultado realizado limpio:

            realizado = movimiento_de_efectivo + costo_de_lo_abierto

        Verificado el 13/08/2026 en la cuenta real: dio +44.206, que es
        exactamente el efectivo (3544.206) menos lo depositado (3500).

        Es el resultado del DIA COMPLETO, no "desde que abriste la app": sobrevive
        a cerrar y reabrir. Y como es 'equities cash', un deposito no lo ensucia.

        Si ese campo no viniera, se cae al metodo anterior (anclar en la primera
        lectura), que sirve igual para medir el neto de una pasada del bot.
        """
        try:
            js = self._pedir("GET", f"/accounts/{self._account}/balances")
        except Exception:  # noqa: BLE001
            return None
        d = js.get("data", {})
        try:
            posiciones = self.get_positions()
        except Exception:  # noqa: BLE001
            posiciones = []
        costo_abierto = sum(p.avg_price * p.quantity for p in posiciones)

        realizado = None
        if (d.get("intraday-equities-cash-amount") is not None
                and self._es_de_hoy(d.get("intraday-equities-cash-effective-date"))):
            monto = _f(d.get("intraday-equities-cash-amount"))
            if str(d.get("intraday-equities-cash-effect", "")).lower() == "debit":
                monto = -monto
            realizado = monto + costo_abierto
        elif d.get("intraday-equities-cash-amount") is not None:
            # El campo trae el de la sesion ANTERIOR: Tasty no lo pone en cero al
            # empezar el dia, lo actualiza recien con el primer movimiento. Si no se
            # mira su fecha, a la mañana se muestra el resultado de AYER como si
            # fuera el de hoy (pasa hasta que operas, y ahi "se acomoda" solo).
            # Sin actividad todavia, el realizado del dia es cero.
            realizado = 0.0

        if realizado is None:                      # respaldo: el metodo viejo
            equivalente = _f(d.get("cash-balance")) + costo_abierto
            if self._ancla_realizado is None:
                self._ancla_realizado = equivalente
            realizado = equivalente - self._ancla_realizado

        return DayPnL(realizado=round(realizado, 4),
                      no_realizado=round(self._no_realizado(posiciones), 4))

    @staticmethod
    def _es_de_hoy(fecha) -> bool:
        """La fecha efectiva del campo (AAAA-MM-DD) es la del dia operativo en curso?

        Se compara contra la fecha en NUEVA YORK, no la de la PC: a la madrugada
        argentina (que en NY todavia es el dia anterior) la fecha local ya cambio y
        el campo quedaria mal descartado.

        Sin zona horaria disponible se responde True: en el peor caso se muestra un
        numero de mas, que es preferible a esconder el resultado del dia."""
        if not fecha:
            return False
        t = ahora_et()
        if t is None:
            return True
        # el dia operativo arranca a las 04:00 ET: antes de esa hora seguimos en el
        # dia anterior (la sesion overnight es continuacion del que venia corriendo)
        hoy = (t if t.hour >= 4 else t - timedelta(days=1)).strftime("%Y-%m-%d")
        return str(fecha)[:10] == hoy

    def _no_realizado(self, posiciones) -> float:
        """Lo que ganan/pierden las posiciones ABIERTAS al precio de ahora.
        Cuesta una cotizacion por posicion; el bot trabaja de a una, asi que en la
        practica es una sola. Si algo falla, devuelve 0 y no rompe el resultado."""
        total = 0.0
        for p in posiciones[:5]:                   # tope por las dudas
            try:
                q = self.get_quote(p.symbol)
                medio = (q.bid + q.ask) / 2 if (q.bid and q.ask) else (q.bid or q.ask)
                if medio:
                    total += (medio - p.avg_price) * p.quantity
            except Exception:  # noqa: BLE001
                continue
        return total

    def distingue_venta_en_corto(self) -> bool:
        """True: Tasty tiene 'Sell to Close' y 'Sell to Open' separados, asi que el
        broker mismo frena una venta de mas (no hace falta la red de la app)."""
        return True

    def puede_operar_en_corto(self) -> bool | None:
        """Para vender en corto hace falta cuenta de MARGEN."""
        try:
            js = self._pedir("GET", "/customers/me/accounts")
            for it in js.get("data", {}).get("items", []):
                cuenta = it.get("account", it)
                if str(cuenta.get("account-number")) == self._account:
                    return str(cuenta.get("margin-or-cash", "")).lower() == "margin"
        except Exception:  # noqa: BLE001
            return None
        return None

    def catalogo(self) -> list[dict]:
        """Todo lo que Tasty sabe de cada instrumento.

        'bloqueada' sale de is-closing-only: solo dejan CERRAR, no abrir.

        OJO CON EL SANDBOX (medido el 15/08/2026): lista OTRO universo, 24.802
        instrumentos en 15,9 s, y no marca NINGUNO: is-closing-only y is-fraud-risk
        vienen en false para los 24.802. Produccion, en cambio, lista 13.194 en
        7,5 s con 394 bloqueadas, 6.004 iliquidas y 3.539 con marca de fraude.
        Como las bloqueadas de verdad solo estan en produccion, estando en sandbox
        se piden ahi directamente (y de paso tarda la mitad).

        Las marcas 'iliquida' (45%) y 'marca_fraude' (27%) se informan pero NO
        bloquean nada: filtrar por ahi vaciaria cualquier watchlist. Quedan para
        mirarlas en el catalogo."""
        self.catalogo_origen = None
        if self._sandbox:
            # Se pide derecho a PRODUCCION: es el unico lado donde estan marcadas.
            # Es una lectura del listado de instrumentos: no toca la cuenta, no mira
            # posiciones y no manda ordenes. Y ademas es MAS RAPIDO (7,5 s contra
            # 15,9 s del sandbox, que lista el doble de instrumentos inventados).
            try:
                prod = TastytradeBroker.from_credentials(environment="production")
                reales = prod._catalogo_crudo()
            except Exception:       # noqa: BLE001  sin credenciales de produccion
                reales = []
            if reales:
                self.catalogo_origen = (
                    "el sandbox no marca ninguna bloqueada, asi que la lista sale "
                    "del catalogo de PRODUCCION (solo lectura, no toca la cuenta)")
                return reales
        return self._catalogo_crudo()

    def _catalogo_crudo(self) -> list[dict]:
        """Las paginas tal como las manda el entorno al que esta conectado."""
        filas = []
        for pagina in range(0, 30):
            js = self._pedir("GET", "/instruments/equities/active",
                             params={"per-page": 1000, "page-offset": pagina},
                             timeout=60)
            items = js.get("data", {}).get("items", [])
            if not items:
                break
            for i in items:
                filas.append({
                    "symbol": str(i.get("symbol", "")).upper(),
                    "bloqueada": bool(i.get("is-closing-only")),
                    "operable": bool(i.get("active", True)),
                    "prestable": str(i.get("lendability") or "") == "Easy To Borrow",
                    "costo_prestamo": i.get("borrow-rate"),
                    "iliquida": bool(i.get("is-illiquid")),
                    "marca_fraude": bool(i.get("is-fraud-risk")),
                    "overnight_bloqueada": not i.get("overnight-trading-permitted", True),
                    "mercado": str(i.get("listed-market") or ""),
                })
        return filas

    def lista_etb(self) -> list[str]:
        """Acciones EASY TO BORROW segun Tasty (campo 'lendability' del instrumento).

        La lista completa son ~25.000 instrumentos paginados, asi que se recorre de a
        1000 con un tope de seguridad."""
        etb: list[str] = []
        for pagina in range(0, 30):          # 30 x 1000 = 30.000, de sobra
            js = self._pedir("GET", "/instruments/equities/active",
                             params={"per-page": 1000, "page-offset": pagina},
                             timeout=60)
            items = js.get("data", {}).get("items", [])
            if not items:
                break
            for it in items:
                if str(it.get("lendability", "")).lower() == "easy to borrow":
                    sym = str(it.get("symbol") or "").strip()
                    if sym:
                        etb.append(sym)
            if len(items) < 1000:
                break
        return sorted(set(etb))

    # ---------------- Ordenes ----------------
    def _cuerpo_orden(self, symbol: str, side: Side, quantity: int, price: float,
                      tipo: OrderType, extended: bool) -> dict:
        cuerpo = {
            # DAY salvo que se pida horario extendido, que en Tasty es 'Ext'
            "time-in-force": "Ext" if extended else "Day",
            "order-type": "Limit" if tipo == OrderType.LIMIT else "Market",
            "legs": [{
                "instrument-type": "Equity",
                "symbol": symbol.upper().strip(),
                "quantity": int(quantity),
                "action": _ACCION[side],
            }],
        }
        if tipo == OrderType.LIMIT:
            cuerpo["price"] = f"{price:.2f}"
            cuerpo["price-effect"] = _EFECTO[side]
        return cuerpo

    def place_order(self, request: OrderRequest) -> Order:
        cuerpo = self._cuerpo_orden(request.symbol, request.side, request.quantity,
                                    request.price, request.type, request.extended)
        js = self._pedir("POST", f"/accounts/{self._account}/orders", cuerpo=cuerpo)
        node = js.get("data", {}).get("order", {})
        if node:
            return self._parse_order(node)
        return Order(id="", symbol=request.symbol, side=request.side,
                     quantity=request.quantity, price=request.price,
                     type=request.type, status=OrderStatus.PENDING,
                     extended=request.extended)

    def modify_order(self, order_id: str, *, price: float | None = None,
                     quantity: int | None = None, duration=None) -> Order:
        """OJO: Tasty REEMPLAZA la orden y devuelve OTRO id. El que llama tiene que
        seguir el id devuelto (el motor ya lo hace con _orden_vigente)."""
        actual = self.get_order(order_id)
        cuerpo = self._cuerpo_orden(
            actual.symbol, actual.side,
            int(quantity) if quantity is not None else actual.quantity,
            float(price) if price is not None else actual.price,
            actual.type, actual.extended,
        )
        js = self._pedir("PUT", f"/accounts/{self._account}/orders/{order_id}",
                         cuerpo=cuerpo)
        data = js.get("data", {})
        return self._parse_order(data.get("order", data))

    def cancel_order(self, order_id: str) -> None:
        self._pedir("DELETE", f"/accounts/{self._account}/orders/{order_id}")

    # ---------------- Streaming ----------------
    def subscribe_quotes(self, symbols: list[str],
                         on_quote: Callable[[Quote], None]) -> None:
        raise NotImplementedError(
            "El streaming de precios de Tastytrade (DXLink) todavia no esta hecho."
        )

    def subscribe_account(self, on_fill: Callable[[Fill], None]) -> None:
        raise NotImplementedError(
            "El streaming de cuenta de Tastytrade todavia no esta hecho."
        )
