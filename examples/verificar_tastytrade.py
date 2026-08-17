"""
Verifica el conector de TASTYTRADE metodo por metodo contra el SANDBOX.

No toca dinero real: usa la cuenta de sandbox de tastytrade (se reinicia cada 24 h).
Deja todo limpio al terminar (cancela lo que haya mandado).

    python examples/verificar_tastytrade.py

Con el MERCADO ABIERTO se puede probar ademas que las ordenes se ejecuten de
verdad, que aparezca la posicion (larga y corta) y que el resultado realizado sea
exacto. Eso manda ordenes que SE LLENAN en el sandbox:

    python examples/verificar_tastytrade.py --con-mercado-abierto
"""
from __future__ import annotations

import configparser
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.tastytrade import _ACCION, _EFECTO, TastytradeBroker  # noqa: E402
from tradingbot.core.models import OrderRequest, OrderStatus, OrderType, Side  # noqa: E402


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

    # OJO con el precio: con el mercado ABIERTO, una VENTA por DEBAJO del mercado es
    # ejecutable y se llena al instante (paso: una venta a 5.00 con AAPL en 307 dejo
    # un corto abierto). Para que la orden quede QUIETA y se pueda cancelar, la venta
    # tiene que ir MUY POR ENCIMA del mercado (y la compra, muy por debajo).
    # El corto va en OTRO simbolo a proposito. Medido el 17/08/2026: el sandbox de
    # Tasty ACEPTA el cancel de estos cortos (contesta "Cancel Requested") pero
    # NUNCA lo completa: la orden vuelve a "Live" y queda viva hasta el cierre. Y
    # como Tasty no admite una compra y una venta abiertas en el mismo simbolo, si
    # el corto fuera de AAPL, el sobrante trababa el ciclo de ordenes de la corrida
    # siguiente. Con simbolos separados, cada prueba se banca los restos de la otra.
    print("\n=== VENTA EN CORTO (Sell to Open, precio alto: no se ejecuta) ===")
    s = chequear("place_order sell_short 5 MSFT @ 9999",
                 lambda: b.place_order(
                     OrderRequest("MSFT", Side.SELL_SHORT, 5, 9999.00, OrderType.LIMIT)))
    if s is not None:
        vuelta = b.get_order(s.id)
        bien = vuelta.side == Side.SELL_SHORT
        print(f"  {'OK ' if bien else '***'} el lado vuelve como SELL_SHORT "
              f"(leido: {vuelta.side.value})")
        ok += bien
        fallos += (not bien)
        chequear("cancel_order (corto)", lambda: (b.cancel_order(s.id), "cancelada")[1])

    # Con el mercado ABIERTO se puede probar lo que de verdad importa: que las
    # ordenes se EJECUTEN, que aparezca la posicion y que el resultado realizado
    # sea exacto. El sandbox usa PRECIOS REALES (verificado el 10/08/2026), asi que
    # una limite lejos del mercado no se llena: para forzar ejecucion, a mercado.
    if "--con-mercado-abierto" in sys.argv:
        print("\n=== EJECUCION REAL (mercado abierto) ===")
        cuenta = b.get_account_id()

        def efectivo() -> float:
            d = b._pedir("GET", f"/accounts/{cuenta}/balances")["data"]
            return float(d.get("cash-balance") or 0.0)

        def esperar(oid, seg=5.0):
            time.sleep(seg)
            return b.get_order(oid)

        cash0, pl0 = efectivo(), b.get_day_pnl().realizado
        compra = esperar(b.place_order(
            OrderRequest("AAPL", Side.BUY, 10, 0.0, OrderType.MARKET)).id)
        lleno = compra.status == OrderStatus.FILLED
        print(f"  {'OK ' if lleno else '***'} la compra se EJECUTA "
              f"(estado {compra.status.value} @ {compra.avg_fill_price})")
        ok += lleno
        fallos += (not lleno)

        pos = b.get_positions()
        bien = len(pos) == 1 and pos[0].quantity == 10 and pos[0].is_long
        print(f"  {'OK ' if bien else '***'} aparece la POSICION larga: "
              f"{[(p.symbol, p.quantity, p.avg_price) for p in pos]}")
        ok += bien
        fallos += (not bien)

        # con la posicion ABIERTA el realizado casi no se mueve (no cerramos nada).
        # Este es el chequeo que descubrio el bug: antes saltaba al costo de la compra.
        abierto = b.get_day_pnl().realizado
        sano = abs(abierto - pl0) < 5.0
        print(f"  {'OK ' if sano else '***'} el realizado NO salta con la posicion "
              f"abierta ({abierto - pl0:+.4f}; el costo fue ~3070)")
        ok += sano
        fallos += (not sano)

        venta = esperar(b.place_order(
            OrderRequest("AAPL", Side.SELL, 10, 0.0, OrderType.MARKET)).id)
        cerro = venta.status == OrderStatus.FILLED and not b.get_positions()
        print(f"  {'OK ' if cerro else '***'} la venta CIERRA la posicion "
              f"(@ {venta.avg_fill_price})")
        ok += cerro
        fallos += (not cerro)

        # el realizado tiene que moverse EXACTAMENTE lo que se movio el efectivo
        cash1, pl1 = efectivo(), b.get_day_pnl().realizado
        exacto = abs((cash1 - cash0) - (pl1 - pl0)) < 0.001
        print(f"  {'OK ' if exacto else '***'} el realizado coincide con el efectivo: "
              f"informa {pl1 - pl0:+.4f} / efectivo {cash1 - cash0:+.4f}")
        ok += exacto
        fallos += (not exacto)

        # corto ejecutado de verdad
        corto = esperar(b.place_order(
            OrderRequest("AAPL", Side.SELL_SHORT, 10, 0.0, OrderType.MARKET)).id)
        pos = b.get_positions()
        en_corto = bool(pos) and pos[0].quantity == -10 and pos[0].is_short
        print(f"  {'OK ' if en_corto else '***'} el CORTO deja posicion negativa: "
              f"{[(p.symbol, p.quantity) for p in pos]}")
        ok += en_corto
        fallos += (not en_corto)

        cubrir = esperar(b.place_order(
            OrderRequest("AAPL", Side.BUY_TO_COVER, 10, 0.0, OrderType.MARKET)).id)
        plano = cubrir.status == OrderStatus.FILLED and not b.get_positions()
        print(f"  {'OK ' if plano else '***'} el BUY TO COVER cierra el corto")
        ok += plano
        fallos += (not plano)

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
    #
    # La limpieza NO puede tumbar la corrida: si el sandbox se niega a cancelar
    # algo, eso no dice nada de lo que se estaba probando. Antes reventaba con un
    # error y la corrida entera terminaba en rojo con todas las pruebas en verde.
    print("\n=== LIMPIEZA ===")
    vivas = b.get_open_orders()
    canceladas = trabadas = 0
    for x in vivas:
        try:
            b.cancel_order(x.id)
            canceladas += 1
        except Exception as e:  # noqa: BLE001
            trabadas += 1
            print(f"  (no se dejo cancelar {x.id} {x.symbol}: {str(e)[-60:]})")
    print(f"  cancele {canceladas} orden(es) que hubieran quedado vivas"
          + (f", {trabadas} no se dejaron" if trabadas else ""))
    time.sleep(1)
    print(f"  vivas al final: {len(b.get_open_orders())} | "
          f"posiciones: {len(b.get_positions())}")

    print(f"\n{ok} OK / {fallos} fallos")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
