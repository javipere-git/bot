"""
Configuracion del bot (el 'que' y 'como' que decide el usuario).

Cubre la ENTRADA (Tanda 1) y la SALIDA + guardia (Tanda 2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .models import Duration, Side


class OffsetUnit(str, Enum):
    """En que unidad se expresa el corrimiento (offset) de una orden."""
    PERCENT_SPREAD = "percent_spread"  # % del spread (ej. 10% de 0.20 = 0.02)
    DOLLARS = "dollars"                # monto fijo en $ (ej. 0.02)


@dataclass
class OrderConfig:
    """Configuracion de una orden de entrada (Orden 1 u Orden 2)."""
    offset: float            # cuanto se corre respecto del bid/ask
    unit: OffsetUnit         # en % del spread o en $
    timeout_s: float         # cuantos segundos esperar el llenado


@dataclass
class ExitLevel:
    """Un nivel del cierre escalonado (hasta 4)."""
    offset: float
    unit: OffsetUnit
    timeout_s: float
    enabled: bool = True
    cross: bool = False      # "cruzar": ignora el offset y cruza el spread


class GuardUnit(str, Enum):
    """En que unidad se mide el umbral del guardia."""
    DOLLARS = "dollars"      # centavos / $ absolutos
    PERCENT = "percent"      # % del precio de referencia (bid/ask de entrada)


class GuardAction(str, Enum):
    """Que hace el bot cuando el guardia se dispara."""
    MANUAL = "manual"          # (A) frena la salida y pasa a manual
    FORCE_EXIT = "force_exit"  # (B) cruza el spread y sale al instante
    CONTINUE = "continue"      # (C) sigue con el escalonado normal


class GuardReference(str, Enum):
    """Desde que precio mide el guardia el movimiento en contra."""
    ENTRY_CALC = "entry_calc"  # bid/ask usado para CALCULAR la orden de entrada
    EXIT_START = "exit_start"  # bid/ask leido al ARRANCAR el cierre (comport. anterior)


@dataclass
class GuardConfig:
    """Freno de seguridad por movimiento en contra."""
    threshold: float                       # umbral del movimiento en contra
    unit: GuardUnit = GuardUnit.DOLLARS
    action: GuardAction = GuardAction.MANUAL
    enabled: bool = True
    reference: GuardReference = GuardReference.ENTRY_CALC


@dataclass
class EngineConfig:
    """Todo lo que el bot necesita."""
    side: Side                          # BUY (entra largo) o SELL_SHORT (entra corto)
    quantity: int                       # cantidad fija de acciones por orden
    order1: OrderConfig
    order2: OrderConfig | None = None
    spread_min: float | None = None     # filtro de spread en $ (None = sin limite)
    spread_max: float | None = None
    # Filtro de SPREAD CONTRA EL PRECIO: que tan ancho es el spread comparado con lo
    # que vale la accion. Ej. 5 => si el spread es 5% o MAS del precio, saltea (spread
    # 0.50 en una accion de 10.00 = 5%). Sirve para dejar afuera las iliquidas, donde
    # el spread se come la ganancia. Se mide con la cotizacion del momento (no necesita
    # streaming). El precio de referencia es el PUNTO MEDIO entre bid y ask.
    # None = filtro apagado.
    max_spread_pct_precio: float | None = None
    # Filtro de MOVIMIENTO: cuantas veces se movio el precio en los ultimos segundos.
    # Si se paso del tope, el bot saltea el simbolo (accion demasiado nerviosa).
    # El bid y el ask van por separado, cada uno con su ventana; None = ese lado no
    # filtra nada (se pueden usar los dos, uno solo, o ninguno).
    max_cambios_bid: int | None = None
    ventana_bid_s: float = 30.0
    max_cambios_ask: int | None = None
    ventana_ask_s: float = 30.0
    # Filtro de SPREAD MAXIMO: el spread mas ancho de los ultimos X segundos no debe
    # superar este % del spread ACTUAL (el que se usa para calcular la orden).
    # Ej. 150 => si el spread llego a estar 2x mas ancho que el de ahora, saltea.
    # None = filtro apagado.
    max_spread_pct: float | None = None
    ventana_spread_s: float = 30.0
    # Filtro de VOLUMEN RECIENTE: acciones operadas en los ultimos X segundos. Si se
    # paso del tope, saltea (demasiada actividad). Es un MAXIMO a proposito: el feed
    # de Tradier viene muestreado y cuenta de menos, y con un maximo eso solo hace
    # que filtre de MENOS (nunca saltea de mas). None = apagado.
    max_volumen_seg: int | None = None
    ventana_volumen_s: float = 30.0
    volume_min: int | None = None       # filtro de volumen operado en el dia, en
    volume_max: int | None = None       # acciones (None = sin limite por ese lado)
    duration: Duration = Duration.DAY   # por defecto DAY
    extended_hours: bool = False        # operar tambien fuera de la rueda regular
    reprice_mode: str = "modify"        # "modify" (recomendado) o "cancel_new"
    poll_interval_s: float = 0.5        # cada cuanto consulta estado / cotizacion
    # PAUSA ANTES DE ENTRAR A UN SIMBOLO NUEVO (0 = apagada, se comporta como siempre).
    #
    # Para que existe: hay brokers que NO liberan al instante el poder de compra de
    # una orden que se acaba de cancelar. Medido en Tastytrade el 14/08/2026: tres
    # segundos despues de cancelar una orden de $4.541, rechazaron una de $670
    # teniendo $7.334 disponibles. Con una pausa, el broker alcanza a devolver la
    # plata antes de que salga la orden siguiente.
    #
    # DONDE cae la pausa, y por que ahi: DESPUES de que el simbolo paso todos los
    # filtros y ANTES de leer el bid/ask con el que se calcula la orden. Asi no se
    # pierde tiempo en simbolos que igual iban a saltearse, y el precio con el que
    # se entra es fresco (se relee la cotizacion despues de esperar).
    pausa_simbolo_s: float = 0.0

    # ----- salida (Tanda 2) -----
    exit_levels: list[ExitLevel] = field(default_factory=list)  # hasta 4
    wait_before_exit_s: float = 0.0     # espera entre el llenado y el inicio del cierre
    guard: GuardConfig | None = None    # freno de seguridad (None = sin guardia)
    # Los escalones NORMALES no salen a peor precio que el promedio de la posicion
    # (no vender por debajo si largo / no comprar por encima si corto). Para salir
    # con perdida esta "cruzar", que NO se topa. (Default False = comportamiento
    # historico; la pantalla lo enciende por defecto.)
    no_cerrar_bajo_promedio: bool = False

    # ----- flujo del recorrido de la watchlist -----
    pause_on_fill: bool = True          # tras CERRAR una posicion, pausar (reanudable)
    loop_watchlist: bool = True         # True: recorre en loop; False: una pasada y termina

    # ----- robustez (Fase 6) -----
    max_strikes: int = 3                # rechazos/fallos de orden SEGUIDOS antes de frenar
