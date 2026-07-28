"""
Punto de entrada de la app grafica.

Para correrla:  python examples/correr_app.py
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .main_window import MainWindow
from .perfiles import perfiles_disponibles
from .startup import StartupDialog
from ..registro import configurar_registro, log, nombre_maquina, ruta_log, version_app


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    perfiles = perfiles_disponibles()
    if not perfiles:
        QMessageBox.critical(
            None,
            "Sin credenciales",
            "No encontre ninguna cuenta configurada en config/credentials.ini "
            "(Tradier sandbox y/o Alpaca paper). Carga al menos una y volve a abrir.",
        )
        return 1

    inicio = StartupDialog(perfiles)
    if not inicio.exec():  # el usuario cerro/cancelo el dialogo
        return 0
    perfil = inicio.perfil_elegido()

    # log separado por PC y por broker (asi dos instancias/maquinas no se pisan)
    configurar_registro(sufijo=perfil.id)
    log(f"=== App iniciada: {perfil.broker_nombre} / {perfil.cuenta_texto} ===")
    # PC y version del codigo: imprescindible para diagnosticar un log de OTRA
    # maquina (saber si tenia las ultimas correcciones o una version vieja)
    log(f"    PC: {nombre_maquina()}  |  version del codigo: {version_app()}")

    win = MainWindow(perfil)
    win.show()
    codigo = app.exec()
    log(f"=== App cerrada normalmente (codigo {codigo}) ===")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
