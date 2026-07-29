"""
Prueba el soporte de la sesion OVERNIGHT (Blue Ocean ATS, 20:00-04:00 ET).

Por que existe: en esa franja el feed consolidado (SIP) no publica NADA. Los
precios y las operaciones van por un feed aparte ('boats'). La app tiene que
elegir el feed segun la hora, y cambiarlo sola cuando arranca o termina la sesion.

Parte 1: la deteccion de sesion, con horarios simulados (no toca nada).
Parte 2 (--real): contra Alpaca, muestra que feed usa AHORA y trae precios.

    python examples/demo_overnight.py
    python examples/demo_overnight.py --real
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001
    ET = None

from tradingbot.core.horarios import (  # noqa: E402
    es_sesion_overnight, inicio_dia_operativo, nombre_sesion,
)


def parte1() -> bool:
    if ET is None:
        print("(sin zona horaria instalada: se saltea la prueba)")
        return True
    print("PARTE 1: deteccion de la sesion segun la hora del Este")
    print("-" * 68)
    casos = [
        # (fecha y hora ET, es overnight?, que sesion es, por que)
        ((2026, 7, 28, 10, 30), False, "regular",      "martes al mediodia"),
        ((2026, 7, 28, 17, 0),  False, "post-market",  "martes a la tarde"),
        ((2026, 7, 28, 20, 30), True,  "overnight",    "martes de noche -> SI"),
        ((2026, 7, 29, 2, 0),   True,  "overnight",    "miercoles madrugada -> SI"),
        ((2026, 7, 29, 6, 0),   False, "pre-market",   "miercoles temprano"),
        ((2026, 7, 31, 21, 0),  False, "cerrado",      "VIERNES de noche -> NO hay sesion"),
        ((2026, 8, 1, 2, 0),    False, "fin de semana", "sabado madrugada -> NO"),
        ((2026, 8, 2, 21, 0),   True,  "overnight",    "DOMINGO de noche -> SI (abre la semana)"),
    ]
    ok = True
    for partes, esperado, sesion_esp, porque in casos:
        t = datetime(*partes, tzinfo=ET)
        got = es_sesion_overnight(t)
        ses = nombre_sesion(t)
        bien = (got == esperado and ses == sesion_esp)
        ok = ok and bien
        print(f"  {'OK ' if bien else '***'} {t.strftime('%a %d/%m %H:%M')}  "
              f"overnight={str(got):5} sesion={ses:14} | {porque}")
    print()
    return ok


def parte1b() -> bool:
    """Regresion del bug del 29/07/2026: durante el overnight, el filtro de
    'ordenes de hoy' caia en el FUTURO y escondia TODAS las ordenes (el usuario
    mando una orden desde el ladder, Alpaca la acepto, y la app no la mostraba)."""
    if ET is None:
        return True
    print("PARTE 1b: el filtro de 'ordenes del dia' NUNCA puede quedar en el futuro")
    print("-" * 68)
    ok = True
    casos = [
        ((2026, 7, 28, 23, 38), "de noche, en pleno overnight (el caso del bug)"),
        ((2026, 7, 29, 2, 30),  "madrugada (el dia operativo empezo ayer)"),
        ((2026, 7, 29, 3, 59),  "un minuto antes del corte de las 04:00"),
        ((2026, 7, 29, 4, 1),   "un minuto despues del corte"),
        ((2026, 7, 29, 10, 0),  "media rueda"),
        ((2026, 7, 29, 19, 0),  "post-market"),
    ]
    for partes, porque in casos:
        t = datetime(*partes, tzinfo=ET)
        ini = inicio_dia_operativo(t)
        futuro = ini > t
        horas = (t - ini).total_seconds() / 3600
        bien = (not futuro) and 0 <= horas <= 24
        ok = ok and bien
        print(f"  {'OK ' if bien else '***'} {t.strftime('%a %d/%m %H:%M ET')} -> pide desde "
              f"{ini.strftime('%d/%m %H:%M UTC')} ({horas:4.1f}h atras) | {porque}")
    print()
    return ok


def parte2() -> bool:
    from tradingbot.connectors.alpaca import AlpacaBroker
    from tradingbot.connectors.alpaca_stream import AlpacaMarketStream

    print("PARTE 2: contra Alpaca, AHORA")
    print("-" * 68)
    b = AlpacaBroker.from_credentials(environment="live")
    s = AlpacaMarketStream.from_credentials(environment="live")
    print(f"  sesion actual        : {nombre_sesion()}")
    print(f"  feed configurado     : {b._feed}")
    print(f"  feed que usa AHORA   : {b.feed_actual()}")
    print(f"  stream que usa AHORA : {s.url_actual()}")
    q = b.get_quote("SPY")
    print(f"  SPY: bid {q.bid} x ask {q.ask}")
    ok = q.bid > 0 and q.ask > 0
    print(f"  -> {'OK: hay precios en vivo' if ok else 'sin precios (mercado sin actividad)'}")
    return ok


def main() -> None:
    ok = parte1()
    ok = parte1b() and ok
    if "--real" in sys.argv:
        ok = parte2() and ok
    else:
        print("(para probarlo tambien contra Alpaca ahora mismo: --real)")
    print("\nOK: la app elige el feed segun la sesion." if ok else "\n*** HAY FALLOS.")


if __name__ == "__main__":
    main()
