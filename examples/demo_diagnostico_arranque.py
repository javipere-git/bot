"""
Las dos redes de diagnostico funcionan. No toca dinero ni red.

POR QUE EXISTEN (dos casos reales que no dejaban NINGUNA evidencia):

  1. CHOQUE NATIVO. El 12/08/2026 la app murio con una violacion de acceso
     (0xc0000005). No es un error de Python: el proceso muere de golpe y el
     capturador de errores de Python no llega a correr. El registro no decia nada;
     la causa la dio el visor de eventos de Windows. Ahora `faulthandler` deja el
     detalle en un archivo aparte.

  2. LA APP NO ABRE. Se lanza con pythonw (sin consola) y el registro recien se
     configura DESPUES de elegir el broker. Si algo falla en el medio, el error va
     a una salida que no existe: la ventana de login desaparece, no se abre nada y
     no queda ni una linea. Ahora cada paso del arranque queda en
     'ultimo_arranque.log'.

    python examples/demo_diagnostico_arranque.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tradingbot.registro import (  # noqa: E402
    activar_faulthandler,
    anotar_falla_de_arranque,
    rastro_arranque,
    ruta_choques,
)


def main() -> int:
    checks = {}

    # ---------- 1) el rastro del arranque ----------
    print("=== 1) rastro del arranque ===")
    rastro_arranque("1. arrancando")
    rastro_arranque("2. ventana grafica lista")
    ruta = os.path.join(RAIZ, "ultimo_arranque.log")
    contenido = open(ruta, encoding="utf-8").read() if os.path.exists(ruta) else ""
    print(f"  archivo: {ruta}")
    print("  " + contenido.replace("\n", "\n  ").strip())
    checks["el rastro anota los pasos"] = "1. arrancando" in contenido and \
        "2. ventana grafica lista" in contenido

    # se pisa en cada corrida (solo interesa el ultimo arranque)
    import tradingbot.registro as reg
    reg._RUTA_ARRANQUE = None
    rastro_arranque("1. arranque NUEVO")
    contenido2 = open(ruta, encoding="utf-8").read()
    checks["cada arranque pisa al anterior"] = "ventana grafica" not in contenido2

    # ---------- 2) la falla de arranque queda anotada ----------
    print("\n=== 2) si la app no puede abrir ===")
    anotar_falla_de_arranque("Traceback simulado: algo exploto al crear la ventana")
    c = open(ruta, encoding="utf-8").read()
    checks["la falla de arranque se anota"] = "LA APP NO PUDO ABRIR" in c
    print("  " + [l for l in c.splitlines() if "NO PUDO ABRIR" in l][0])

    # ---------- 3) el capturador de choques arranca VACIO ----------
    print("\n=== 3) capturador de choques ===")
    activar_faulthandler(sufijo="demo_diagnostico")
    rc = ruta_choques("demo_diagnostico")
    vacio = os.path.exists(rc) and os.path.getsize(rc) == 0
    print(f"  archivo: {rc}")
    print(f"  arranca vacio: {vacio}  <- si tuviera contenido seria un choque REAL")
    checks["el archivo de choques arranca vacio"] = vacio

    # ---------- 4) LA PRUEBA DE FUEGO: provocar un choque nativo de verdad ----------
    # Se corre en otro proceso (este tiene que sobrevivir) y se comprueba que el
    # detalle quede escrito. Es exactamente lo que paso el 12/08.
    print("\n=== 4) choque nativo DE VERDAD (en otro proceso) ===")
    tmp = os.path.join(tempfile.gettempdir(), "choque_de_prueba.log")
    guion = (
        "import faulthandler, ctypes\n"
        f"f = open(r'{tmp}', 'w', encoding='utf-8')\n"
        "faulthandler.enable(file=f, all_threads=True)\n"
        "ctypes.string_at(0)\n"          # leer la direccion 0 = violacion de acceso
    )
    r = subprocess.run([sys.executable, "-c", guion], capture_output=True, timeout=60)
    detalle = open(tmp, encoding="utf-8").read() if os.path.exists(tmp) else ""
    print(f"  el proceso murio con codigo {r.returncode}")
    print("  quedo escrito:")
    for linea in detalle.strip().splitlines()[:4]:
        print("     ", linea)
    checks["un choque nativo REAL queda registrado"] = bool(detalle.strip())
    try:
        os.remove(tmp)
    except OSError:
        pass
    try:
        os.remove(rc)
    except OSError:
        pass

    print()
    for nombre, ok in checks.items():
        print(f"  {'OK ' if ok else '*** FALLO'} {nombre}")
    todo = all(checks.values())
    print("\nOK: la proxima caida va a dejar evidencia." if todo
          else "\n*** FALLO: el diagnostico no captura.")
    return 0 if todo else 1


if __name__ == "__main__":
    sys.exit(main())
