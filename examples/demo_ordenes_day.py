"""
GARANTIA: sin tildar "Ext. hours", las ordenes son SIEMPRE day. Y siguen siendo day
despues de moverlas.

Por que existe este test: mandar sin querer una orden de horario extendido durante la
rueda regular es peligroso. Aca se revisa el CUERPO EXACTO de lo que cada conector le
manda al broker, sin tocar la red, asi queda congelado para siempre y cualquier broker
nuevo tiene que cumplir lo mismo.

Se verifica, para Tradier y para Alpaca:
  1. Mandar SIN tildar          -> el broker recibe "day" (Tradier) / sin extended (Alpaca)
  2. Mandar TILDADO             -> recibe la duracion extendida / extended_hours=true
  3. MOVER una orden day        -> sigue siendo day
  4. MOVER una orden extendida  -> sigue siendo extendida (no se degrada a day)

    python examples/demo_ordenes_day.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.alpaca import AlpacaBroker  # noqa: E402
from tradingbot.connectors.tradier import TradierBroker  # noqa: E402
from tradingbot.core.models import (  # noqa: E402
    Duration,
    OrderRequest,
    OrderType,
    Side,
)


class EspiaTradier(TradierBroker):
    """Tradier que NO llama a la red: anota lo que hubiera mandado."""

    def __init__(self):
        self.enviado = []
        self._account_id = "TEST"
        self._token = "x"
        self._base = "https://test"

    def _send(self, method, path, data=None, params=None):
        self.enviado.append({"metodo": method, "datos": dict(data or {})})
        return {"order": {"id": 1, "status": "ok"}}


class EspiaAlpaca(AlpacaBroker):
    """Alpaca que NO llama a la red: anota lo que hubiera mandado."""

    def __init__(self):
        self.enviado = []
        self._account_id = "TEST"
        self._feed = "sip"
        self._es_live = False

    def _send(self, method, path, params=None, json_body=None, base=None):
        self.enviado.append({"metodo": method, "datos": dict(json_body or {})})
        return {"id": "1", "symbol": "SPY", "side": "buy", "qty": "1",
                "limit_price": "100", "status": "new", "type": "limit"}


def main() -> None:
    fallos = []

    print("=" * 72)
    print("TRADIER")
    print("=" * 72)
    t = EspiaTradier()

    t.place_order(OrderRequest("SPY", Side.BUY, 10, 100.0, OrderType.LIMIT))
    dur = t.enviado[-1]["datos"].get("duration")
    ok = dur == "day"
    print(f"  1. mandar SIN tildar      -> duration={dur!r}   (esperado 'day')")
    fallos += [] if ok else ["tradier enviar sin tildar"]

    t.place_order(OrderRequest("SPY", Side.BUY, 10, 100.0, OrderType.LIMIT, extended=True))
    dur_ext = t.enviado[-1]["datos"].get("duration")
    ok = dur_ext in ("pre", "post")
    print(f"  2. mandar TILDADO         -> duration={dur_ext!r}  (esperado 'pre' o 'post')")
    fallos += [] if ok else ["tradier enviar tildado"]

    t.modify_order("1", price=101.0, duration=Duration.DAY)
    dur_mov = t.enviado[-1]["datos"].get("duration")
    ok = dur_mov == "day"
    print(f"  3. MOVER una orden day    -> duration={dur_mov!r}   (esperado 'day')")
    fallos += [] if ok else ["tradier mover day"]

    t.modify_order("1", price=101.0, duration=Duration.POST)
    dur_mov2 = t.enviado[-1]["datos"].get("duration")
    ok = dur_mov2 == "post"
    print(f"  4. MOVER una orden post   -> duration={dur_mov2!r}  (esperado 'post')")
    fallos += [] if ok else ["tradier mover post"]

    t.modify_order("1", price=101.0)          # sin decirle nada
    dur_mov3 = t.enviado[-1]["datos"].get("duration")
    ok = dur_mov3 == "day"
    print(f"  5. MOVER sin indicar nada -> duration={dur_mov3!r}   (esperado 'day': lo seguro)")
    fallos += [] if ok else ["tradier mover por defecto"]

    print()
    print("=" * 72)
    print("ALPACA")
    print("=" * 72)
    a = EspiaAlpaca()

    a.place_order(OrderRequest("SPY", Side.BUY, 10, 100.0, OrderType.LIMIT))
    cuerpo = a.enviado[-1]["datos"]
    ok = "extended_hours" not in cuerpo and cuerpo.get("time_in_force") == "day"
    print(f"  1. mandar SIN tildar      -> extended_hours ausente: "
          f"{'extended_hours' not in cuerpo}, time_in_force={cuerpo.get('time_in_force')!r}")
    fallos += [] if ok else ["alpaca enviar sin tildar"]

    a.place_order(OrderRequest("SPY", Side.BUY, 10, 100.0, OrderType.LIMIT, extended=True))
    cuerpo = a.enviado[-1]["datos"]
    ok = cuerpo.get("extended_hours") is True
    print(f"  2. mandar TILDADO         -> extended_hours={cuerpo.get('extended_hours')}")
    fallos += [] if ok else ["alpaca enviar tildado"]

    a.modify_order("1", price=101.0, duration=Duration.DAY)
    cuerpo = a.enviado[-1]["datos"]
    ok = "extended_hours" not in cuerpo and "time_in_force" not in cuerpo
    print(f"  3. MOVER: el cuerpo del PATCH es {cuerpo}")
    print("     -> no toca el horario extendido: Alpaca conserva el de la orden")
    fallos += [] if ok else ["alpaca mover"]

    print()
    print("=" * 72)
    if fallos:
        print("*** FALLOS:", ", ".join(fallos))
    else:
        print("OK: sin tildar Ext. hours, las ordenes son SIEMPRE day, y al moverlas")
        print("    siguen siendo day. Tildado, se respeta el horario extendido.")
    return not fallos


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
