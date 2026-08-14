"""
Tastytrade: las ordenes y el P/L tienen que ser del DIA DE HOY.

Dos problemas reales del 14/08/2026, los dos por lo mismo: Tasty devuelve datos de
sesiones anteriores y hay que acotarlos al dia operativo en curso.

 1. ORDENES. Tasty NO filtra por dia (como Alpaca). Medido en la cuenta real ese
    dia: sin filtro **1.881** ordenes, de las cuales **1.593 eran de ayer**; con el
    filtro, **288**. Como las tablas se ordenan por hora, las de ayer quedaban
    arriba de todo.

 2. P/L DEL DIA. 'intraday-equities-cash-amount' NO arranca en cero: conserva el de
    la sesion anterior hasta el primer movimiento del dia. Por eso a la mañana se
    veia el resultado de AYER y "se acomodaba solo" al entrar en posicion. El campo
    'intraday-equities-cash-effective-date' dice a que dia corresponde: si no es hoy,
    el realizado del dia es CERO.

No manda ninguna orden. La parte contra la cuenta real es solo lectura y se saltea
sola si no hay credenciales.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.tastytrade import TastytradeBroker   # noqa: E402
from tradingbot.core.horarios import ahora_et, inicio_dia_operativo  # noqa: E402

fallos = []


def check(ok: bool, titulo: str, detalle: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FALLO'}  {titulo}{'  ->  ' + detalle if detalle else ''}")
    if not ok:
        fallos.append(titulo)


print("\n=== 1. La fecha efectiva decide si el P/L es de hoy ===")
t = ahora_et()
if t is None:
    print("  (sin zona horaria: se saltea)")
else:
    hoy = (t if t.hour >= 4 else t - timedelta(days=1)).strftime("%Y-%m-%d")
    ayer = (datetime.strptime(hoy, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    check(TastytradeBroker._es_de_hoy(hoy) is True, "la de hoy se acepta", hoy)
    check(TastytradeBroker._es_de_hoy(ayer) is False,
          "la de AYER se rechaza (era el bug)", ayer)
    check(TastytradeBroker._es_de_hoy(None) is False, "sin fecha, no se usa el monto")
    check(TastytradeBroker._es_de_hoy(f"{hoy}T14:06:34Z") is True,
          "tolera que venga con hora")

print("\n=== 2. El corte pedido a Tasty es el del dia operativo (04:00 ET) ===")
corte = inicio_dia_operativo()
check(corte <= datetime.now(timezone.utc),
      "el corte NUNCA queda en el futuro (esconderia TODAS las ordenes)",
      corte.isoformat())
check((datetime.now(timezone.utc) - corte) <= timedelta(hours=24),
      "y no se va mas de 24 horas atras")

print("\n=== 3. El P/L descarta el monto de la sesion anterior ===")
# Con un balances de mentira, que es la unica forma de reproducir el caso: el campo
# trayendo el monto de AYER, que es lo que pasa a la mañana hasta que operas.


class BrokerFalso(TastytradeBroker):
    """Solo reemplaza la respuesta del broker; el calculo es el de verdad."""

    def __init__(self, balances):
        self._balances = balances
        self._account = "TEST"          # get_day_pnl lo usa para armar la ruta

    def _pedir(self, metodo, ruta, **kw):          # noqa: D102
        return {"data": self._balances}

    def get_positions(self):                        # sin posiciones abiertas
        return []


if t is not None:
    ayer_bal = {"intraday-equities-cash-amount": "125.50",
                "intraday-equities-cash-effect": "Credit",
                "intraday-equities-cash-effective-date": ayer,
                "cash-balance": "3500"}
    hoy_bal = dict(ayer_bal, **{"intraday-equities-cash-effective-date": hoy})
    p_ayer = BrokerFalso(ayer_bal).get_day_pnl()
    p_hoy = BrokerFalso(hoy_bal).get_day_pnl()
    check(p_ayer is not None and p_ayer.realizado == 0.0,
          "si el monto es de AYER, el realizado de hoy es CERO",
          str(p_ayer.realizado if p_ayer else None))
    check(p_hoy is not None and abs(p_hoy.realizado - 125.50) < 0.001,
          "si es de hoy, se usa tal cual", str(p_hoy.realizado if p_hoy else None))

print("\n=== 4. Contra la cuenta real (SOLO LECTURA) ===")
try:
    b = TastytradeBroker.from_credentials(environment="production")
except Exception as e:  # noqa: BLE001
    print(f"  (sin credenciales de produccion, se saltea: {str(e)[:60]})")
else:
    def total(**extra):
        js = b._pedir("GET", f"/accounts/{b._account}/orders",
                      params={"per-page": 1, "sort": "Desc", **extra})
        return js.get("pagination", {}).get("total-items")

    sin_filtro = total()
    con_filtro = total(**{"start-at": b._desde_hoy()})
    print(f"  sin filtro: {sin_filtro} ordenes | con el filtro nuevo: {con_filtro}")
    check(con_filtro is not None and sin_filtro is not None and con_filtro <= sin_filtro,
          "el filtro acota de verdad (no lo ignora)")

    # OJO: hay que probar la PASADA COMPLETA (sin limit), que es la que traia las de
    # ayer. Con limit=200 no se nota nada: las 200 mas recientes son de hoy igual, y
    # el chequeo pasaria aunque el filtro no estuviera.
    ordenes = b.get_orders()
    dias = sorted({str(o.create_date or "")[:10] for o in ordenes} - {""})
    print(f"  la pasada completa trajo {len(ordenes)} ordenes")
    check(bool(dias), "las ordenes traen su fecha (si no, esto no probaria nada)")
    check(len(dias) == 1, "la pasada completa trae UN solo dia", str(dias))
    if t is not None:
        check(dias == [hoy], "y ese dia es HOY", f"{dias} vs {hoy}")
    check(con_filtro is not None and len(ordenes) <= con_filtro + 5,
          "trae las del dia, no el historico entero",
          f"{len(ordenes)} vs {sin_filtro} sin filtrar")

    pnl = b.get_day_pnl()
    check(pnl is not None, "el P/L del dia se lee", str(pnl))

print()
if fallos:
    print(f"PROBLEMAS: {len(fallos)}")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("OK: Tasty informa solo el dia de hoy, en ordenes y en el resultado.")
