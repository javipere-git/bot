"""
Sonidos de la app. Dos sonidos DISTINTOS:
  - sonar_ejecucion(): cuando se llena una orden (controlado por el check "Sonido al ejecutar").
  - sonar_alerta():    cuando el bot pasa a manual o se detiene (alerta de seguridad).

POR QUE NO ALCANZA CON EL SONIDO DEL SISTEMA (aprendido el 13/08/2026, con la
alarma del guardia que no se oia): `winsound.MessageBeep` reproduce el sonido que
el usuario tenga asignado en el ESQUEMA DE SONIDOS de Windows. Si ese esquema
esta en "Sin sonidos", o el evento quedo sin archivo, o la app esta silenciada en
el mezclador, NO SUENA NADA y ademas falla en silencio (devuelve exito igual).

Por eso, para la ALERTA -que es de seguridad y tiene que oirse si o si- se hacen
las dos cosas: el sonido del sistema Y un tono generado por nosotros, que no
depende de ningun esquema. Mejor que suene dos veces a que no suene.

El tono se toca en un hilo aparte: `winsound.Beep` es BLOQUEANTE y, llamado desde
la pantalla, la congelaria durante toda su duracion.
"""
from __future__ import annotations

import threading


def _tono(frecuencia: int, milisegundos: int, repeticiones: int = 1) -> bool:
    """Tono propio, en un hilo aparte. No depende del esquema de sonidos."""
    try:
        import winsound
    except Exception:  # noqa: BLE001
        return False

    def _tocar() -> None:
        try:
            for i in range(repeticiones):
                winsound.Beep(frecuencia, milisegundos)
                if i + 1 < repeticiones:
                    import time
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
    """Se lleno una orden. Un solo sonido, discreto."""
    try:
        import winsound
        if _sonido_del_sistema(winsound.MB_OK):
            return
    except Exception:  # noqa: BLE001
        pass
    if not _tono(880, 120):
        _beep_qt()


def sonar_alerta() -> None:
    """ALERTA DE SEGURIDAD (guardia disparado / bot detenido).

    Va por los DOS caminos a proposito: si el esquema de sonidos de Windows esta
    apagado, el sonido del sistema no se oye y el tono propio salva la alarma.
    """
    sono = False
    try:
        import winsound
        sono = _sonido_del_sistema(winsound.MB_ICONHAND)
    except Exception:  # noqa: BLE001
        pass
    # el tono va SIEMPRE: es la alarma, tiene que oirse
    if not _tono(1200, 220, repeticiones=2) and not sono:
        _beep_qt()


def _beep_qt() -> None:
    try:
        from PySide6.QtWidgets import QApplication
        QApplication.beep()
    except Exception:  # noqa: BLE001
        pass
