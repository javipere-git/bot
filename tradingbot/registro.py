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


def ruta_choques(sufijo: str = "") -> str:
    """Archivo donde queda el detalle de un CHOQUE NATIVO (ver activar_faulthandler)."""
    base = ruta_log(sufijo)
    carpeta, nombre = os.path.split(base)
    return os.path.join(carpeta, "choque_" + nombre.replace("registro_", ""))


# el archivo tiene que quedar ABIERTO mientras viva el proceso: si se cierra,
# faulthandler no puede escribir nada justo cuando mas hace falta
_ARCHIVO_CHOQUES = None


def activar_faulthandler(sufijo: str = "") -> str | None:
    """Deja anotado el detalle de un CHOQUE NATIVO (violacion de acceso).

    Por que hace falta: hay caidas que NO son errores de Python -por ejemplo la
    violacion de acceso 0xc0000005 que tumbo la app el 12/08/2026-. En esas, el
    proceso muere de golpe: el capturador de errores de Python no llega a correr y
    el registro no dice absolutamente nada. Esto es lo unico que deja rastro.

    IMPORTANTE (leccion aprendida): el archivo se deja VACIO al arrancar. Si tiene
    contenido es porque HUBO un choque, no porque la app se abrio. Antes se escribia
    una cabecera en cada arranque y eso llevo a dar por caidas corridas que estaban
    perfectas.
    """
    global _ARCHIVO_CHOQUES
    if _ARCHIVO_CHOQUES is not None:
        return None
    try:
        import faulthandler
    except Exception:  # noqa: BLE001
        return None
    ruta = ruta_choques(sufijo)
    anterior = None
    try:
        # si quedo algo de la corrida pasada, es el detalle de AQUEL choque
        if os.path.exists(ruta) and os.path.getsize(ruta) > 0:
            with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
                anterior = f.read()[:4000]
    except Exception:  # noqa: BLE001
        anterior = None
    try:
        _ARCHIVO_CHOQUES = open(ruta, "w", encoding="utf-8")   # arranca vacio
        faulthandler.enable(file=_ARCHIVO_CHOQUES, all_threads=True)
    except Exception:  # noqa: BLE001
        _ARCHIVO_CHOQUES = None
        return None
    return anterior


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


# ---------------------------------------------------------------------------
# Rastro del ARRANQUE
#
# Problema que resuelve: la app se abre con pythonw (sin consola) y el registro
# recien se configura DESPUES de elegir el broker. Si algo falla en el medio, el
# error se escribe en una salida que no existe: la ventana de login desaparece,
# no se abre nada y NO QUEDA NI UNA LINEA en ningun lado. Paso varias veces.
#
# Esto anota cada paso del arranque en un archivo chico de la carpeta del
# proyecto (que siempre se puede escribir, a diferencia de una carpeta de Drive).
# Se pisa en cada arranque: solo interesa el ULTIMO. Si la app no abrio, la
# ultima linea dice exactamente hasta donde llego.
# ---------------------------------------------------------------------------
_RUTA_ARRANQUE = None


def rastro_arranque(paso: str) -> None:
    """Anota un paso del arranque. No puede fallar nunca."""
    global _RUTA_ARRANQUE
    try:
        import datetime
        if _RUTA_ARRANQUE is None:
            _RUTA_ARRANQUE = os.path.join(_raiz(), "ultimo_arranque.log")
            modo = "w"       # el primero pisa lo de la corrida anterior
        else:
            modo = "a"
        with open(_RUTA_ARRANQUE, modo, encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {paso}\n")
    except Exception:  # noqa: BLE001
        pass


def anotar_falla_de_arranque(detalle: str) -> None:
    """Guarda el error que impidio abrir la app, pase lo que pase."""
    rastro_arranque("*** LA APP NO PUDO ABRIR ***\n" + detalle)
    try:
        _LOGGER.critical("LA APP NO PUDO ABRIR:\n%s", detalle)
    except Exception:  # noqa: BLE001
        pass
