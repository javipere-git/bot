"""
Verifica las SALVAGUARDAS del modo LIVE de Alpaca (dinero real).

NO manda ninguna orden: solo lectura y chequeos de configuracion.

Confirma que:
  1. Los perfiles de Alpaca LIVE existen y estan marcados como DINERO REAL
     (es_live=True), que es lo que dispara todas las protecciones.
  2. Apuntan a la URL de operativa REAL (api.alpaca.markets), no a la de paper.
  3. Hay tope de acciones por orden configurado ([safety] live_max_shares).
  4. El chequeo previo de venta en CORTO lee bien la cuenta.
  5. El gatillo sigue funcionando: SIN claves live, el conector rechaza operar real.

    python examples/probar_salvaguardas_alpaca_live.py
"""
from __future__ import annotations

import configparser
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.alpaca import AlpacaBroker, LIVE_TRADING_BASE  # noqa: E402
from tradingbot.gui.main_window import _live_max_shares  # noqa: E402
from tradingbot.gui.perfiles import perfiles_disponibles  # noqa: E402


def main() -> None:
    todo_ok = True
    perfiles = perfiles_disponibles()

    print("1) Perfiles de Alpaca LIVE (dinero real):")
    vivos = [p for p in perfiles if p.id.startswith("alpaca_live")]
    for p in vivos:
        print(f"     - {p.cuenta_texto}   (es_live={p.es_live})")
    ok1 = bool(vivos) and all(p.es_live for p in vivos)
    todo_ok = todo_ok and ok1
    print(f"   Todos marcados como DINERO REAL: {ok1}  (eso activa las protecciones)\n")

    print("2) Apuntan a la cuenta REAL (no a paper):")
    b = AlpacaBroker.from_credentials(environment="live")
    ok2 = b._trading_base == LIVE_TRADING_BASE and b._es_live
    todo_ok = todo_ok and ok2
    print(f"   base = {b._trading_base}   -> {ok2}\n")

    print("3) Tope de acciones por orden en LIVE:")
    cap = _live_max_shares()
    ok3 = cap > 0
    todo_ok = todo_ok and ok3
    print(f"   live_max_shares = {cap}  (si configuras mas cantidad, el bot NO arranca)\n")

    print("4) Chequeo previo de venta en CORTO:")
    corto = b.puede_operar_en_corto()
    print(f"   esta cuenta permite shortear: {corto}")
    if corto is False:
        print("   -> el bot se NEGARA a arrancar en 'Venta (ask-)' y te avisara.")
    print()

    print("5) El gatillo sigue vivo: sin claves live, no se puede operar real.")
    cfg = configparser.ConfigParser()
    cfg["alpaca"] = {"paper_key_id": "x", "paper_secret": "y",
                     "live_key_id": "", "live_secret": ""}
    tmp = os.path.join(tempfile.gettempdir(), "cred_sin_live.ini")
    with open(tmp, "w", encoding="utf-8") as f:
        cfg.write(f)
    try:
        AlpacaBroker.from_credentials(path=tmp, environment="live")
        print("   *** FALLO: creo un broker live sin claves.")
        todo_ok = False
    except ValueError as e:
        print(f"   OK: lo rechaza -> {str(e)[:80]}...")
    finally:
        os.remove(tmp)

    print("\nProtecciones activas al operar Alpaca en REAL:")
    print("   - Escribir REAL al elegir el perfil, y cartel de confirmacion al Iniciar")
    print("   - Tope de acciones por orden (live_max_shares)")
    print("   - Banner VERDE + aviso en el registro")
    print("   - No abrir posicion nueva si ya hay uNA abierta")
    print("   - Aviso previo si la cuenta no permite shortear")

    print("\nOK: las salvaguardas de Alpaca LIVE estan activas."
          if todo_ok else "\n*** HAY FALLOS EN LAS SALVAGUARDAS.")


if __name__ == "__main__":
    main()
