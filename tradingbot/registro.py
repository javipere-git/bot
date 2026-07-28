"""
Registro a archivo (log persistente) + captura de errores no atrapados.

Por que existe: cuando la app se cierra sola (crash), sin un archivo de registro
no queda NINGUNA evidencia de que paso (con el acceso directo no hay consola).

El archivo se llama 'registro_<PC>_<perfil>.log':
  - <PC>: el nombre de la computadora. Asi, si varias maquinas escriben en una
    carpeta compartida (ej. Google Drive), los logs NO se pisan y se sabe de cual
    vino cada uno.
  - <perfil>: el broker/cuenta (tradier_live, alpaca_paper...), para que dos
    instancias abiertas a la vez tampoco se pisen.
Rota solo: cuando pasa de ~2 MB arranca archivo nuevo y guarda los 3 anteriores.

Donde se guarda: por defecto en la carpeta del proyecto. Se puede mandar a una
carpeta sincronizada (Drive/OneDrive/Dropbox) poniendo en config/credentials.ini:

    [logs]
    carpeta = C:\\Users\\Casa\\Mi unidad\\bot-logs

Ademas engancha los errores NO atrapados (el tipo de error que voltea la app):
quedan escritos en el log con su detalle completo antes de que pase nada.
"""
from __future__ import annotations

import configparser
import logging
import os
import socket
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler

_LOGGER = logging.getLogger("tradingbot")


def _raiz() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def nombre_maquina() -> str:
    """Nombre de esta computadora, apto para usar en un nombre de archivo."""
    bruto = os.environ.get("COMPUTERNAME") or ""
    if not bruto:
        try:
            bruto = socket.gethostname()
        except Exception:  # noqa: BLE001
            bruto = "PC"
    limpio = "".join(c if (c.isalnum() or c in "-_") else "-" for c in bruto)
    return limpio[:20] or "PC"


def version_app() -> str:
    """Version del codigo que esta corriendo, leida de git (sin ejecutar git).

    Sirve para saber, mirando un log de otra maquina, si tenia las ultimas
    correcciones o una version vieja. Devuelve algo como 'main a1b2c3d'.
    Si el proyecto no esta en git todavia, devuelve 'sin-git'."""
    try:
        git = os.path.join(_raiz(), ".git")
        with open(os.path.join(git, "HEAD"), "r", encoding="utf-8") as f:
            head = f.read().strip()
        if not head.startswith("ref:"):
            return head[:7]                      # HEAD "suelto": es el hash
        ref = head.split(" ", 1)[1].strip()       # ej. refs/heads/main
        rama = ref.rsplit("/", 1)[-1]
        suelto = os.path.join(git, *ref.split("/"))
        if os.path.exists(suelto):
            with open(suelto, "r", encoding="utf-8") as f:
                return f"{rama} {f.read().strip()[:7]}"
        empaquetado = os.path.join(git, "packed-refs")   # refs comprimidas
        if os.path.exists(empaquetado):
            with open(empaquetado, "r", encoding="utf-8") as f:
                for linea in f:
                    if linea.rstrip().endswith(ref):
                        return f"{rama} {linea.split(' ', 1)[0][:7]}"
        return rama
    except Exception:  # noqa: BLE001
        return "sin-git"


def _carpeta_configurada() -> str:
    """Carpeta de logs elegida en credentials.ini ([logs] carpeta). Si no hay, o
    si no se puede usar, cae a la carpeta del proyecto (nunca falla por esto)."""
    try:
        cfg = configparser.ConfigParser()
        cfg.read(os.path.join(_raiz(), "config", "credentials.ini"))
        carpeta = cfg.get("logs", "carpeta", fallback="").strip()
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
            if os.path.isdir(carpeta):
                return carpeta
    except Exception:  # noqa: BLE001
        pass
    return _raiz()


def ruta_log(sufijo: str = "") -> str:
    partes = ["registro", nombre_maquina()]
    if sufijo:
        partes.append(sufijo)
    return os.path.join(_carpeta_configurada(), "_".join(partes) + ".log")


def configurar_registro(sufijo: str = "") -> None:
    """Prende el registro a archivo y la captura de errores. Llamar UNA vez.
    El 'sufijo' (el id del perfil) separa el log por broker/cuenta."""
    if _LOGGER.handlers:  # ya configurado
        return
    try:
        handler = RotatingFileHandler(
            ruta_log(sufijo), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
    except Exception:  # noqa: BLE001
        # si la carpeta configurada fallo (ej. Drive desconectado), al proyecto
        nombre = os.path.basename(ruta_log(sufijo))
        handler = RotatingFileHandler(
            os.path.join(_raiz(), nombre), maxBytes=2_000_000, backupCount=3,
            encoding="utf-8",
        )
    handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    _LOGGER.addHandler(handler)
    _LOGGER.setLevel(logging.INFO)

    # ---- errores no atrapados: que queden en el log antes de voltear nada ----
    def _hook(tipo, valor, tb):
        detalle = "".join(traceback.format_exception(tipo, valor, tb))
        _LOGGER.critical("ERROR NO ATRAPADO (esto es lo que voltea la app):\n%s", detalle)
        sys.__excepthook__(tipo, valor, tb)

    sys.excepthook = _hook

    def _hook_hilo(args):
        detalle = "".join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        )
        _LOGGER.critical("ERROR NO ATRAPADO en un hilo:\n%s", detalle)

    threading.excepthook = _hook_hilo


def log(mensaje: str) -> None:
    """Escribe una linea en el archivo de registro (si esta configurado)."""
    _LOGGER.info(mensaje)
