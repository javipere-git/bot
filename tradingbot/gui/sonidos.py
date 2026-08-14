"""
Sonidos de la app. Dos sonidos DISTINTOS:
  - sonar_ejecucion(): cuando se llena una orden (controlado por el check "Sonido al ejecutar").
  - sonar_alerta():    cuando el bot pasa a manual o se detiene (alerta de seguridad).

USA ARCHIVOS PROPIOS (gui/audio/*.wav), no los sonidos de Windows.

Por que (aprendido usando la app en tres computadoras distintas): antes se usaba
`winsound.MessageBeep`, que reproduce el sonido que cada PC tenga asignado en su
ESQUEMA DE SONIDOS. Resultado: en una maquina sonaba de una forma, en otra
distinto, y en una tercera tan bajo que casi no se oia. Y si el esquema esta
apagado o el evento quedo sin archivo, NO SUENA NADA y encima Windows devuelve
exito, asi que falla en silencio.

Con archivos propios suena IGUAL en todas las maquinas y controlamos el volumen.
La alarma del guardia se genera al 92% de la escala justamente para que se oiga;
la de ejecucion al 55%, que se repite seguido y no tiene que molestar.

Los .wav se generan con examples/generar_sonidos.py y viven en el repo.

RESPALDOS, por si el archivo no estuviera (instalacion a medias) o PlaySound
fallara: se cae al tono generado, y despues al sonido del sistema.
"""
from __future__ import annotations

import os
import threading

_CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
ARCHIVO_EJECUCION = os.path.join(_CARPETA, "ejecucion.wav")
ARCHIVO_ALERTA = os.path.join(_CARPETA, "alerta.wav")


def _tocar_archivo(ruta: str) -> bool:
    """Toca un .wav sin bloquear la pantalla. True si salio."""
    if not os.path.exists(ruta):
        return False
    try:
        import winsound
        # ASYNC = vuelve al instante; NODEFAULT = si falla, que no toque el "ding"
        # generico de Windows (quedaria un sonido que no es el nuestro)
        winsound.PlaySound(ruta, winsound.SND_FILENAME | winsound.SND_ASYNC
                           | winsound.SND_NODEFAULT)
        return True
    except Exception:  # noqa: BLE001
        return False


def _tono(frecuencia: int, milisegundos: int, repeticiones: int = 1) -> bool:
    """Respaldo: tono generado en el momento, en un hilo aparte.
    (winsound.Beep es BLOQUEANTE: llamado desde la pantalla la congelaria)."""
    try:
        import winsound
    except Exception:  # noqa: BLE001
        return False

    def _tocar() -> None:
        try:
            import time
            for i in range(repeticiones):
                winsound.Beep(frecuencia, milisegundos)
                if i + 1 < repeticiones:
                    time.sleep(0.06)
        except Exception:  # noqa: BLE001
            pass

    try:
        threading.Thread(target=_tocar, daemon=True).start()
        return True
    except Exception:  # noqa: BLE001
        return False


def _sonido_del_sistema(tipo: int) -> bool:
    try:
        import winsound
        winsound.MessageBeep(tipo)
        return True
    except Exception:  # noqa: BLE001
        return False


def sonar_ejecucion() -> None:
    """Se lleno una orden. Corto y discreto: se repite seguido."""
    if _tocar_archivo(ARCHIVO_EJECUCION):
        return
    if _tono(880, 120):                      # respaldo 1
        return
    try:                                     # respaldo 2
        import winsound
        _sonido_del_sistema(winsound.MB_OK)
    except Exception:  # noqa: BLE001
        _beep_qt()


def sonar_alerta() -> None:
    """ALERTA DE SEGURIDAD (guardia disparado / bot detenido). Tiene que oirse."""
    if _tocar_archivo(ARCHIVO_ALERTA):
        return
    if _tono(1200, 220, repeticiones=2):     # respaldo 1
        return
    try:                                     # respaldo 2
        import winsound
        _sonido_del_sistema(winsound.MB_ICONHAND)
    except Exception:  # noqa: BLE001
        _beep_qt()


def _beep_qt() -> None:
    try:
        from PySide6.QtWidgets import QApplication
        QApplication.beep()
    except Exception:  # noqa: BLE001
        pass
