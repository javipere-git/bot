"""
Que el recolector de basura no corra dentro de un hilo de trabajo.

EL CHOQUE (capturado el 14/08/2026 en la cuenta real de Alpaca, con el ladder en
uso intenso):

    Windows fatal exception: access violation
    Current thread:
      Garbage-collecting
      File "<string>", line 2 in __init__
      File ".../connectors/alpaca.py", line 99 in _parse_order_dict
      File ".../gui/market_worker.py", line 84 in run

El recolector automatico lo dispara el hilo que pide memoria en ese momento. Si
es un hilo de trabajo y le toca liberar un objeto de Qt, el destructor en C++
corre fuera del hilo de la pantalla -> el proceso muere de golpe.

La prueba mide LO QUE IMPORTA: que un hilo de trabajo, pidiendo memoria a lo
loco (como hace el monitoreo al parsear cientos de ordenes), NO dispare ninguna
recoleccion; y que la limpieza igual ocurra, pero en el hilo de la pantalla.
"""
from __future__ import annotations

import gc
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QTimer                # noqa: E402
from PySide6.QtWidgets import QApplication                          # noqa: E402

from tradingbot.gui import recolector                               # noqa: E402

fallos = []


def check(ok: bool, titulo: str, detalle: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FALLO'}  {titulo}{'  ->  ' + detalle if detalle else ''}")
    if not ok:
        fallos.append(titulo)


app = QApplication.instance() or QApplication([])

# Espia: anota en QUE hilo corre cada recoleccion
hilo_gui = threading.get_ident()
recolecciones = []
gc.callbacks.append(
    lambda fase, info: recolecciones.append(threading.get_ident())
    if fase == "start" else None
)


def churn(vueltas=40_000):
    """Imita lo que hace el monitoreo: crear muchisimos objetos con ciclos, que es
    justo lo que dispara el recolector automatico."""
    for _ in range(vueltas):
        a = {}
        b = {"otro": a}
        a["otro"] = b          # ciclo: solo el recolector puede liberarlo


print("\n=== 1. SIN proteccion: el hilo de trabajo dispara la recoleccion ===")
gc.enable()
recolecciones.clear()
h = threading.Thread(target=churn, daemon=True)
h.start()
h.join()
en_worker = [t for t in recolecciones if t != hilo_gui]
check(len(en_worker) > 0,
      "se reproduce el problema: recolecta DENTRO del hilo de trabajo",
      f"{len(en_worker)} de {len(recolecciones)} recolecciones")

print("\n=== 2. CON proteccion: el hilo de trabajo ya no recolecta ===")
recolector.proteger(app)
check(recolector.esta_protegido(), "el recolector automatico quedo apagado")
recolecciones.clear()
h = threading.Thread(target=churn, daemon=True)
h.start()
h.join()
en_worker = [t for t in recolecciones if t != hilo_gui]
check(len(en_worker) == 0,
      "NINGUNA recoleccion en el hilo de trabajo (era la causa del choque)",
      f"{len(en_worker)} recolecciones en hilos de trabajo")

print("\n=== 3. Pero la memoria se sigue limpiando, en el hilo de la pantalla ===")
recolector.INTERVALO_MS = 200          # para no esperar 20 segundos en la prueba
recolector._timer.setInterval(200)
antes = recolector.pasadas()
recolecciones.clear()
churn(20_000)                          # basura acumulada, nadie la limpio todavia
fin = time.time() + 3
while time.time() < fin and recolector.pasadas() == antes:
    QCoreApplication.processEvents()
    time.sleep(0.02)
check(recolector.pasadas() > antes, "la limpieza programada corrio",
      f"{recolector.pasadas() - antes} pasada(s)")
check(all(t == hilo_gui for t in recolecciones),
      "y corrio EN EL HILO DE LA PANTALLA, que es donde es seguro",
      f"{len(recolecciones)} recoleccion(es), todas en la pantalla")

print("\n=== 4. La liberacion normal de memoria no se toca ===")
# Python libera por conteo de referencias; apagar el recolector NO afecta eso.
liberados = []


class Testigo:
    def __del__(self):
        liberados.append(1)


for _ in range(100):
    Testigo()                          # sin ciclo: se libera al instante
check(len(liberados) == 100,
      "los objetos sin ciclos se siguen liberando al instante",
      f"{len(liberados)}/100")

print()
if fallos:
    print(f"PROBLEMAS: {len(fallos)}")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("OK: el recolector ya no corre en hilos de trabajo, y la memoria se limpia igual.")
