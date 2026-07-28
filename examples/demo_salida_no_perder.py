"""
Prueba el tope de "no cerrar a peor precio que el promedio" en la salida
(no toca dinero: conector de mentira).

Escenario del usuario: largo 10 @ 100.00, con 4 salidas 50%, 60%, 70% y CRUZAR.
El mercado esta por DEBAJO del promedio (bid 99.50 x ask 99.70), asi que los
offsets 50/60/70 darian precios perdedores. Con el tope activado:
  - los escalones normales quedan topados al promedio (100.00), nunca por debajo,
  - los niveles que quedan al mismo precio NO se reprecian (ahorra llamadas),
  - solo "cruzar" sale por debajo del promedio (para eso esta).

    python examples/demo_salida_no_perder.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker  # noqa: E402
from tradingbot.core.config import EngineConfig, ExitLevel, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine, Outcome  # noqa: E402
from tradingbot.core.models import OrderRequest, Position, Side  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


class BrokerContando(FakeBroker):
    """Cuenta los repricios y guarda a que precios se mandaron las ordenes de venta."""

    def __init__(self) -> None:
        super().__init__()
        self.reprecios = 0
        self.precios_venta: list[float] = []

    def place_order(self, request: OrderRequest):
        if request.side == Side.SELL:
            self.precios_venta.append(request.price)
        return super().place_order(request)

    def modify_order(self, order_id, *, price=None, quantity=None):
        self.reprecios += 1
        if price is not None:
            self.precios_venta.append(price)
        return super().modify_order(order_id, price=price, quantity=quantity)


def _config(topar: bool) -> EngineConfig:
    return EngineConfig(
        side=Side.BUY,
        quantity=10,
        order1=OrderConfig(0.0, OffsetUnit.DOLLARS, 1.0),
        exit_levels=[
            ExitLevel(50.0, OffsetUnit.PERCENT_SPREAD, 1.0),
            ExitLevel(60.0, OffsetUnit.PERCENT_SPREAD, 1.0),
            ExitLevel(70.0, OffsetUnit.PERCENT_SPREAD, 1.0),
            ExitLevel(0.0, OffsetUnit.PERCENT_SPREAD, 1.0, cross=True),
        ],
        no_cerrar_bajo_promedio=topar,
    )


def _correr(topar: bool):
    broker = BrokerContando()
    broker._positions["TEST"] = Position("TEST", 10, 100.00)   # largo, promedio 100
    broker.set_quote("TEST", 99.50, 99.70)                      # mercado por DEBAJO
    engine = BotEngine(broker, _config(topar), clock=FakeClock(), log=lambda m: print("   " + m))
    outcome = engine.manage_exit(Position("TEST", 10, 100.00))
    return broker, outcome


def main() -> None:
    print("CON el tope activado (promedio 100.00, mercado 99.50 x 99.70):")
    print("-" * 70)
    broker, outcome = _correr(topar=True)
    print("-" * 70)
    no_cross = broker.precios_venta[:-1]   # todos menos el ultimo (cruzar)
    cruce = broker.precios_venta[-1]
    print(f"precios de las ordenes de venta: {broker.precios_venta}")
    print(f"repricios (modify) enviados: {broker.reprecios}")
    ok_topado = all(p >= 100.00 for p in no_cross)
    ok_cruce = cruce < 100.00
    ok_ahorro = broker.reprecios <= 1     # 50/60/70 al mismo precio: no reprecia; solo cruza
    print(f"\nescalones normales nunca por debajo de 100.00: {ok_topado}")
    print(f"cruzar SI sale por debajo (a {cruce}): {ok_cruce}")
    print(f"no reprecio los niveles topados al mismo precio: {ok_ahorro} "
          f"(reprecios={broker.reprecios})")
    print(f"cerro: {outcome.value}")

    print("\nSIN el tope (comportamiento historico), para comparar:")
    print("-" * 70)
    broker2, _ = _correr(topar=False)
    print("-" * 70)
    print(f"precios de las ordenes de venta: {broker2.precios_venta}")
    hubo_perdedoras = any(p < 100.00 for p in broker2.precios_venta[:-1])
    print(f"habia escalones por debajo del promedio: {hubo_perdedoras} (esperado True)")

    todo = ok_topado and ok_cruce and ok_ahorro and hubo_perdedoras
    print("\nOK: el tope funciona (escalones nunca peor que el promedio; cruzar si; "
          "sin reprecios al pedo)." if todo else "\n*** REVISAR: ver arriba.")


if __name__ == "__main__":
    main()
