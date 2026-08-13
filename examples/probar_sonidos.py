"""
Prueba los sonidos de la app EN ESTA COMPUTADORA. Correlo con auriculares/parlantes.

Para que sirve: si la alarma del guardia no se oye, esto dice DONDE esta el
problema. Prueba cada camino por separado y te va avisando que tendrias que estar
escuchando. Al final imprime un resumen para pasarle al asistente.

    python examples/probar_sonidos.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    print("=" * 66)
    print("PRUEBA DE SONIDOS - subi el volumen y escucha")
    print("=" * 66)
    resultados = {}

    # ---------- 1) sonido del sistema ----------
    print("\n1) SONIDO DEL SISTEMA (el que usa el esquema de Windows)")
    print("   ... deberias escuchar DOS sonidos, uno tras otro")
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_OK)
        time.sleep(1.5)
        winsound.MessageBeep(winsound.MB_ICONHAND)
        time.sleep(1.5)
        resultados["sonido del sistema"] = "se ejecuto sin error"
    except Exception as e:  # noqa: BLE001
        resultados["sonido del sistema"] = f"FALLO: {e}"
        print(f"   *** fallo: {e}")

    # ---------- 2) tono propio ----------
    print("\n2) TONO PROPIO (NO depende del esquema de Windows)")
    print("   ... deberias escuchar dos pitidos agudos")
    try:
        import winsound
        winsound.Beep(1200, 220)
        time.sleep(0.1)
        winsound.Beep(1200, 220)
        resultados["tono propio"] = "se ejecuto sin error"
    except Exception as e:  # noqa: BLE001
        resultados["tono propio"] = f"FALLO: {e}"
        print(f"   *** fallo: {e}")
    time.sleep(1)

    # ---------- 3) los de la app ----------
    print("\n3) LOS SONIDOS DE LA APP, tal cual los toca")
    try:
        from tradingbot.gui.sonidos import sonar_alerta, sonar_ejecucion
        print("   ... sonido de ORDEN EJECUTADA")
        sonar_ejecucion()
        time.sleep(2)
        print("   ... ALARMA DEL GUARDIA (la importante)")
        sonar_alerta()
        time.sleep(2.5)
        resultados["sonidos de la app"] = "se ejecutaron sin error"
    except Exception as e:  # noqa: BLE001
        resultados["sonidos de la app"] = f"FALLO: {e}"
        print(f"   *** fallo: {e}")

    # ---------- 4) que dice Windows ----------
    print("\n4) CONFIGURACION DE WINDOWS EN ESTA PC")
    try:
        import winreg
        for evento in (".Default", "SystemHand"):
            ruta = rf"AppEvents\Schemes\Apps\.Default\{evento}\.Current"
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ruta) as k:
                    valor = winreg.QueryValueEx(k, "")[0]
            except OSError:
                valor = "(no existe)"
            existe = os.path.exists(valor) if valor and valor != "(no existe)" else False
            estado = "OK" if existe else "SIN ARCHIVO -> NO SUENA"
            print(f"   {evento:14} = {valor or '(vacio)'}   [{estado}]")
            resultados[f"esquema {evento}"] = f"{valor or '(vacio)'} [{estado}]"
    except Exception as e:  # noqa: BLE001
        print(f"   no pude leer la configuracion: {e}")

    print("\n" + "=" * 66)
    print("RESUMEN (copiale esto al asistente):")
    for k, v in resultados.items():
        print(f"   {k:22}: {v}")
    print("=" * 66)
    print("\nDECIME CUALES ESCUCHASTE:")
    print("   - si NO se oyo NINGUNO      -> la app esta silenciada en el mezclador")
    print("     de volumen de Windows, o el sonido sale por otro dispositivo")
    print("   - si se oyo el 2 pero no el 1 -> el esquema de sonidos esta apagado")
    print("     (ya lo cubrimos: la alarma ahora toca los dos caminos)")
    print("   - si se oyo todo             -> el problema esta en CUANDO los toca")
    print("     la app, no en el sonido; avisame y sigo por ahi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
