"""
Que el recolector de basura de Python no tumbe la app.

EL PROBLEMA (choque capturado el 14/08/2026, cuenta real de Alpaca):

    Windows fatal exception: access violation
    Current thread ...:
      Garbage-collecting                                  <-- aca
      File "<string>", line 2 in __init__
      File "...connectors/alpaca.py", line 99 in _parse_order_dict
      File "...gui/market_worker.py", line 84 in run

Python corre su recolector **automaticamente**, y lo dispara el hilo que en ese
momento este pidiendo memoria. Si ese hilo es uno de trabajo (el monitoreo, el
ladder, un streaming) y en la limpieza le toca liberar un objeto de Qt, el
destructor en C++ de ese objeto **tiene que correr en el hilo de la pantalla**.
Corriendo en otro, el proceso muere de golpe: violacion de acceso, sin traza de
Python, la ventana desaparece sin decir nada.

Es exactamente la falla que Mariano ya habia documentado en su propia app.

LA SOLUCION, en dos partes:

 1. **Apagar el recolector automatico.** Asi ningun hilo de trabajo lo dispara
    nunca. Ojo: esto NO desactiva la liberacion normal de memoria, que en Python
    es por conteo de referencias y sigue funcionando igual. El recolector solo se
    ocupa de los CICLOS (objetos que se apuntan entre si).

 2. **Limpiarlos nosotros, desde el hilo de la pantalla.** Un temporizador de Qt
    llama a la limpieza cada tanto. Como los temporizadores de Qt corren en el
    hilo de la pantalla, ahi liberar un objeto de Qt es seguro.

Asi no se pierde la limpieza de memoria: solo se elige QUIEN y CUANDO la hace.

Por que no alcanzaba con apagarlo y listo (que es lo que hizo Mariano): sin la
segunda parte, los ciclos no se liberan nunca y en una sesion larga la memoria
crece. Con el temporizador, se limpian igual que antes.
"""
from __future__ import annotations

import gc

from PySide6.QtCore import QObject, QTimer

# Cada cuanto se limpia, en milisegundos. 20 segundos: lo bastante seguido como
# para que no se acumule nada en una rueda entera, y lo bastante espaciado como
# para que no se note (una limpieza tipica es de milisegundos).
INTERVALO_MS = 20_000

_timer: QTimer | None = None
_pasadas = 0


def proteger(padre: QObject | None = None) -> None:
    """Apaga el recolector automatico y programa la limpieza en el hilo de la
    pantalla. Se llama UNA vez, al arrancar, ANTES de crear los hilos."""
    global _timer
    gc.disable()
    try:
        # Todo lo que existe al arrancar (modulos, clases, la ventana) es de larga
        # vida: se lo saca de la vista del recolector para que cada limpieza mire
        # solo lo nuevo y sea mas barata.
        gc.freeze()
    except AttributeError:      # por si algun dia corre en un Python sin freeze
        pass
    if _timer is None:
        _timer = QTimer(padre)
        _timer.setInterval(INTERVALO_MS)
        _timer.timeout.connect(_limpiar)
        _timer.start()


def _limpiar() -> None:
    global _pasadas
    _pasadas += 1
    gc.collect()


def esta_protegido() -> bool:
    """Para las pruebas: el recolector automatico esta apagado?"""
    return not gc.isenabled()


def pasadas() -> int:
    """Para las pruebas: cuantas limpiezas se hicieron."""
    return _pasadas
