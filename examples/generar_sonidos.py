"""
Genera los dos archivos de sonido de la app. Se corre UNA vez; los .wav quedan
guardados en el repo, asi que suenan IGUAL en todas las computadoras.

Por que propios y no los de Windows: antes usabamos los sonidos del sistema, que
dependen del esquema que tenga cada PC. Resultado: en una maquina sonaban de una
forma, en otra distinto, y en una tercera casi no se oian. Con archivos propios
controlamos exactamente que se escucha y con cuanto volumen.

    python examples/generar_sonidos.py
"""
from __future__ import annotations

import math
import os
import struct
import sys
import wave

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, "tradingbot", "gui", "audio")
HZ = 44100


def _tono(frecuencia: float, segundos: float, volumen: float) -> list[float]:
    """Un tono con entrada y salida suaves (sin el 'clic' de cortar de golpe)."""
    n = int(HZ * segundos)
    borde = max(1, int(HZ * 0.006))          # 6 ms de subida y bajada
    muestras = []
    for i in range(n):
        v = math.sin(2 * math.pi * frecuencia * i / HZ)
        if i < borde:                        # entrada
            v *= i / borde
        elif i > n - borde:                  # salida
            v *= (n - i) / borde
        muestras.append(v * volumen)
    return muestras


def _silencio(segundos: float) -> list[float]:
    return [0.0] * int(HZ * segundos)


def _guardar(nombre: str, muestras: list[float]) -> str:
    os.makedirs(CARPETA, exist_ok=True)
    ruta = os.path.join(CARPETA, nombre)
    with wave.open(ruta, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(HZ)
        datos = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, m)) * 32767)) for m in muestras
        )
        w.writeframes(datos)
    return ruta


def main() -> int:
    # ---- ORDEN EJECUTADA: corto y agradable, no molesta si se repite ----
    # dos notas ascendentes (La -> Mi), volumen medio
    ejecucion = _tono(880, 0.075, 0.55) + _tono(1320, 0.11, 0.55)

    # ---- ALARMA DEL GUARDIA: tiene que OIRSE. Es la de seguridad ----
    # tres pulsos alternados, volumen alto (0.92 de la escala)
    alerta = []
    for _ in range(3):
        alerta += _tono(1245, 0.13, 0.92)     # agudo
        alerta += _tono(933, 0.13, 0.92)      # un poco mas grave
        alerta += _silencio(0.05)

    for nombre, muestras in (("ejecucion.wav", ejecucion), ("alerta.wav", alerta)):
        ruta = _guardar(nombre, muestras)
        dur = len(muestras) / HZ
        pico = max(abs(m) for m in muestras)
        print(f"  {nombre:15} {dur:.2f} s   volumen pico {pico*100:.0f}%   -> {ruta}")

    print("\nOK: sonidos generados. Para escucharlos: python examples/probar_sonidos.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
