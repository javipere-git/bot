"""
Perfiles de broker: cada combinacion (broker + cuenta) que se puede elegir al
abrir la app. Aca vive TODO lo que cambia de un broker a otro, para que el resto
de la pantalla no tenga que saber con cual esta hablando.

Agregar un broker nuevo = agregar un perfil aca (y su conector). Nada mas.
"""
from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from typing import Callable

from ..connectors.alpaca import AlpacaBroker
from ..connectors.alpaca_stream import AlpacaMarketStream
from ..connectors.alpaca_trade_stream import AlpacaTradeStream
from ..connectors.tradier_account_stream import TradierAccountStream
from ..connectors.hibrido import BrokerHibrido
from ..connectors.tradier import TradierBroker
from ..connectors.tastytrade import TastytradeBroker
from ..connectors.tastytrade_stream import TastytradeMarketStream
from ..connectors.tastytrade_account_stream import TastytradeAccountStream


@dataclass
class Perfil:
    id: str                          # identificador corto (para el log, etc.)
    broker_nombre: str               # "Tradier" / "Alpaca" / "Tastytrade"
    cuenta_texto: str                # "PAPER (simulado)" / "LIVE - DINERO REAL"
    es_live: bool                    # True = dinero real (banner verde, doble confirmacion)
    _crear_broker: Callable[[], object]
    _crear_stream: Callable[[], object] | None = None
    _crear_avisos: Callable[[], object] | None = None
    # De donde salen los PRECIOS. Vacio = del mismo broker donde se opera. La pantalla
    # de inicio arma con esto el desplegable de "datos de mercado" (ver startup.py).
    datos_nombre: str = ""
    # Etiqueta corta de la cuenta para los desplegables: PAPER / LIVE / SANDBOX.
    modo_texto: str = ""

    @property
    def datos(self) -> str:
        return self.datos_nombre or self.broker_nombre

    @property
    def modo(self) -> str:
        return self.modo_texto or ("LIVE" if self.es_live else "PAPER")

    def crear_broker(self):
        return self._crear_broker()

    def crear_avisos(self):
        """Canal de AVISOS DE CUENTA (orden puesta/ejecutada/cancelada) para que la
        pantalla se refresque al instante. None si el broker no lo ofrece."""
        return self._crear_avisos() if self._crear_avisos else None

    def crear_stream(self):
        """Devuelve el StreamWorker de precios en vivo, o None si este broker
        todavia no tiene streaming cableado (el ladder cae a lectura por REST)."""
        return self._crear_stream() if self._crear_stream else None


def _ruta_credenciales() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "config", "credentials.ini")


def _leer_cfg() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read(_ruta_credenciales())
    return cfg


def _tradier_live_disponible(cfg: configparser.ConfigParser) -> bool:
    if not cfg.has_section("tradier"):
        return False
    token = cfg["tradier"].get("production_token", "").strip()
    acct = cfg["tradier"].get("production_account_id", "").strip()
    return bool(token) and not token.startswith("PEGA_") and bool(acct)


def _alpaca_disponible(cfg: configparser.ConfigParser) -> bool:
    if not cfg.has_section("alpaca"):
        return False
    return bool(cfg["alpaca"].get("paper_key_id", "").strip()) and bool(
        cfg["alpaca"].get("paper_secret", "").strip()
    )


def _alpaca_live_disponible(cfg: configparser.ConfigParser) -> bool:
    """True solo si el usuario cargo las claves de su cuenta REAL de Alpaca."""
    if not cfg.has_section("alpaca"):
        return False
    return bool(cfg["alpaca"].get("live_key_id", "").strip()) and bool(
        cfg["alpaca"].get("live_secret", "").strip()
    )


def _tasty_disponible(cfg: configparser.ConfigParser, entorno: str) -> bool:
    """Tastytrade necesita el client secret y el refresh token del grant personal."""
    if not cfg.has_section("tastytrade"):
        return False
    pre = "sandbox" if entorno == "sandbox" else "production"
    s = cfg["tastytrade"]
    return bool(s.get(f"{pre}_client_secret", "").strip()) and bool(
        s.get(f"{pre}_refresh_token", "").strip()
    )


def perfiles_disponibles() -> list[Perfil]:
    """Lista los perfiles que se pueden usar segun lo cargado en credentials.ini.
    El streaming de precios (Tradier) usa el token de produccion, asi que solo se
    ofrece si ese token esta cargado; si no, el ladder usa lectura por REST."""
    from .stream_worker import StreamWorker  # import tardio (evita ciclo)
    from .account_worker import AccountWorker

    def avisos_tradier():
        return AccountWorker(
            TradierAccountStream.from_credentials(environment="production"), "tradier")

    def avisos_tasty(entorno):
        def crear():
            return AccountWorker(
                TastytradeAccountStream.from_credentials(environment=entorno),
                "tastytrade")
        return crear

    def avisos_alpaca(entorno):
        def crear():
            return AccountWorker(
                AlpacaTradeStream.from_credentials(environment=entorno), "alpaca")
        return crear

    cfg = _leer_cfg()
    perfiles: list[Perfil] = []

    hay_stream_tradier = bool(cfg.has_section("tradier")
                              and cfg["tradier"].get("production_token", "").strip())
    stream_factory = (StreamWorker.from_credentials if hay_stream_tradier else None)

    # Tradier PAPER (sandbox) -- siempre, es el modo por defecto
    if cfg.has_section("tradier") and cfg["tradier"].get("sandbox_token", "").strip():
        perfiles.append(Perfil(
            id="tradier_paper",
            datos_nombre="Tradier",
            modo_texto="PAPER",
            broker_nombre="Tradier",
            cuenta_texto="PAPER (simulado)   -   SIN DINERO REAL",
            es_live=False,
            _crear_broker=lambda: TradierBroker.from_credentials(environment="sandbox"),
            _crear_stream=stream_factory,
        ))

    # Tradier LIVE (real) -- solo si cargo token + numero de cuenta de produccion
    if _tradier_live_disponible(cfg):
        perfiles.append(Perfil(
            id="tradier_live",
            datos_nombre="Tradier",
            modo_texto="LIVE",
            broker_nombre="Tradier",
            cuenta_texto="LIVE   -   DINERO REAL",
            es_live=True,
            _crear_broker=lambda: TradierBroker.from_credentials(environment="production"),
            _crear_stream=stream_factory,
            _crear_avisos=avisos_tradier,
        ))

    # Alpaca PAPER -- solo si cargo las claves paper. Streaming propio de Alpaca
    # (feed segun data_feed: iex gratis / sip con el plan Algo Trader Plus).
    if _alpaca_disponible(cfg):
        perfiles.append(Perfil(
            id="alpaca_paper",
            datos_nombre="Alpaca",
            modo_texto="PAPER",
            broker_nombre="Alpaca",
            cuenta_texto="PAPER (simulado)   -   SIN DINERO REAL",
            es_live=False,
            _crear_broker=lambda: AlpacaBroker.from_credentials(environment="paper"),
            _crear_stream=lambda: StreamWorker(
                AlpacaMarketStream.from_credentials(environment="paper")
            ),
            _crear_avisos=avisos_alpaca("paper"),
        ))

    # Alpaca PAPER con DATOS de Tradier (NBBO real) -- si estan las dos cosas.
    # Opera en Alpaca pero los precios salen de Tradier (produccion, en vivo);
    # evita el feed IEX de Alpaca, que no da el NBBO consolidado.
    hay_datos_tradier = bool(cfg.has_section("tradier")
                             and cfg["tradier"].get("production_token", "").strip())
    if _alpaca_disponible(cfg) and hay_datos_tradier:
        perfiles.append(Perfil(
            id="alpaca_paper_datos_tradier",
            datos_nombre="Tradier",
            modo_texto="PAPER",
            broker_nombre="Alpaca",
            cuenta_texto="PAPER (simulado)   -   datos de Tradier (NBBO real)",
            es_live=False,
            _crear_broker=lambda: BrokerHibrido(
                operativa=AlpacaBroker.from_credentials(environment="paper"),
                datos=TradierBroker.from_credentials(environment="production"),
            ),
            _crear_stream=stream_factory,   # streaming de precios de Tradier
            _crear_avisos=avisos_alpaca("paper"),   # avisos de la cuenta de Alpaca
        ))

    # Alpaca LIVE (DINERO REAL) -- solo si cargo las claves de la cuenta real.
    # Hereda TODAS las salvaguardas de live (tope de tamano, doble confirmacion,
    # escribir REAL) por tener es_live=True. Se ofrece la variante con datos de
    # Tradier (recomendada, NBBO real) y la de datos propios (IEX).
    if _alpaca_live_disponible(cfg):
        if hay_datos_tradier:
            perfiles.append(Perfil(
                id="alpaca_live_datos_tradier",
                datos_nombre="Tradier",
                modo_texto="LIVE",
                broker_nombre="Alpaca",
                cuenta_texto="LIVE - DINERO REAL   -   datos de Tradier (NBBO real)",
                es_live=True,
                _crear_broker=lambda: BrokerHibrido(
                    operativa=AlpacaBroker.from_credentials(environment="live"),
                    datos=TradierBroker.from_credentials(environment="production"),
                ),
                _crear_stream=stream_factory,
                _crear_avisos=avisos_alpaca("live"),
            ))
        perfiles.append(Perfil(
            id="alpaca_live",
            datos_nombre="Alpaca",
            modo_texto="LIVE",
            broker_nombre="Alpaca",
            cuenta_texto="LIVE - DINERO REAL   -   datos propios de Alpaca",
            es_live=True,
            _crear_broker=lambda: AlpacaBroker.from_credentials(environment="live"),
            _crear_stream=lambda: StreamWorker(
                AlpacaMarketStream.from_credentials(environment="live")
            ),
            _crear_avisos=avisos_alpaca("live"),
        ))

    # ---- Tastytrade ----
    # SANDBOX: Tasty NO da cotizaciones por REST fuera de produccion (devuelve 502),
    # asi que el perfil util es el HIBRIDO: opera en Tasty y los precios salen de
    # Tradier (produccion, en vivo). El de datos propios se ofrece igual, por si se
    # quiere usar solo para mandar ordenes.
    if _tasty_disponible(cfg, "sandbox"):
        if hay_datos_tradier:
            perfiles.append(Perfil(
                id="tasty_sandbox_datos_tradier",
                _crear_avisos=avisos_tasty("sandbox"),
                datos_nombre="Tradier",
                modo_texto="SANDBOX",
                broker_nombre="Tastytrade",
                cuenta_texto="SANDBOX (simulado)   -   datos de Tradier (NBBO real)",
                es_live=False,
                _crear_broker=lambda: BrokerHibrido(
                    operativa=TastytradeBroker.from_credentials(environment="sandbox"),
                    datos=TradierBroker.from_credentials(environment="production"),
                ),
                _crear_stream=stream_factory,   # streaming de precios de Tradier
            ))
        perfiles.append(Perfil(
            id="tasty_sandbox",
            _crear_avisos=avisos_tasty("sandbox"),
            datos_nombre="(sin precios)",
            modo_texto="SANDBOX",
            broker_nombre="Tastytrade",
            cuenta_texto="SANDBOX (simulado)   -   SIN precios (solo ordenes)",
            es_live=False,
            _crear_broker=lambda: TastytradeBroker.from_credentials(environment="sandbox"),
        ))

    # LIVE (DINERO REAL): en produccion Tasty SI tiene cotizaciones por REST
    # (cuentas con fondos), asi que puede andar solo. Igual se ofrece la variante
    # con datos de Tradier. Hereda todas las salvaguardas de live por es_live=True.
    if _tasty_disponible(cfg, "production"):
        if hay_datos_tradier:
            perfiles.append(Perfil(
                id="tasty_live_datos_tradier",
                _crear_avisos=avisos_tasty("production"),
                datos_nombre="Tradier",
                modo_texto="LIVE",
                broker_nombre="Tastytrade",
                cuenta_texto="LIVE - DINERO REAL   -   datos de Tradier (NBBO real)",
                es_live=True,
                _crear_broker=lambda: BrokerHibrido(
                    operativa=TastytradeBroker.from_credentials(environment="production"),
                    datos=TradierBroker.from_credentials(environment="production"),
                ),
                _crear_stream=stream_factory,
            ))
        perfiles.append(Perfil(
            id="tasty_live",
            _crear_avisos=avisos_tasty("production"),
            datos_nombre="Tastytrade",
            modo_texto="LIVE",
            broker_nombre="Tastytrade",
            cuenta_texto="LIVE - DINERO REAL   -   datos propios de Tastytrade",
            es_live=True,
            _crear_broker=lambda: TastytradeBroker.from_credentials(environment="production"),
            # Streaming propio por DXLink: precios en vivo para el ladder y el Time &
            # Sales, y datos para los filtros de movimiento del bot (sin streaming
            # esos filtros no tienen que medir y dejarian pasar todo).
            # OJO, dato medido: este feed trae ODD LOTS (tamanos que no son multiplos
            # del lote redondo); el REST de Tasty y el de Tradier, no.
            _crear_stream=lambda: StreamWorker(
                TastytradeMarketStream.from_credentials(environment="production")
            ),
        ))

    return perfiles


def perfil_por_defecto() -> Perfil:
    """Un perfil Tradier-paper para pruebas (smoke) sin pasar por el dialogo."""
    return Perfil(
        id="tradier_paper",
        broker_nombre="Tradier",
        cuenta_texto="PAPER (simulado)   -   SIN DINERO REAL",
        es_live=False,
        _crear_broker=lambda: TradierBroker.from_credentials(environment="sandbox"),
        _crear_stream=None,
    )
