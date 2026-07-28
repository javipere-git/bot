"""
Prueba de INTEGRACION con MERCADO ABIERTO (sandbox, plata de mentira).

Recorre una watchlist con el cerebro + el conector REAL de Tradier, colocando
las ordenes por DEBAJO del mercado (offset negativo) para que NO se llenen.
El objetivo es validar el recorrido completo -mandar -> MODIFICAR -> cancelar-,
en especial el "modificar", que con el mercado cerrado no se podia probar.

No crea posiciones a proposito. Limpia cualquier orden viva al final.

Para correrlo:  python examples/probar_integracion_abierto.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.tradier import TradierBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine  # noqa: E402
from tradingbot.core.models import Side  # noqa: E402
from tradingbot.core.watchlist import parse_watchlist  # noqa: E402

WATCHLIST = "MU GE WING CAR AMD CRDO TTMI MELI"


def main() -> None:
    broker = TradierBroker.from_credentials(environment="sandbox")
    symbols = parse_watchlist(WATCHLIST)

    print("INTEGRACION (mercado abierto) - cerebro + Tradier REAL (sandbox)")
    print("-" * 64)
    print(f"Estado inicial: posiciones {len(broker.get_positions())} | "
          f"ordenes abiertas {len(broker.get_open_orders())}")
    print("Cotizaciones (demoradas ~15 min en sandbox):")
    validos: list[str] = []
    for s in symbols:
        try:
            q = broker.get_quote(s)
            validos.append(s)
            print(f"  {s:<6} bid {q.bid:>9.2f}  x  ask {q.ask:>9.2f}   (spread {q.spread:.2f})")
        except Exception as e:
            print(f"  {s:<6} sin cotizacion ({e}) -> lo salteo")
    print("-" * 64)

    # Offsets NEGATIVOS a proposito: las ordenes quedan por debajo del mercado
    # y no se llenan. Probamos el recorrido (incluido modificar), no un llenado.
    cfg = EngineConfig(
        side=Side.BUY,
        quantity=1,
        order1=OrderConfig(-0.50, OffsetUnit.DOLLARS, timeout_s=2),
        order2=OrderConfig(-1.00, OffsetUnit.DOLLARS, timeout_s=2),
        poll_interval_s=1.0,
    )

    log_lines: list[str] = []

    def logger(m: str) -> None:
        print(m)
        log_lines.append(m)

    engine = BotEngine(broker, cfg, log=logger)
    try:
        engine.scan_and_enter(validos, max_cycles=1)
    except Exception as e:
        print(f"Error durante el recorrido: {e}")
    finally:
        abiertas = broker.get_open_orders()
        if abiertas:
            print(f"Limpieza: cancelo {len(abiertas)} orden(es) viva(s)...")
            for o in abiertas:
                try:
                    broker.cancel_order(o.id)
                except Exception:
                    pass
        posiciones = broker.get_positions()
        print("-" * 64)
        print(f"Estado final: posiciones {len(posiciones)} | "
              f"ordenes abiertas {len(broker.get_open_orders())}")
        if posiciones:
            print(f"  ATENCION: quedo(aron) posicion(es) inesperada(s): {posiciones}")

        intentos = sum(1 for ln in log_lines if "(modify)" in ln)
        fallidos = sum(1 for ln in log_lines if "no se pudo modificar" in ln)
        print("-" * 64)
        print(f"Modificaciones intentadas: {intentos} | fallidas: {fallidos}")
        if intentos > 0 and fallidos == 0:
            print(">>> El 'modificar' AHORA funciona (mercado abierto). Era lo que faltaba validar.")
        elif intentos == 0:
            print(">>> No hubo intentos de modificar (raro: revisar).")
        else:
            print(">>> Algunas modificaciones fallaron: revisar los mensajes de arriba.")


if __name__ == "__main__":
    main()
