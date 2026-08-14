"""
Punto de entrada de la app grafica.

Para correrla:  python examples/correr_app.py
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .main_window import MainWindow
from .perfiles import perfiles_disponibles
from .recolector import proteger as proteger_recolector
from .startup import StartupDialog
from ..registro import (
    activar_faulthandler,
    anotar_falla_de_arranque,
    configurar_registro,
    log,
    nombre_maquina,
    rastro_arranque,
    ruta_choques,
    ruta_log,
    version_app,
)


def main() -> int:
    """Red de seguridad del arranque.

    La app se abre con pythonw (sin consola): si algo falla antes de que exista el
    registro, el error se escribe en una salida que no existe y el proceso muere en
    silencio -la ventana de login desaparece y no se abre nada-. Paso varias veces
    y no dejaba NINGUNA evidencia. Ahora todo queda anotado en 'ultimo_arranque.log'.
    """
    try:
        return _main()
    except BaseException:  # noqa: BLE001  (tambien queremos ver un SystemExit raro)
        import traceback
        anotar_falla_de_arranque(traceback.format_exc())
        raise


def _main() -> int:
    rastro_arranque("1. arrancando")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    rastro_arranque("2. ventana grafica lista")

    perfiles = perfiles_disponibles()
    rastro_arranque(f"3. perfiles disponibles: {len(perfiles)}")
    if not perfiles:
        QMessageBox.critical(
            None,
            "Sin credenciales",
            "No encontre ninguna cuenta configurada en config/credentials.ini "
            "(Tradier sandbox y/o Alpaca paper). Carga al menos una y volve a abrir.",
        )
        return 1

    inicio = StartupDialog(perfiles)
    aceptado = bool(inicio.exec())
    rastro_arranque(f"4. eleccion de broker: {'ACEPTADA' if aceptado else 'cancelada'}")
    if not aceptado:  # el usuario cerro/cancelo el dialogo
        return 0
    perfil = inicio.perfil_elegido()
    rastro_arranque(f"5. perfil elegido: {perfil.id}")

    # log separado por PC y por broker (asi dos instancias/maquinas no se pisan)
    configurar_registro(sufijo=perfil.id)
    rastro_arranque("6. registro configurado")
    # y el capturador de CHOQUES NATIVOS (los que no dejan traza de Python)
    choque_previo = activar_faulthandler(sufijo=perfil.id)
    rastro_arranque("7. capturador de choques activo")

    log(f"=== App iniciada: {perfil.broker_nombre} / {perfil.cuenta_texto} ===")
    # PC y version del codigo: imprescindible para diagnosticar un log de OTRA
    # maquina (saber si tenia las ultimas correcciones o una version vieja)
    log(f"    PC: {nombre_maquina()}  |  version del codigo: {version_app()}")
    if choque_previo:
        # la corrida ANTERIOR murio de golpe: su detalle se copia aca, que es
        # donde lo vamos a buscar
        log("*** LA SESION ANTERIOR TERMINO CON UN CHOQUE. Detalle: ***\n"
            + choque_previo)
        log(f"*** (el archivo de choques es {ruta_choques(perfil.id)}) ***")

    # ANTES de crear la ventana y los hilos: que el recolector de basura no corra
    # nunca dentro de un hilo de trabajo (ver gui/recolector.py). Sin esto, la app
    # se cierra sola de golpe cada tanto, sin dejar traza.
    proteger_recolector(app)
    rastro_arranque("8. creando la ventana principal")
    win = MainWindow(perfil)
    rastro_arranque("9. ventana creada, mostrando")
    win.show()
    rastro_arranque("10. app abierta, todo OK")
    codigo = app.exec()
    log(f"=== App cerrada normalmente (codigo {codigo}) ===")
    rastro_arranque(f"11. cerrada normalmente (codigo {codigo})")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
