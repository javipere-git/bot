"""
Sonidos de la app. Dos sonidos DISTINTOS:
  - sonar_ejecucion(): cuando se llena una orden (controlado por el check "Sonido al ejecutar").
  - sonar_alerta():    cuando el bot pasa a manual o se detiene (alerta de seguridad).

Sin archivos: usa los sonidos del sistema (Windows). Si no hay audio, no falla.
"""
from __future__ import annotations


def sonar_ejecucion() -> None:
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_OK)          # sonido "OK" del sistema
    except Exception:
        _beep_qt()


def sonar_alerta() -> None:
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONHAND)    # sonido "critico" del sistema
    except Exception:
        _beep_qt()


def _beep_qt() -> None:
    try:
        from PySide6.QtWidgets import QApplication
        QApplication.beep()
    except Exception:
        pass
