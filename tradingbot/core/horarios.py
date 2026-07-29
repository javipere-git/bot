"""
Horarios del mercado (en hora del Este, con horario de verano automatico).

Sesiones de acciones de EEUU:
  - pre-market      04:00 - 09:30 ET
  - regular         09:30 - 16:00 ET
  - post-market     16:00 - 20:00 ET
  - OVERNIGHT       20:00 - 04:00 ET  (Blue Ocean ATS, domingo a jueves)

La sesion overnight es la unica que NO viaja por el feed consolidado (SIP): tiene
su propio feed. Por eso hace falta saber en que sesion estamos.
"""
from __future__ import annotations

from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001  (sin tzdata instalado)
    _ET = None


def ahora_et() -> datetime | None:
    """Hora actual del Este, o None si no se puede calcular."""
    if _ET is None:
        return None
    try:
        return datetime.now(_ET)
    except Exception:  # noqa: BLE001
        return None


def es_sesion_overnight(momento: datetime | None = None) -> bool:
    """True si estamos en la sesion overnight de Blue Ocean (20:00 - 04:00 ET,
    de domingo a jueves por la noche).

    Si no se puede saber la hora del Este, devuelve False: se sigue usando el feed
    normal, que es el comportamiento de siempre (nunca peor que antes)."""
    t = momento or ahora_et()
    if t is None:
        return False
    dia = t.weekday()          # lunes=0 ... domingo=6
    if t.hour >= 20:           # la sesion arranca esta noche
        return dia in (6, 0, 1, 2, 3)      # domingo a jueves
    if t.hour < 4:             # la sesion arranco anoche
        return dia in (0, 1, 2, 3, 4)      # lunes a viernes de madrugada
    return False


def nombre_sesion(momento: datetime | None = None) -> str:
    """Nombre de la sesion actual, para mostrar en pantalla."""
    t = momento or ahora_et()
    if t is None:
        return ""
    if es_sesion_overnight(t):
        return "overnight"
    minutos = t.hour * 60 + t.minute
    if t.weekday() >= 5:
        return "fin de semana"
    if 240 <= minutos < 570:
        return "pre-market"
    if 570 <= minutos < 960:
        return "regular"
    if 960 <= minutos < 1200:
        return "post-market"
    return "cerrado"
