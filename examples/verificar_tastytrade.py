"""
Verifica el conector de TASTYTRADE metodo por metodo contra el SANDBOX.

No toca dinero real: usa la cuenta de sandbox de tastytrade (se reinicia cada 24 h).
Deja todo limpio al terminar (cancela lo que haya mandado).

    python examples/verificar_tastytrade.py
"""
from __future__ import annotations

import configparser
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.tastytrade import _ACCION, _EFECTO, TastytradeBroker  # noqa: E402
from tradingbot.core.models import OrderRequest, OrderType, Side  # noqa: E402


def main() -> int:
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(raiz, "config", "credentials.ini"))
    if not cfg.has_section("tastytrade") or not cfg["tastytrade"].get(
            "sandbox_refresh_token", "").strip():
        print("Falta la seccion [tastytrade] con las credenciales de SANDBOX en "
              "config/credentials.ini -> nada que verificar.")
        return 0

    b = TastytradeBroker.from_credentials(environment="sandbox")
    ok = fallos = 0

    def chequear(nombre, fn):
        nonlocal ok, fallos
        try:
            r = fn()
            print(f"  OK   {nombre}: {r}")
            ok += 1
            return r
        except Exception as e:  # noqa: BLE001
            print(f"  ***  {nombre}: {e}")
            fallos += 1
            return None

    print("=== LECTURA ===")
    chequear("get_account_id", b.get_account_id)
    chequear("get_positions", lambda: f"{len(b.get_positions())} posiciones")
    chequear("get_open_orders", lambda: f"{len(b.get_open_orders())} vivas")
    chequear("get_orders", lambda: f"{len(b.get_orders())} del dia")
    chequear("get_orders(limit=3)", lambda: f"{len(b.get_orders(limit=3))} recientes")
    chequear("get_buying_power", b.get_buying_power)
    chequear("get_day_pnl", b.get_day_pnl)
    chequear("distingue_venta_en_corto", b.distingue_venta_en_corto)
    chequear("puede_operar_en_corto", b.puede_operar_en_corto)

    print("\n=== MAPEO DE LADOS (nuestro lado -> accion de Tasty) ===")
    esperado = {
        Side.BUY: "Buy to Open",
        Side.SELL: "Sell to Close",
        Side.SELL_SHORT: "Sell to Open",
        Side.BUY_TO_COVER: "Buy to Close",
    }
    for lado, accion in esperado.items():
        bien = _ACCION[lado] == accion
        print(f"  {'OK ' if bien else '***'} {lado.value:15} -> {_ACCION[lado]:15} "
              f"({_EFECTO[lado]})")
        ok += bien
        fallos += (not bien)

    # limite 5.00 => por la regla del sandbox queda VIVA sin llenarse
    print("\n=== CICLO DE ORDEN (mandar -> leer -> mover -> cancelar) ===")
    o = chequear("place_order buy 1 AAPL @ 5.00",
                 lambda: b.place_order(
                     OrderRequest("AAPL", Side.BUY, 1, 5.00, OrderType.LIMIT)))
    if o is not None:
        leida = chequear("get_order", lambda: b.get_order(o.id))
        if leida is not None and leida.symbol != "AAPL":
            print("   *** el simbolo no volvio bien")
            fallos += 1
        m = chequear("modify_order a 5.50", lambda: b.modify_order(o.id, price=5.50))
        if m is not None:
            cambio = str(m.id) != str(o.id)
            print(f"       id viejo {o.id} -> id nuevo {m.id}")
            print(f"  {'OK ' if cambio else '***'} Tasty REEMPLAZA con id nuevo "
                  f"(como Alpaca; el motor lo cubre con _orden_vigente)")
            ok += cambio
            fallos += (not cambio)
            chequear("cancel_order", lambda: (b.cancel_order(m.id), "cancelada")[1])
            time.sleep(1)

    print("\n=== VENTA EN CORTO (Sell to Open) ===")
    s = chequear("place_order sell_short 5 AAPL @ 5.00",
                 lambda: b.place_order(
                     OrderRequest("AAPL", Side.SELL_SHORT, 5, 5.00, OrderType.LIMIT)))
    if s is not None:
        vuelta = b.get_order(s.id)
        bien = vuelta.side == Side.SELL_SHORT
        print(f"  {'OK ' if bien else '***'} el lado vuelve como SELL_SHORT "
              f"(leido: {vuelta.side.value})")
        ok += bien
        fallos += (not bien)
        chequear("cancel_order (corto)", lambda: (b.cancel_order(s.id), "cancelada")[1])

    print("\n=== COTIZACION (en sandbox NO hay: se espera un aviso claro) ===")
    try:
        q = b.get_quote("AAPL")
        print(f"  OK   get_quote: bid={q.bid} ask={q.ask}")
        ok += 1
    except Exception as e:  # noqa: BLE001
        aviso = "perfil hibrido" in str(e)
        print(f"  {'OK ' if aviso else '***'} aviso esperado: {str(e)[:110]}...")
        ok += aviso
        fallos += (not aviso)

    # dejar la cuenta como estaba
    print("\n=== LIMPIEZA ===")
    vivas = b.get_open_orders()
    for x in vivas:
        b.cancel_order(x.id)
    print(f"  cancele {len(vivas)} orden(es) que hubieran quedado vivas")
    time.sleep(1)
    print(f"  vivas al final: {len(b.get_open_orders())} | "
          f"posiciones: {len(b.get_positions())}")

    print(f"\n{ok} OK / {fallos} fallos")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
