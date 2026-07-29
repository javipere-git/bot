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
    volume_min: int | None = None       # filtro de volumen operado en el dia, en
    volume_max: int | None = None       # acciones (None = sin limite por ese lado)
    duration: Duration = Duration.DAY   # por defecto DAY
    extended_hours: bool = False        # operar tambien fuera de la rueda regular
    reprice_mode: str = "modify"        # "modify" (recomendado) o "cancel_new"
    poll_interval_s: float = 0.5        # cada cuanto consulta estado / cotizacion

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
