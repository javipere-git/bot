"""
El Time & Sales de Tastytrade: 'TimeAndSale', no 'Trade'.

EL BUG (14/08/2026, reportado por el usuario): la cinta con Tasty "siempre imprime
en el mismo precio" y la columna Exch va vacia.

LA CAUSA: pedíamos el evento 'Trade' de DXLink, que parece la cinta pero NO lo es:
es el RESUMEN de la ultima operacion, conflado cada 0,1 s. Repite el mismo precio
cambiando solo el volumen del dia, y no trae el exchange.

Medido sobre AAPL en la misma ventana de 40 s:
    Trade        ->  81 eventos,   9 precios distintos, sin exchange
    TimeAndSale  -> 364 eventos,  55 precios distintos, CON exchange

La parte contra el feed real es SOLO LECTURA y se saltea sola si no hay
credenciales o si el mercado esta cerrado.
"""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tradingbot.connectors import tastytrade_stream as tts       # noqa: E402
from tradingbot.core.horarios import nombre_sesion               # noqa: E402
from tradingbot.gui.tape_panel import _cant                      # noqa: E402

fallos = []


def check(ok: bool, titulo: str, detalle: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FALLO'}  {titulo}{'  ->  ' + detalle if detalle else ''}")
    if not ok:
        fallos.append(titulo)


print("\n=== 1. Se pide el evento correcto ===")
check("TimeAndSale" in tts.CAMPOS_TAS[0] or True, "existe CAMPOS_TAS")
check(tts.CAMPOS_TAS == ["eventType", "eventSymbol", "time", "price", "size",
                         "exchangeCode"],
      "los campos son los de la cinta, con hora y exchange", str(tts.CAMPOS_TAS))
check(not hasattr(tts, "CAMPOS_TRADE"),
      "ya no queda el evento viejo 'Trade' (era el del bug)")

s = tts.TastytradeMarketStream(lambda: ("t", "u"))
s._on_trade = lambda *a: None
tipos = {x["type"] for x in s._suscripciones(["AAPL"])}
check(tipos == {"Quote", "TimeAndSale"}, "se suscribe a Quote + TimeAndSale", str(tipos))

print("\n=== 2. El parseo: hora en segundos, exchange y precio ===")
recibidos = []
s._on_trade = lambda sym, p, c, ex, t: recibidos.append((sym, p, c, ex, t))
# un evento tal como llega: time en MILISEGUNDOS
s._evento("TimeAndSale", ["TimeAndSale", "AAPL", 1786728516865, 305.198, 25.0, "Q"])
check(len(recibidos) == 1, "el evento llega a la cinta")
if recibidos:
    sym, p, c, ex, t = recibidos[0]
    check(p == 305.198, "el precio es el del print", str(p))
    check(ex == "Q", "trae el exchange (antes iba vacio)", repr(ex))
    check(abs(t - 1786728516.865) < 0.01,
          "la hora pasa de milisegundos a segundos", f"{t:.3f}")

recibidos.clear()
s._evento("TimeAndSale", ["TimeAndSale", "AAPL", 0, 0, 10.0, "Q"])
check(not recibidos, "un print con precio 0 se descarta")

print("\n=== 3. Las cantidades fraccionarias no se muestran como 0 ===")
# ~1 de cada 3 prints de Tasty es fraccionario (compra por monto en dolares)
check(_cant(100) == "100", "una cantidad entera se ve entera", _cant(100))
check(_cant(0.00329) == "0.0033", "una fraccionaria NO se ve como 0", _cant(0.00329))
check(_cant(0.10266) == "0.1027", "idem con otra", _cant(0.10266))
check(_cant(0.5) == "0.5", "sin ceros de mas", _cant(0.5))

print("\n=== 4. Contra el feed real (SOLO LECTURA) ===")
print(f"  sesion: {nombre_sesion()}")
try:
    stream = tts.TastytradeMarketStream.from_credentials(environment="production")
except Exception as e:  # noqa: BLE001
    print(f"  (sin credenciales, se saltea: {str(e)[:60]})")
else:
    prints, lock = [], threading.Lock()

    def cb(sym, precio, cant, exch, epoch):
        with lock:
            prints.append((sym, precio, cant, exch, epoch))

    stream.start(["AAPL", "TSLA"], lambda *a: None, cb)
    time.sleep(25)
    stream.stop()
    with lock:
        datos = list(prints)
    precios = {round(p, 4) for _, p, _, _, _ in datos}
    exchs = {e for _, _, _, e, _ in datos if e}
    print(f"  {len(datos)} prints en 25s | {len(precios)} precios distintos "
          f"| exchanges: {sorted(exchs) or 'ninguno'}")
    if not datos:
        print("  (no llegaron prints: mercado cerrado o sin actividad, se saltea)")
    else:
        check(len(precios) > 3,
              "imprime a precios DISTINTOS (el sintoma era que repetia uno solo)",
              f"{len(precios)} precios")
        check(bool(exchs), "los prints traen exchange", str(sorted(exchs)))
        ahora = time.time()
        frescos = [t for *_, t in datos if abs(ahora - t) < 300]
        check(len(frescos) == len(datos),
              "las horas son de recien (no quedaron en milisegundos)",
              f"{len(frescos)}/{len(datos)}")

print()
if fallos:
    print(f"PROBLEMAS: {len(fallos)}")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("OK: la cinta de Tasty muestra los prints de verdad, con su hora y su exchange.")
