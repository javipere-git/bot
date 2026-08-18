"""
Simbolos excluidos (dos listas) + catalogo del broker a Excel.

PARA QUE: el 14/08/2026 Tastytrade rechazo 85 ordenes en un dia. 24 eran de
simbolos que tiene BLOQUEADOS para abrir posicion (is-closing-only): nunca las
iba a aceptar, la vuelta entera fue al pedo. Mas las que uno quiere sacar a mano.

LO QUE SE VERIFICA (el valor esta en la SEPARACION de las dos listas):
 1. Ida y vuelta al archivo: lo que guardas es lo que lees.
 2. Renovar la del broker NO pisa las tuyas. Ese es todo el punto del cuadro
    dividido en dos: la del broker son cientos y cambian solas.
 3. El motor SALTEA los excluidos: no les pide ni la cotizacion.
 4. Si todo esta excluido, corta; no se queda dando vueltas al vacio.
 5. El catalogo se guarda con SI/NO, y lo que el broker NO informa queda VACIO
    (un "NO" ahi seria mentira).
 6. De todo el catalogo, las que van a la lista de excluidas son SOLO las
    bloqueadas.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# OJO: aca NO se fuerza la pantalla de mentira ('offscreen'). Esa usa una letra
# mucho mas ancha que la de Windows y desmiente cualquier medida de ancho: con
# ella los cuatro botones "no entran", y en la app de verdad entran de sobra.
# Ninguna ventana se muestra igual, asi que no aparece nada en pantalla.

from tradingbot.connectors.fake_broker import FakeBroker            # noqa: E402
from tradingbot.core import excluidas                               # noqa: E402
from tradingbot.core.catalogo import (                             # noqa: E402
    COLUMNAS as COLUMNAS_ESPERADAS,
    guardar_catalogo,
)
from tradingbot.core.config import EngineConfig, OffsetUnit, OrderConfig  # noqa: E402
from tradingbot.core.engine import BotEngine, Outcome               # noqa: E402
from tradingbot.core.models import Side                             # noqa: E402

fallos = []


def check(ok, titulo, detalle=""):
    print(f"  {'OK  ' if ok else 'FALLO'}  {titulo}{'  ->  ' + detalle if detalle else ''}")
    if not ok:
        fallos.append(titulo)


carpeta = tempfile.mkdtemp(prefix="excluidas_")
ruta = os.path.join(carpeta, "excluidas.txt")

print("\n=== 1. Ida y vuelta: lo que guardas es lo que lees ===")
excluidas.guardar([("Impuestos", ["aaa", "$bbb"]), ("Sin liquidez", ["ccc"])],
                  ["XXX", "YYY", "ZZZ"], ruta)
mias, broker = excluidas.leer(ruta)
por_nombre = dict(mias)
check(por_nombre["Impuestos"] == ["AAA", "BBB"],
      "vuelven en mayuscula y sin el $", f"{por_nombre['Impuestos']}")
check(por_nombre["Sin liquidez"] == ["CCC"], "y cada lista con lo suyo", f"{mias}")
check(broker == ["XXX", "YYY", "ZZZ"], "las del broker vuelven enteras", f"{broker}")
check(len(mias) == excluidas.CUANTAS_MIAS,
      "siempre vuelven los mismos cuadros, aunque esten vacios", f"{len(mias)}")

print("\n=== 1b. Cada simbolo sabe DE QUE lista salio ===")
todas = excluidas.todas(ruta)
check(set(todas) == {"AAA", "BBB", "CCC", "XXX", "YYY", "ZZZ"},
      "todas() junta todas las listas")
check(todas["AAA"] == "Impuestos" and todas["CCC"] == "Sin liquidez",
      "y dice de cual salio cada uno", f"{todas['AAA']} / {todas['CCC']}")
check(todas["XXX"] == "bloqueadas por el broker",
      "incluidas las del broker", f"{todas['XXX']}")
check("AAA" in todas and "ZZZ" in todas,
      "se sigue usando igual que antes: 'simbolo in excluidas'")

print("\n=== 2. Renovar la del broker NO toca las mias ===")
# esto es exactamente lo que hace el boton 'Traer del broker' + Guardar
mias_antes, _ = excluidas.leer(ruta)
excluidas.guardar(mias_antes, ["QQQ", "RRR"], ruta)
mias, broker = excluidas.leer(ruta)
check(dict(mias)["Impuestos"] == ["AAA", "BBB"],
      "las mias siguen ahi despues de renovar la otra", f"{dict(mias)['Impuestos']}")
check(broker == ["QQQ", "RRR"], "y la del broker quedo reemplazada, no sumada", f"{broker}")

# y al reves: cambiar una lista mia no borra ni las otras ni la del broker
mias2 = [("Impuestos", ["CCC"])] + mias_antes[1:]
excluidas.guardar(mias2, broker, ruta)
mias, broker = excluidas.leer(ruta)
check(dict(mias)["Impuestos"] == ["CCC"] and dict(mias)["Sin liquidez"] == ["CCC"],
      "editar una lista no toca las otras", f"{mias}")
check(broker == ["QQQ", "RRR"], "ni la del broker", f"{broker}")

print("\n=== 2b. Los nombres se pueden cambiar, y se guardan ===")
excluidas.guardar([("Me fue mal", ["AAA"]), ("", ["BBB"])], [], ruta)
mias, _ = excluidas.leer(ruta)
check(mias[0] == ("Me fue mal", ["AAA"]), "el nombre nuevo vuelve tal cual", f"{mias[0]}")
check(mias[1][0] and mias[1][1] == ["BBB"],
      "y una lista sin nombre igual se guarda, con uno puesto", f"{mias[1]}")
excluidas.guardar([("Con = y\nsaltos", ["AAA"])], [], ruta)
mias, _ = excluidas.leer(ruta)
check(mias[0][1] == ["AAA"] and "\n" not in mias[0][0] and "=" not in mias[0][0],
      "un nombre con caracteres raros no rompe el archivo", f"{mias[0]}")

print("\n=== 2c. Un archivo del formato viejo se sigue leyendo ===")
ruta_vieja = os.path.join(carpeta, "vieja.txt")
with open(ruta_vieja, "w", encoding="utf-8") as f:
    f.write("# Simbolos que el bot NO va a operar.\n"
            "# === MIAS (las excluis vos) ===\n"
            "TSLA\nGME\n\n"
            "# === DEL BROKER (bloqueadas para abrir) ===\n"
            "QNRX\n")
mias, broker = excluidas.leer(ruta_vieja)
check(dict(mias)[excluidas.NOMBRES_POR_DEFECTO[0]] == ["TSLA", "GME"],
      "lo que tenias cargado no se pierde: cae en el primer cuadro", f"{mias[0]}")
check(broker == ["QNRX"], "y la del broker se lee igual", f"{broker}")

print("\n=== 3. El motor saltea los excluidos sin pedirles ni la cotizacion ===")


class BrokerEspia(FakeBroker):
    def __init__(self):
        super().__init__()
        self.pedidos = []

    def get_quote(self, symbol):
        self.pedidos.append(symbol)
        return super().get_quote(symbol)


def armar(excl, ordenes_side=Side.BUY):
    br = BrokerEspia()
    for s in ("AAA", "BBB", "CCC"):
        br.set_quote(s, 100.00, 100.20, 300, 300, volume=1_000_000)
    cfg = EngineConfig(
        side=ordenes_side, quantity=10,
        order1=OrderConfig(10, OffsetUnit.PERCENT_SPREAD, 1.0),
        order2=None, excluidas=excl, loop_watchlist=False,
    )
    return br, BotEngine(br, cfg, log=lambda m: None)


br, motor = armar({"BBB"})
motor.run_watchlist(["AAA", "BBB", "CCC"])
check("BBB" not in br.pedidos, "al excluido no le pidio NI la cotizacion",
      f"pedidos: {sorted(set(br.pedidos))}")
check("AAA" in br.pedidos and "CCC" in br.pedidos, "y a los otros dos si los opero")
simbolos_operados = {o.symbol for o in br.get_orders()}
check("BBB" not in simbolos_operados, "no mando ninguna orden del excluido",
      f"opero {sorted(simbolos_operados)}")

# en minuscula tambien: la watchlist se pega de cualquier lado
br, motor = armar({"BBB"})
motor.run_watchlist(["aaa", "bbb"])
check([s.lower() for s in br.pedidos] == ["aaa"],
      "compara sin importar mayuscula/minuscula", f"pedidos: {br.pedidos}")

print("\n=== 3b. El registro dice de QUE lista salio cada salteado ===")
mensajes = []
br = BrokerEspia()
for s in ("AAA", "BBB", "CCC"):
    br.set_quote(s, 100.00, 100.20, 300, 300, volume=1_000_000)
cfg = EngineConfig(
    side=Side.BUY, quantity=10,
    order1=OrderConfig(10, OffsetUnit.PERCENT_SPREAD, 1.0),
    order2=None, loop_watchlist=False,
    excluidas={"BBB": "Impuestos", "CCC": "Sin liquidez"},
)
BotEngine(br, cfg, log=mensajes.append).run_watchlist(["AAA", "BBB", "CCC"])
aviso = next((m for m in mensajes if m.startswith("Excluidas:")), "")
check("Impuestos" in aviso and "Sin liquidez" in aviso and "BBB" in aviso,
      "el registro nombra la lista y los simbolos", aviso)

# y con un conjunto pelado (como lo pasaban los tests viejos) tampoco se rompe
mensajes.clear()
br2 = BrokerEspia()
br2.set_quote("AAA", 100.00, 100.20, 300, 300, volume=1_000_000)
cfg2 = EngineConfig(
    side=Side.BUY, quantity=10,
    order1=OrderConfig(10, OffsetUnit.PERCENT_SPREAD, 1.0),
    order2=None, loop_watchlist=False, excluidas={"BBB"},
)
BotEngine(br2, cfg2, log=mensajes.append).run_watchlist(["AAA", "BBB"])
aviso = next((m for m in mensajes if m.startswith("Excluidas:")), "")
check("BBB" in aviso, "con un conjunto pelado tambien anda (sin motivo)", aviso)

print("\n=== 4. Si esta TODO excluido, corta ===")
br, motor = armar({"AAA", "BBB"})
res = motor.run_watchlist(["AAA", "BBB"])
check(res == Outcome.STOPPED, "termina en STOPPED (no se cuelga en un bucle vacio)",
      f"{res}")
check(br.pedidos == [], "y no gasto ni una llamada", f"{br.pedidos}")

print("\n=== 5. El catalogo a Excel: SI/NO, y vacio lo que el broker no informa ===")
filas = [
    {"symbol": "AAA", "bloqueada": True, "operable": False, "prestable": False,
     "costo_prestamo": 12.5, "iliquida": True, "marca_fraude": False,
     "overnight_bloqueada": True, "mercado": "NASDAQ"},
    {"symbol": "BBB", "bloqueada": False, "operable": True, "prestable": True,
     "costo_prestamo": None, "iliquida": None, "marca_fraude": None,
     "overnight_bloqueada": False, "mercado": "NYSE"},
]
csv_ruta = os.path.join(carpeta, "catalogo.csv")
guardar_catalogo(filas, csv_ruta)
with open(csv_ruta, encoding="utf-8-sig", newline="") as f:
    leido = list(csv.reader(f, delimiter=";"))
check(leido[0][0] == "Simbolo" and "Bloqueada para abrir" in leido[0],
      "la primera fila son los titulos en castellano", f"{leido[0][:3]}")
check(len(leido) == 3, "una fila por simbolo", f"{len(leido)} filas con el titulo")
fila_a = dict(zip(leido[0], leido[1]))
check(fila_a["Bloqueada para abrir"] == "SI" and fila_a["Operable"] == "NO",
      "los si/no salen como SI y NO, no como True/False",
      f"{fila_a['Bloqueada para abrir']} / {fila_a['Operable']}")
check(fila_a["Costo prestamo %"] == "12.5", "el costo de prestamo sale como numero")
fila_b = dict(zip(leido[0], leido[2]))
check(fila_b["Iliquida"] == "" and fila_b["Costo prestamo %"] == "",
      "lo que el broker no informa queda VACIO (no 'NO')",
      f"iliquida='{fila_b['Iliquida']}'")
check(fila_b["Marca de fraude"] == "" and fila_b["Prestable (ETB)"] == "SI",
      "y los que si informa siguen bien")

print("\n=== 6. Del catalogo, a excluir van SOLO las bloqueadas ===")
# es el filtro que aplica el boton 'Traer del broker'
bloqueadas = [f["symbol"] for f in filas if f.get("bloqueada")]
check(bloqueadas == ["AAA"], "AAA (bloqueada) si, BBB (iliquida pero operable) no",
      f"{bloqueadas}")
# ojo con esto: iliquida y marca de fraude son el 45% y el 27% del mercado en
# Tasty. Si alguna vez se cuelan en el filtro, la watchlist queda vacia.
check(all(f["symbol"] != "BBB" for f in filas if f.get("bloqueada")),
      "una iliquida sin bloquear NO se excluye sola")

print("\n=== 7. Un broker que no tiene catalogo no rompe nada ===")
check(FakeBroker().catalogo() == [],
      "el que no lo implementa devuelve lista vacia (no explota)")

print("\n=== 8. Cada conector traduce SUS campos a las mismas columnas ===")
# Sin red: se les cambia el pedido HTTP por una respuesta de mentira. Lo que se
# mira es la TRADUCCION, que es donde se puede errar el campo.
from tradingbot.connectors.alpaca import AlpacaBroker              # noqa: E402
from tradingbot.connectors.tastytrade import TastytradeBroker      # noqa: E402

# cada simbolo de mentira tiene una combinacion DISTINTA de marcas: si estuvieran
# todas juntas, confundir un campo con otro pasaria desapercibido
tasty = object.__new__(TastytradeBroker)
tasty._sandbox = False          # aca se mira la traduccion, no de donde sale
paginas = [[
    {"symbol": "BLOQ", "is-closing-only": True, "active": True,
     "lendability": "Locate Required", "borrow-rate": "8.5",
     "is-illiquid": False, "is-fraud-risk": False, "listed-market": "NASDAQ"},
    {"symbol": "ILIQ", "is-closing-only": False, "active": True,
     "lendability": "Easy To Borrow", "borrow-rate": "0.0",
     "is-illiquid": True, "is-fraud-risk": False, "listed-market": "NYSE"},
    {"symbol": "SOSPE", "is-closing-only": False, "active": True,
     "lendability": "Easy To Borrow", "borrow-rate": "0.0",
     "is-illiquid": False, "is-fraud-risk": True, "listed-market": "NYSE"},
]]
tasty._pedir = lambda *a, **k: {"data": {"items": paginas.pop(0) if paginas else []}}
cat_t = {f["symbol"]: f for f in tasty.catalogo()}
check(cat_t["BLOQ"]["bloqueada"] is True and cat_t["ILIQ"]["bloqueada"] is False
      and cat_t["SOSPE"]["bloqueada"] is False,
      "Tasty: 'bloqueada' sale de is-closing-only, de ningun otro campo")
check(cat_t["ILIQ"]["prestable"] is True and cat_t["BLOQ"]["prestable"] is False,
      "Tasty: 'prestable' es lendability == Easy To Borrow")
check(cat_t["ILIQ"]["iliquida"] is True and cat_t["SOSPE"]["iliquida"] is False,
      "Tasty: iliquida no se mezcla con la marca de fraude")
check(cat_t["SOSPE"]["marca_fraude"] is True and cat_t["ILIQ"]["marca_fraude"] is False,
      "Tasty: la marca de fraude viaja, pero NO bloquea (es el 27% del mercado)")

print("\n=== 8b. El sandbox de Tasty no marca ninguna: la lista sale de produccion ===")
# Medido el 15/08/2026: el sandbox lista 24.802 instrumentos y NINGUNO bloqueado;
# produccion lista 13.194 con 394 bloqueadas. Sin este recurso el boton trae cero.
sand = object.__new__(TastytradeBroker)
sand._sandbox = True
sand._catalogo_crudo = lambda: [
    {"symbol": "INVENT", "bloqueada": False, "operable": True, "prestable": True,
     "costo_prestamo": None, "iliquida": False, "marca_fraude": False,
     "overnight_bloqueada": True, "mercado": "XNAS"},
]
prod_falso = object.__new__(TastytradeBroker)
prod_falso._catalogo_crudo = lambda: [
    {"symbol": "REALBLOQ", "bloqueada": True, "operable": True, "prestable": False,
     "costo_prestamo": "8.5", "iliquida": True, "marca_fraude": True,
     "overnight_bloqueada": True, "mercado": "XNAS"},
]
_orig_from = TastytradeBroker.from_credentials
TastytradeBroker.from_credentials = classmethod(lambda cls, environment="sandbox": prod_falso)
try:
    filas_s = sand.catalogo()
    check([f["symbol"] for f in filas_s] == ["REALBLOQ"],
          "en sandbox trae el catalogo de produccion (que si tiene bloqueadas)",
          f"{[f['symbol'] for f in filas_s]}")
    check(bool(sand.catalogo_origen) and "PRODUCCION" in sand.catalogo_origen,
          "y deja dicho de donde salio, para que se vea en el registro",
          f"{sand.catalogo_origen}")

    # si produccion no contesta (no hay credenciales), se queda con lo que tenia
    TastytradeBroker.from_credentials = classmethod(
        lambda cls, environment="sandbox": (_ for _ in ()).throw(RuntimeError("sin credenciales")))
    filas_s = sand.catalogo()
    check([f["symbol"] for f in filas_s] == ["INVENT"],
          "sin credenciales de produccion no revienta: devuelve lo del sandbox",
          f"{[f['symbol'] for f in filas_s]}")
    check(sand.catalogo_origen is None, "y no miente sobre el origen")

    # en produccion NO vuelve a pedirse a si misma
    prod = object.__new__(TastytradeBroker)
    prod._sandbox = False
    prod._catalogo_crudo = lambda: []
    check(prod.catalogo() == [], "en produccion no hay recurso a ningun lado")
finally:
    TastytradeBroker.from_credentials = _orig_from

alp = object.__new__(AlpacaBroker)
alp._get = lambda *a, **k: [
    # tradable y easy_to_borrow al reves a proposito, para que no se puedan confundir
    {"symbol": "NOOP", "tradable": False, "easy_to_borrow": True,
     "attributes": [], "exchange": "OTC"},
    {"symbol": "SOLODIA", "tradable": True, "easy_to_borrow": False,
     "attributes": ["overnight_halted"], "exchange": "NASDAQ"},
]
cat_a = {f["symbol"]: f for f in alp.catalogo()}
check(cat_a["NOOP"]["bloqueada"] is True and cat_a["SOLODIA"]["bloqueada"] is False,
      "Alpaca: 'bloqueada' sale de tradable=false")
check(cat_a["NOOP"]["prestable"] is True and cat_a["SOLODIA"]["prestable"] is False,
      "Alpaca: 'prestable' es easy_to_borrow, que es otra cosa")
check(cat_a["SOLODIA"]["overnight_bloqueada"] is True
      and cat_a["NOOP"]["overnight_bloqueada"] is False,
      "Alpaca: overnight_halted es SOLO la sesion nocturna, no bloquea el dia")
check(cat_a["NOOP"]["iliquida"] is None,
      "Alpaca: lo que no informa va None, no False", f"{cat_a['NOOP']['iliquida']}")
faltan = [c for c, _ in COLUMNAS_ESPERADAS if c not in cat_a["NOOP"] or c not in cat_t["BLOQ"]]
check(not faltan, "los dos conectores devuelven las MISMAS columnas", f"faltan {faltan}")

print("\n=== 9. Con el perfil hibrido, las bloqueadas son del broker donde se OPERA ===")
from tradingbot.connectors.hibrido import BrokerHibrido             # noqa: E402


class BrokerOpera(FakeBroker):
    def catalogo(self):
        return [{"symbol": "OPERA", "bloqueada": True}]


class BrokerDatos(FakeBroker):
    def catalogo(self):
        return [{"symbol": "DATOS", "bloqueada": True}]


hib = BrokerHibrido(BrokerOpera(), BrokerDatos())
check([f["symbol"] for f in hib.catalogo()] == ["OPERA"],
      "trae el catalogo del que EJECUTA, no el del que da los precios",
      f"{[f['symbol'] for f in hib.catalogo()]}")

print("\n=== 10. El cuadro de excluidas: dos cajas, y traer del broker llena una sola ===")
from PySide6.QtWidgets import (                                     # noqa: E402
    QApplication,
    QHBoxLayout,
    QScrollArea,
)

from tradingbot.gui.control_panel import ControlPanel               # noqa: E402
from tradingbot.gui.excluidas_dialog import DialogoExcluidas        # noqa: E402

app = QApplication.instance() or QApplication([])
excluidas.guardar([("Impuestos", ["MIA1"]), ("Sin liquidez", ["MIA2"])],
                  ["VIEJA1"], ruta)
dlg = DialogoExcluidas(ruta=ruta)
mias_ui, broker_ui = dlg.listas()
check(len(dlg.filas) == excluidas.CUANTAS_MIAS,
      f"hay {excluidas.CUANTAS_MIAS} cuadros para las tuyas", f"{len(dlg.filas)}")
check(dict(mias_ui)["Impuestos"] == ["MIA1"]
      and dict(mias_ui)["Sin liquidez"] == ["MIA2"] and broker_ui == ["VIEJA1"],
      "abre con cada lista en su caja", f"{mias_ui} / {broker_ui}")

dlg.poner_del_broker(["NUEVA1", "NUEVA2"])      # esto hace 'Traer del broker'
mias_ui, broker_ui = dlg.listas()
check(dict(mias_ui)["Impuestos"] == ["MIA1"]
      and dict(mias_ui)["Sin liquidez"] == ["MIA2"],
      "traer del broker NO toca ninguna de las tuyas (el punto del cuadro)",
      f"{mias_ui}")
check(broker_ui == ["NUEVA1", "NUEVA2"],
      "y reemplaza la del broker, no la suma a la vieja", f"{broker_ui}")

# cambiarle el nombre a una lista desde la pantalla
dlg.filas[0][0].setText("Impuestos 2027")
dlg.filas[0][1].setPlainText("mia1 mia9")
mias_ui, _ = dlg.listas()
check(mias_ui[0] == ("Impuestos 2027", ["MIA1", "MIA9"]),
      "el nombre y los simbolos se leen de la pantalla", f"{mias_ui[0]}")

panel = ControlPanel()
check(hasattr(panel, "btn_excluidas") and hasattr(panel, "btn_catalogo"),
      "los dos botones nuevos existen en el panel")



def fila_de(btn):
    """En que layout horizontal esta metido este boton. None = en ninguno (un
    boton que se creo pero nunca se agrego a la pantalla no tiene ni padre)."""
    padre = btn.parentWidget()
    if padre is None:
        return None
    for lay in padre.findChildren(QHBoxLayout):
        for i in range(lay.count()):
            if lay.itemAt(i).widget() is btn:
                return lay
    return None


filas = [fila_de(b) for b in (panel.btn_etb_cargar, panel.btn_etb_bajar,
                              panel.btn_excluidas, panel.btn_catalogo)]
check(filas[0] is not None and len(set(map(id, filas))) == 1,
      "los cuatro botones estan en la MISMA linea")
check(filas[0] is not None and filas[0].count() == 4,
      "esa linea quedo dividida en 4 (ni un boton suelto de mas)",
      f"{filas[0].count() if filas[0] else 0} lugares")

# Que ENTREN. Si un dia se les alarga el nombre, los ultimos quedan afuera del
# panel: invisibles y sin poder apretarlos (no hay barra horizontal). Se comparan
# contra el grupo MAS ANCHO de los OTROS: ese es el ancho que el panel iba a tener
# igual. Compararlos contra el panel entero no sirve de nada, porque la fila es
# parte del panel y lo estira: siempre daria que entra.
pide_la_fila = filas[0].minimumSize().width() if filas[0] else 0
contenido = panel.findChildren(QScrollArea)[0].widget().layout()
otros = []
for i in range(contenido.count()):
    g = contenido.itemAt(i).widget()
    if g is not None and not g.isAncestorOf(panel.btn_etb_cargar):
        otros.append(g.minimumSizeHint().width())
reserva_el_panel = max(otros)
if app.platformName() == "offscreen":
    print("  (salteo la medida de ancho: la letra de la pantalla de mentira no es "
          "la de Windows y da cualquier numero)")
else:
    check(pide_la_fila <= reserva_el_panel,
          "los cuatro entran en el ancho del panel, sin agrandarlo",
          f"la fila pide {pide_la_fila}, el panel ya reserva {reserva_el_panel}")
check(panel.traer_bloqueadas is None,
      "sin ventana principal el panel no sabe a quien preguntarle (y no revienta)")

print()
if fallos:
    print(f"PROBLEMAS: {len(fallos)}")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("OK: las dos listas viven separadas, el motor saltea, y el catalogo se lee en Excel.")
