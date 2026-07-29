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


@dataclass
class Perfil:
    id: str                          # identificador corto (para el log, etc.)
    broker_nombre: str               # "Tradier" / "Alpaca"
    cuenta_texto: str                # "PAPER (simulado)" / "LIVE - DINERO REAL"
    es_live: bool                    # True = dinero real (banner verde, doble confirmacion)
    _crear_broker: Callable[[], object]
    _crear_stream: Callable[[], object] | None = None
    _crear_avisos: Callable[[], object] | None = None

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


def perfiles_disponibles() -> list[Perfil]:
    """Lista los perfiles que se pueden usar segun lo cargado en credentials.ini.
    El streaming de precios (Tradier) usa el token de produccion, asi que solo se
    ofrece si ese token esta cargado; si no, el ladder usa lectura por REST."""
    from .stream_worker import StreamWorker  # import tardio (evita ciclo)
    from .account_worker import AccountWorker

    def avisos_tradier():
        return AccountWorker(
            TradierAccountStream.from_credentials(environment="production"), "tradier")

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
            broker_nombre="Alpaca",
            cuenta_texto="LIVE - DINERO REAL   -   datos propios de Alpaca",
            es_live=True,
            _crear_broker=lambda: AlpacaBroker.from_credentials(environment="live"),
            _crear_stream=lambda: StreamWorker(
                AlpacaMarketStream.from_credentials(environment="live")
            ),
            _crear_avisos=avisos_alpaca("live"),
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
