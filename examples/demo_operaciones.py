"""
Historial de operaciones de la cuenta, a un archivo que abre Excel.

PARA QUE: las paginas de los brokers son inservibles para esto. En Alpaca no hay
boton de descargar: hay que seleccionar la tabla a mano, pagina por pagina, o
bajar un PDF por dia. Medido el 17/08/2026 contra las cuentas de verdad, la API
lo entrega entero: Alpaca 3.008 ejecuciones de 30 dias en 6,9 s, Tradier 3.526 en
1,6 s, Tastytrade 252 en 0,6 s.

LO QUE SE VERIFICA:
 1. La hora sale en hora de NUEVA YORK, no en UTC (14:44 UTC = 10:44 en NY: si no
    se convierte, cada operacion figura cuatro horas mas tarde de lo que fue).
 2. Cuando el broker solo informa la FECHA (Tradier), no se inventa un horario.
 3. Cada conector traduce SUS campos a las mismas columnas, y el que no informa
    un dato deja la celda VACIA (un 0 en la comision seria mentira).
 4. El signo: Tasty manda la plata sin signo y aparte un "efecto"; sin eso, una
    comision cobrada y un reintegro se verian igual.
 5. Tradier marca las ventas con la CANTIDAD en negativo: de ahi sale el lado.
 6. El archivo sale ordenado de lo mas viejo a lo mas nuevo.
 7. Con el perfil hibrido, el historial es del broker donde se OPERA.
 8. El cuadro de fechas no deja pedir un rango al reves (el broker devolveria
    vacio y pareceria que no operaste nada).
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.connectors.fake_broker import FakeBroker               # noqa: E402
from tradingbot.core.historial import (                                # noqa: E402
    COLUMNAS,
    a_hora_ny,
    guardar_operaciones,
    resumen,
)

fallos = []


def check(ok, titulo, detalle=""):
    print(f"  {'OK  ' if ok else 'FALLO'}  {titulo}{'  ->  ' + detalle if detalle else ''}")
    if not ok:
        fallos.append(titulo)


carpeta = tempfile.mkdtemp(prefix="operaciones_")

print("\n=== 1. La hora, en hora de Nueva York ===")
check(a_hora_ny("2026-08-17T14:44:06.618Z") == "2026-08-17 10:44:06",
      "14:44 UTC de agosto son las 10:44 de NY", a_hora_ny("2026-08-17T14:44:06.618Z"))
check(a_hora_ny("2026-01-15T14:44:06Z") == "2026-01-15 09:44:06",
      "y en enero son las 09:44 (el horario de verano cambia la cuenta)",
      a_hora_ny("2026-01-15T14:44:06Z"))
check(a_hora_ny("2026-08-17T01:30:00Z") == "2026-08-16 21:30:00",
      "de madrugada en UTC es el dia ANTERIOR en NY",
      a_hora_ny("2026-08-17T01:30:00Z"))

print("\n=== 2. Si el broker no informa la hora, no se inventa ===")
check(a_hora_ny("2026-08-14T00:00:00Z") == "2026-08-14",
      "Tradier manda solo la fecha: queda la fecha sola",
      a_hora_ny("2026-08-14T00:00:00Z"))
check(a_hora_ny(None) == "" and a_hora_ny("") == "", "sin fecha, celda vacia")
check(a_hora_ny("cualquier cosa") == "cualquier cosa",
      "si no lo entiende lo deja tal cual (no lo tira a la basura)")

print("\n=== 3. Cada conector traduce a las mismas columnas ===")
from tradingbot.connectors.alpaca import AlpacaBroker                  # noqa: E402
from tradingbot.connectors.tastytrade import TastytradeBroker          # noqa: E402
from tradingbot.connectors.tradier import TradierBroker                # noqa: E402

alp = object.__new__(AlpacaBroker)
alp._get = lambda *a, **k: [{
    "id": "20260817::abc", "activity_type": "FILL", "type": "partial_fill",
    "transaction_time": "2026-08-17T14:44:06.618Z", "price": "6.04", "qty": "16",
    "side": "sell", "symbol": "bcaru", "order_id": "ord-1",
}] if not k.get("params", {}).get("page_token") else []
ops_a = alp.operaciones("2026-07-18", "2026-08-17")
check(len(ops_a) == 1, "Alpaca devuelve la ejecucion", f"{len(ops_a)}")
a = ops_a[0]
check(a["symbol"] == "BCARU" and a["lado"] == "Venta",
      "Alpaca: simbolo en mayuscula y lado en castellano", f"{a['symbol']} / {a['lado']}")
check(a["importe"] == 96.64, "el importe es cantidad x precio", f"{a['importe']}")
check(a["comision"] is None and a["tasas"] is None,
      "Alpaca no informa comisiones: van VACIAS, no en cero")
check(a["notas"] == "ejecucion parcial", "avisa cuando la ejecucion fue parcial")

tra = object.__new__(TradierBroker)
tra._account_id = "X"
tra._get = lambda *a, **k: {"history": {"event": [
    {"amount": 2761.51, "date": "2026-08-14T00:00:00Z", "type": "trade",
     "trade": {"commission": 0.0, "description": "UTAH MEDICAL", "price": 70.81,
               "quantity": -39.0, "symbol": "UTMD", "trade_type": "equity"}},
    {"amount": -230.01, "date": "2026-08-13T00:00:00Z", "type": "trade",
     "trade": {"commission": 1.5, "description": "VICORE", "price": 11.5,
               "quantity": 20.0, "symbol": "VCRE", "trade_type": "equity"}},
]}}
ops_t = {o["symbol"]: o for o in tra.operaciones("2026-07-18", "2026-08-17")}
check(ops_t["UTMD"]["lado"] == "Venta" and ops_t["VCRE"]["lado"] == "Compra",
      "Tradier: la cantidad en negativo es una VENTA",
      f"{ops_t['UTMD']['lado']} / {ops_t['VCRE']['lado']}")
check(ops_t["UTMD"]["cantidad"] == 39.0,
      "y la cantidad se guarda en positivo", f"{ops_t['UTMD']['cantidad']}")
check(ops_t["VCRE"]["comision"] == 1.5, "Tradier si informa la comision")
check(ops_t["UTMD"]["neto"] == 2761.51 and ops_t["VCRE"]["neto"] == -230.01,
      "el neto conserva el signo: entro plata / salio plata")

tas = object.__new__(TastytradeBroker)
tas._account = "5W"
tas._pedir = lambda *a, **k: {"data": {"items": [
    {"transaction-type": "Trade", "action": "Sell to Close", "symbol": "ULH",
     "quantity": "20", "price": "19.6201", "executed-at": "2026-08-13T15:03:02Z",
     "commission": "1.0", "commission-effect": "Debit",
     "clearing-fees": "0.016", "clearing-fees-effect": "Debit",
     "regulatory-fees": "0.014", "regulatory-fees-effect": "Debit",
     "net-value": "392.372", "net-value-effect": "Credit",
     "order-id": "o-9", "exec-id": "e-9", "destination-venue": "SUSQUEHANNA"},
    {"transaction-type": "Money Movement", "symbol": "", "quantity": "0",
     "price": "0", "executed-at": "2026-08-13T15:03:02Z"},
]}, "pagination": {"total-pages": 1}}
ops_y = tas.operaciones("2026-07-18", "2026-08-17")
check(len(ops_y) == 1, "Tasty deja afuera los movimientos de plata (no son trades)",
      f"{len(ops_y)}")
y = ops_y[0]
check(y["lado"] == "Venta (cierra)",
      "Tasty es el unico que dice si abrio o cerro la posicion", f"{y['lado']}")
check(y["comision"] == -1.0,
      "la comision cobrada va en NEGATIVO (Tasty la manda sin signo)", f"{y['comision']}")
check(y["tasas"] == 0.03, "las tasas se suman (clearing + regulatorias)", f"{y['tasas']}")
check(y["neto"] == 392.372, "el neto cobrado va en positivo", f"{y['neto']}")
check(y["fecha_hora"] == "2026-08-13 11:03:02", "y la hora en NY", y["fecha_hora"])

faltan = [c for c, _ in COLUMNAS
          if c not in a or c not in ops_t["UTMD"] or c not in y]
check(not faltan, "los tres conectores devuelven las MISMAS columnas", f"faltan {faltan}")

print("\n=== 3b. La paginacion: traer TODO, no la primera pagina ===")
# Es lo mas facil de romper: si el 'siguiente' no avanza, o se cuelga pidiendo
# siempre la misma pagina, o devuelve un mes cortado en 100 lineas y ni te enteras.
alp2 = object.__new__(AlpacaBroker)
paginas_alpaca = {
    None: [{"id": f"a{i}", "transaction_time": "2026-08-17T14:00:00Z", "price": "1",
            "qty": "1", "side": "buy", "symbol": "AAA", "order_id": "o",
            "type": "fill"} for i in range(100)],
    "a99": [{"id": "b1", "transaction_time": "2026-08-17T14:00:00Z", "price": "1",
             "qty": "1", "side": "buy", "symbol": "BBB", "order_id": "o",
             "type": "fill"}],
    "b1": [],
}
pedidos_alpaca = []


def _get_paginado(path, params=None, **k):
    token = (params or {}).get("page_token")
    pedidos_alpaca.append(token)
    return paginas_alpaca.get(token, [])


alp2._get = _get_paginado
ops_p = alp2.operaciones("2026-07-18", "2026-08-17")
check(len(ops_p) == 101, "Alpaca junta las dos paginas (100 + 1)", f"{len(ops_p)}")
check(pedidos_alpaca == [None, "a99"],
      "y pide la segunda con el id de la ultima fila, sin repetir la primera",
      f"{pedidos_alpaca}")

tas2 = object.__new__(TastytradeBroker)
tas2._account = "5W"
paginas_tasty = []


def _pedir_paginado(metodo, ruta, params=None, **k):
    off = (params or {}).get("page-offset", 0)
    paginas_tasty.append(off)
    if off > 1:
        return {"data": {"items": []}, "pagination": {"total-pages": 2}}
    return {"data": {"items": [
        {"transaction-type": "Trade", "action": "Buy to Open", "symbol": f"S{off}",
         "quantity": "1", "price": "1", "executed-at": "2026-08-13T15:00:00Z"}]},
        "pagination": {"total-pages": 2}}


tas2._pedir = _pedir_paginado
ops_tp = tas2.operaciones("2026-07-18", "2026-08-17")
check(len(ops_tp) == 2, "Tasty recorre sus dos paginas", f"{len(ops_tp)}")
check(paginas_tasty == [0, 1], "y para cuando dice que no hay mas (no gira al vacio)",
      f"{paginas_tasty}")

print("\n=== 4. El archivo: ordenado, con titulos, y sin inventar ceros ===")
ruta = os.path.join(carpeta, "ops.csv")
guardar_operaciones(ops_a + list(ops_t.values()) + ops_y, ruta)
with open(ruta, encoding="utf-8-sig", newline="") as f:
    leido = list(csv.reader(f, delimiter=";"))
check(leido[0][0] == "Fecha y hora (NY)", "titulos en castellano", f"{leido[0][:3]}")
check(len(leido) == 5, "una fila por operacion", f"{len(leido)} con el titulo")
fechas = [f[0] for f in leido[1:]]
check(fechas == sorted(fechas), "de la mas vieja a la mas nueva", f"{fechas}")
fila_alpaca = [f for f in leido[1:] if f[1] == "BCARU"][0]
col = {t: i for i, (_, t) in enumerate(COLUMNAS)}
check(fila_alpaca[col["Comision"]] == "" and fila_alpaca[col["Tasas"]] == "",
      "lo que el broker no informa queda VACIO, no en 0",
      f"comision='{fila_alpaca[col['Comision']]}'")

print("\n=== 5. El resumen que va al registro ===")
r = resumen(ops_a + list(ops_t.values()) + ops_y)
check("4 operacion" in r and "2026-08-13" in r and "2026-08-17" in r,
      "cuenta las operaciones y dice de cuando a cuando", r)
check(resumen([]) == "no hay operaciones en esas fechas",
      "y si no hay nada lo dice claro")

print("\n=== 6. Con el perfil hibrido, el historial es del que EJECUTA ===")
from tradingbot.connectors.hibrido import BrokerHibrido                # noqa: E402


class BrokerOpera(FakeBroker):
    def operaciones(self, desde, hasta):
        return [{"symbol": "OPERA"}]


class BrokerDatos(FakeBroker):
    def operaciones(self, desde, hasta):
        return [{"symbol": "DATOS"}]


hib = BrokerHibrido(BrokerOpera(), BrokerDatos())
check([f["symbol"] for f in hib.operaciones("2026-01-01", "2026-01-31")] == ["OPERA"],
      "trae lo del broker donde se opera, no el que da los precios")
check(FakeBroker().operaciones("2026-01-01", "2026-01-31") == [],
      "un broker que no lo implementa devuelve vacio (no explota)")

print("\n=== 7. El cuadro de fechas ===")
from PySide6.QtCore import QDate                                       # noqa: E402
from PySide6.QtWidgets import (                                        # noqa: E402
    QApplication,
    QHBoxLayout,
    QScrollArea,
)

from tradingbot.gui.operaciones_dialog import DialogoOperaciones       # noqa: E402

app = QApplication.instance() or QApplication([])
d = DialogoOperaciones()
desde, hasta = d.fechas()
check(len(desde) == 10 and desde < hasta,
      "arranca con el ultimo mes, en el formato que piden las APIs",
      f"{desde} -> {hasta}")
d._poner(7)
desde7, _ = d.fechas()
check(desde7 > desde, "los atajos mueven la fecha de inicio", f"{desde7}")

d.ed_desde.setDate(QDate.currentDate())
d.ed_hasta.setDate(QDate.currentDate().addDays(-10))
d.accept()
check(d.result() != DialogoOperaciones.Accepted,
      "con las fechas al reves NO deja seguir (si no, parece que no operaste nada)")
check(bool(d.lbl_aviso.text()), "y explica por que", d.lbl_aviso.text())

d.ed_hasta.setDate(QDate.currentDate())
d.accept()
check(d.result() == DialogoOperaciones.Accepted, "con las fechas bien, sigue")

print("\n=== 8. El boton esta en la pantalla ===")
from tradingbot.gui.control_panel import ControlPanel                  # noqa: E402

panel = ControlPanel()
check(hasattr(panel, "btn_operaciones"), "el boton existe")
check(panel.btn_operaciones.parentWidget() is not None,
      "y esta puesto en la pantalla, no suelto")

# que ENTRE: si la fila del registro pide mas de lo que el panel ya reserva,
# el panel se ensancha y le come lugar al ladder
fila = None
for lay in panel.findChildren(QHBoxLayout):
    for i in range(lay.count()):
        if lay.itemAt(i).widget() is panel.btn_operaciones:
            fila = lay
reserva = panel.findChildren(QScrollArea)[0].widget().minimumSizeHint().width()
if app.platformName() == "offscreen":
    print("  (salteo la medida de ancho: la letra de la pantalla de mentira no es "
          "la de Windows y da cualquier numero)")
else:
    check(fila is not None and fila.minimumSize().width() <= reserva,
          "la fila del registro entra sin ensanchar el panel",
          f"pide {fila.minimumSize().width() if fila else 0}, reservado {reserva}")

print()
if fallos:
    print(f"PROBLEMAS: {len(fallos)}")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("OK: el historial sale completo, en hora de NY, y con las mismas columnas "
      "en los tres brokers.")
