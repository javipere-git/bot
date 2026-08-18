"""
Ventana principal de la app: el cartel de broker + cuenta (PAPER/LIVE) arriba y
las tres zonas (control / monitoreo / ladder) con divisores arrastrables.

Habla SIEMPRE con NUESTRO motor (core/engine.py) y NUESTRA interfaz comun
(core/broker.py). El broker concreto lo define el Perfil elegido al abrir
(Tradier, Alpaca...): la ventana no sabe con cual esta hablando.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .control_panel import ControlPanel
from .bot_runner import BotRunner
from .monitor_panel import MonitorPanel
from .market_worker import MarketWorker
from .ladder_panel import LadderPanel
from .tape_panel import TapePanel
from .perfiles import Perfil
from .estado_ui import (
    guardar_columnas,
    guardar_splitter,
    poner_titulo,
    restaurar_splitter,
)
from .tema import aplicar_tema, es_oscuro
from ..core.catalogo import guardar_catalogo
from ..core.historial import (
    filtrar_por_estado,
    guardar_operaciones,
    guardar_ordenes,
    resumen as resumen_operaciones,
    resumen_ordenes,
)
from ..core.planilla import guardar as guardar_planilla
from ..core.round_trips import (
    COLUMNAS as COLUMNAS_TRADES,
    armar as armar_round_trips,
    resumen as resumen_trades,
)
from ..core.models import OrderStatus, Side
from ..core.observador_movimiento import ObservadorMovimiento
from .sonidos import sonar_alerta, sonar_ejecucion

import configparser
import os
import threading


def _live_max_shares() -> int:
    """Tope de seguridad de acciones por orden en LIVE ([safety] en credentials.ini)."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(root, "config", "credentials.ini"))
    try:
        return int(cfg.get("safety", "live_max_shares", fallback="100"))
    except ValueError:
        return 100


def _zona(titulo: str, descripcion: str) -> QFrame:
    """Un panel placeholder con marco, titulo y una descripcion de lo que va a tener."""
    marco = QFrame()
    marco.setFrameShape(QFrame.StyledPanel)
    lay = QVBoxLayout(marco)
    lay.setContentsMargins(8, 8, 8, 8)

    t = QLabel(titulo)
    poner_titulo(t)
    desc = QLabel(descripcion)
    desc.setWordWrap(True)
    desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    desc.setStyleSheet("color: palette(mid);")

    lay.addWidget(t)
    lay.addWidget(desc)
    lay.addStretch()
    return marco


class _AvisoETB(QObject):
    """Solo transporta el resultado del pedido de la lista ETB desde el hilo que la
    trae hasta la pantalla. No hace el trabajo: lo hace un hilo simple de Python."""

    listo = Signal(object)
    error = Signal(str)


class _AvisoCatalogo(QObject):
    """Lo mismo, para el catalogo completo del broker (que simbolos tiene bloqueados,
    prestables, etc.). Es otra clase para que un pedido no pise al otro."""

    listo = Signal(object)
    error = Signal(str)


class _AvisoOperaciones(QObject):
    """Lo mismo, para el historial de operaciones de la cuenta."""

    listo = Signal(object)
    error = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self, perfil: Perfil) -> None:
        super().__init__()
        # El tema va PRIMERO: los paneles leen la paleta al construirse, asi que si
        # se aplica despues, los encabezados de las tablas quedan con los colores
        # del tema claro (blancos sobre fondo oscuro).
        aplicar_tema(es_oscuro())
        self._perfil = perfil
        es_paper = not perfil.es_live

        etiqueta = "LIVE" if perfil.es_live else "PAPER"
        self.setWindowTitle(
            f"Bot de trading + Ladder  -  {perfil.broker_nombre}  -  {etiqueta}"
        )
        self.resize(1200, 720)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- cartel de broker + cuenta (PAPER/LIVE) + estado de conexion ---
        color = "#E8820C" if es_paper else "#1e7d34"  # naranja=PAPER, verde=LIVE (real)
        texto_modo = f"{perfil.broker_nombre.upper()}   -   {perfil.cuenta_texto}"
        self.banner = QFrame()
        self.banner.setStyleSheet(f"background-color: {color};")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(10, 6, 10, 6)
        lbl_modo = QLabel(texto_modo)
        lbl_modo.setStyleSheet(
            "color: white; font-weight: bold; font-size: 13px; background: transparent;"
        )
        self.lbl_conexion = QLabel("")
        self.lbl_conexion.setStyleSheet(
            "color: white; font-weight: bold; background: transparent;"
        )
        self.btn_tema = QPushButton()
        self.btn_tema.setMaximumWidth(120)
        self.btn_tema.setToolTip("Cambiar entre modo claro y modo oscuro")
        self.btn_tema.clicked.connect(self._cambiar_tema)
        bl.addWidget(self.btn_tema)
        bl.addStretch()
        bl.addWidget(lbl_modo)
        bl.addStretch()
        bl.addWidget(self.lbl_conexion)
        outer.addWidget(self.banner)

        # --- tres zonas con divisores arrastrables ---
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        self._manual_broker = None  # canal para operar manual desde el ladder
        self._stream = None         # streaming de precios en vivo (produccion, solo lectura)
        self._avisos = None         # avisos de cuenta (orden puesta/ejecutada/cancelada)
        self._observador = ObservadorMovimiento()   # cuenta cambios de bid/ask (filtro)
        self._closed_seen = None    # ids de ordenes cerradas ya vistas (sonido / rechazos)
        self._pos_warned = False    # para avisar UNA vez si hay posicion abierta al abrir
        self.control = ControlPanel()
        self.monitor = MonitorPanel()
        self.ladder = LadderPanel(
            broker_provider=lambda: self._manual_broker,
            on_symbol=self._set_ladder_symbol,
            log=self.control.append_log,
        )

        self.tape = TapePanel()
        splitter.addWidget(self.control)
        splitter.addWidget(self.monitor)
        splitter.addWidget(self.ladder)
        splitter.addWidget(self.tape)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setStretchFactor(3, 0)
        splitter.setSizes([340, 400, 380, 240])
        self._splitter = splitter
        restaurar_splitter(splitter)      # como lo dejaste la vez pasada
        outer.addWidget(splitter, 1)

        self.statusBar().showMessage("Listo - esqueleto de la pantalla (Fase 5).")

        # --- estado del bot (corre en un hilo aparte) ---
        self._thread: QThread | None = None
        self._runner: BotRunner | None = None
        self.control.btn_iniciar.clicked.connect(self._iniciar)
        self.control.btn_pausar.clicked.connect(self._pausar)
        self.control.btn_reanudar.clicked.connect(self._reanudar)
        self.control.btn_detener.clicked.connect(self._detener)
        self.control.btn_etb_cargar.clicked.connect(lambda: self._lista_etb("cargar"))
        self.control.btn_etb_bajar.clicked.connect(lambda: self._lista_etb("bajar"))
        self.control.btn_catalogo.clicked.connect(self._bajar_catalogo)
        self.control.traer_bloqueadas = self._traer_bloqueadas
        self.control.btn_descargar_reporte.clicked.connect(self._abrir_reporte)
        self.control.btn_operaciones.clicked.connect(self._bajar_operaciones)
        self._set_running(False)

        # --- reportes de las pasadas del dia (contadores del motor + neto por
        # diferencia del realizado del broker). Viven en memoria y se guardan en disco
        # al terminar cada pasada; el desplegable los lista por horario. ---
        self._reportes_dia: list = []           # ReportePasada de hoy
        self._ultimo_realizado: float | None = None   # ultimo "realizado" que informo el broker
        self._realizado_inicio: float | None = None   # foto al apretar Iniciar
        self._broker_pasada = None              # broker de la corrida (para leer el neto)
        self._cargar_reportes_de_hoy()          # si ya hubo pasadas hoy, las trae del disco

        # monitoreo en vivo (su propio broker de lectura, en otro hilo)
        self._arrancar_monitoreo()
        # streaming de precios en vivo para el ladder (token de produccion, SOLO lectura)
        self._arrancar_streaming()
        # avisos de cuenta: para que las ordenes aparezcan al instante
        self._arrancar_avisos()

        # indicador permanente de conexion del streaming en el encabezado
        self._conexion_timer = QTimer(self)
        self._conexion_timer.setInterval(1000)
        self._conexion_timer.timeout.connect(self._actualizar_conexion)
        self._conexion_timer.start()
        self._actualizar_conexion()

        self._actualizar_boton_tema()

    # ---------- control del bot (en hilo aparte) ----------
    def _iniciar(self) -> None:
        symbols = self.control.get_symbols()
        if not symbols:
            self.control.append_log("Watchlist vacia: carga al menos un simbolo.")
            return
        try:
            config = self.control.build_config()
        except Exception as e:  # noqa: BLE001
            self.control.append_log(f"Configuracion invalida: {e}")
            return

        es_live = self._perfil.es_live
        if es_live:
            # Salvaguarda: tope de tamano en LIVE.
            cap = _live_max_shares()
            if config.quantity > cap:
                self.control.append_log(
                    f"*** LIVE: la cantidad ({config.quantity}) supera el tope de seguridad "
                    f"({cap}). Baja la cantidad o cambia live_max_shares en "
                    f"config/credentials.ini. NO se inicio el bot. ***"
                )
                return
            # Salvaguarda: segunda confirmacion, con el resumen de lo que va a hacer.
            lado = "Compra (largo)" if config.side == Side.BUY else "Venta en corto"
            lista = ", ".join(symbols[:8]) + ("..." if len(symbols) > 8 else "")
            r = QMessageBox.warning(
                self,
                "Confirmar operacion con DINERO REAL",
                (
                    "MODO LIVE - DINERO REAL\n\n"
                    f"Vas a iniciar el bot sobre tu cuenta REAL:\n"
                    f"- Simbolos ({len(symbols)}): {lista}\n"
                    f"- Lado: {lado}\n"
                    f"- Cantidad por orden: {config.quantity} acciones\n\n"
                    "Las ordenes se ejecutan con dinero de verdad. Confirmas?"
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                self.control.append_log("Inicio en LIVE cancelado por el usuario.")
                return

        try:
            broker = self._perfil.crear_broker()
        except Exception as e:  # noqa: BLE001
            self.control.append_log(
                f"No pude conectar a {self._perfil.broker_nombre}: {e}"
            )
            return

        # Chequeo previo: si vas a entrar en CORTO, que la cuenta lo permita.
        # (Ej.: las cuentas de Alpaca sin margen tienen el corto deshabilitado; sin
        # esto el bot mandaria orden tras orden y las cobraria todas rechazadas.)
        if config.side == Side.SELL_SHORT:
            try:
                permite = broker.puede_operar_en_corto()
            except Exception:  # noqa: BLE001
                permite = None
            if permite is False:
                self.control.append_log(
                    f"*** {self._perfil.broker_nombre}: esta cuenta NO permite ventas en "
                    f"CORTO. Cambia el lado a Compra, o habilita margen/corto en el "
                    f"broker. NO se inicio el bot. ***"
                )
                return

        if self.control.chk_ext.isChecked():
            self.control.append_log(
                "Extended hours ACTIVADO: las ordenes pueden ejecutarse fuera de la "
                "rueda regular (pre/post; overnight en Alpaca)."
            )

        etiqueta = "LIVE - DINERO REAL" if es_live else "paper"
        self.control.append_log(
            f"Iniciando bot ({etiqueta}) con {len(symbols)} simbolo(s): {', '.join(symbols)}"
        )
        self._thread = QThread()
        # el streaming se suscribe a TODA la watchlist: asi el observador puede medir
        # cuantas veces se movio el bid/ask de cada simbolo antes de que el bot llegue
        filtra_movimiento = (config.max_cambios_bid is not None
                             or config.max_cambios_ask is not None
                             or config.max_spread_pct is not None
                             or config.max_volumen_seg is not None)
        if self._stream is not None and filtra_movimiento:
            self._observador.observar(symbols)
            self._stream.set_watchlist(symbols)
            self.control.append_log(
                f"Filtro de movimiento activo: sigo el bid/ask de {len(symbols)} "
                f"simbolos por streaming."
            )
        # foto del "realizado" del broker al arrancar: el neto de la pasada sera la
        # diferencia contra el realizado al terminar (asi sale neto de comisiones e
        # incluye cierres a mano). Es 1 lectura, ANTES de que el bot empiece a escanear.
        self._broker_pasada = broker
        self._realizado_inicio = self._leer_realizado(broker)

        self._runner = BotRunner(broker, config, symbols, observador=self._observador)
        self._runner.moveToThread(self._thread)
        self._runner.log.connect(self.control.append_log)
        self._runner.manual.connect(self._on_manual)
        self._runner.pausado.connect(self._on_pausado)
        self._runner.finished.connect(self._on_finished)
        self._thread.started.connect(self._runner.run)
        self._thread.start()
        self._set_running(True)
        self._bot_escaneando(True)

    def _detener(self) -> None:
        if self._runner is not None:
            self.control.append_log("Deteniendo (al terminar la accion en curso)...")
            self._runner.stop()

    def _pausar(self) -> None:
        if self._runner is not None:
            self._runner.pause()
            self._bot_escaneando(False)         # el usuario opera a mano: avisos ON
            self.control.append_log("Pausado (entre simbolos).")

    def _reanudar(self) -> None:
        if self._runner is not None:
            self._runner.resume()
            self._bot_escaneando(True)          # vuelve a recorrer la watchlist
            self.control.append_log("Reanudado.")

    def _on_manual(self, sym: str, por_guardia: bool = False) -> None:
        """El bot dejo una posicion abierta para cerrar a mano (guardia disparado o
        los niveles no cerraron): traigo ese simbolo al ladder solo, asi lo tenes
        listo para operar sin tener que buscarlo y cargarlo. Si fue el GUARDIA y la
        opcion esta tildada, ademas suena la alarma continua hasta que confirmes."""
        if not sym:
            return
        self.ladder.cargar_symbol(sym)
        self._bot_escaneando(False)             # ahora operas a mano: avisos instantaneos ON
        self.control.append_log(f"Ladder: cargue {sym} solo (quedo para cerrar a mano).")
        if por_guardia and self.control.chk_guard_alarma.isChecked():
            self._alarma_guardia(sym)

    def _alarma_guardia(self, sym: str) -> None:
        """Alarma sostenida del guardia: suena repetida hasta que aceptes el cartel.

        UN SOLO CARTEL A LA VEZ. El cartel es modal y, mientras esta abierto, Qt sigue
        atendiendo avisos: si llegara un segundo disparo, se apilaria otro cartel
        encima y habria que aceptar los dos para apagar la alarma. El motor ya no
        avisa dos veces, pero esto lo deja garantizado venga de donde venga.
        """
        if getattr(self, "_alarma_abierta", False):
            self.control.append_log(
                f"Guardia: {sym} - la alarma ya esta sonando, no abro otro cartel."
            )
            return
        self._alarma_abierta = True
        # SONAR YA, antes de abrir el cartel. Antes solo arrancaba el temporizador,
        # asi que el primer sonido llegaba 1,2 segundos despues: si aceptabas rapido,
        # la alarma no sonaba NUNCA. En una alerta de seguridad eso no va.
        sonar_alerta()
        timer = QTimer(self)
        timer.setInterval(1200)
        timer.timeout.connect(sonar_alerta)
        timer.start()
        try:
            QMessageBox.critical(
                self,
                "GUARDIA DISPARADO",
                (
                    "GUARDIA DE MOVIMIENTO EN CONTRA DISPARADO\n\n"
                    f"{sym}: el precio se movio en contra y la posicion quedo ABIERTA.\n"
                    f"Ya cargue {sym} en el ladder para que la cierres a mano.\n\n"
                    "Al apretar Aceptar se apaga la alarma."
                ),
            )
        finally:
            # pase lo que pase, la alarma se apaga y se puede volver a avisar
            timer.stop()
            timer.deleteLater()
            self._alarma_abierta = False

    def _on_finished(self, outcome: str) -> None:
        self.control.append_log(f"Bot finalizo: {outcome}")
        # tomo el reporte ANTES de soltar el runner
        rep = self._runner.engine.reporte if self._runner is not None else None
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._runner = None
        self._set_running(False)
        self._bot_escaneando(False)
        self._finalizar_reporte(rep)

    # ===================== reportes de las pasadas =====================
    def _recordar_realizado(self, dia) -> None:
        """Guarda el ultimo 'realizado' que informo el broker (para el neto)."""
        try:
            self._ultimo_realizado = float(dia.realizado)
        except Exception:  # noqa: BLE001
            pass

    def _leer_realizado(self, broker) -> float | None:
        """Lee el realizado del dia del broker (defensivo). Si no puede, cae al ultimo
        valor que llego por el monitoreo; si tampoco, None (el neto quedara n/d)."""
        try:
            dia = broker.get_day_pnl()
            if dia is not None:
                return float(dia.realizado)
        except Exception:  # noqa: BLE001
            pass
        return self._ultimo_realizado

    def _finalizar_reporte(self, rep) -> None:
        """Cierra la pasada: completa el neto, la guarda en memoria y en disco, y
        refresca el desplegable. Nunca corta la app si algo falla."""
        if rep is None:
            return
        try:
            realizado_fin = self._leer_realizado(self._broker_pasada) \
                if self._broker_pasada is not None else self._ultimo_realizado
            if self._realizado_inicio is not None and realizado_fin is not None:
                rep.neto = realizado_fin - self._realizado_inicio
                rep.neto_disponible = True
            self._reportes_dia.append(rep)
            self._guardar_reporte_disco(rep)
            self._refrescar_combo_reportes()
            neto = (f"{'+' if rep.neto >= 0 else ''}{rep.neto:.2f} USD"
                    if rep.neto_disponible and rep.neto is not None else "n/d")
            self.control.append_log(
                f"Reporte de la pasada listo ({rep.rango_horario()}, neto {neto}). "
                f"Abrilo desde el desplegable al lado de 'Registro:'."
            )
        except Exception as e:  # noqa: BLE001
            self.control.append_log(f"No pude armar el reporte de la pasada: {e}")
        finally:
            self._realizado_inicio = None
            self._broker_pasada = None

    def _dir_reportes(self, cuando: float | None = None, crear: bool = False) -> str:
        """Carpeta del dia: reportes/AAAA-MM-DD/. Un dia por carpeta.
        `cuando` es el epoch del que sale la fecha (por defecto, hoy)."""
        import time as _t
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dia = _t.strftime("%Y-%m-%d", _t.localtime(cuando if cuando is not None else _t.time()))
        d = os.path.join(raiz, "reportes", dia)
        if crear:
            os.makedirs(d, exist_ok=True)
        return d

    def _dir_datos(self, cuando: float | None = None, crear: bool = False) -> str:
        """Subcarpeta 'datos' del dia: guarda los .json que la app relee al reabrir
        (asi la vista del usuario en reportes/AAAA-MM-DD/ queda limpia, solo .txt)."""
        d = os.path.join(self._dir_reportes(cuando), "datos")
        if crear:
            os.makedirs(d, exist_ok=True)
        return d

    def _nombre_base_pasada(self, rep) -> str:
        import time as _t
        return _t.strftime("pasada_%Y-%m-%d_%H-%M-%S", _t.localtime(rep.inicio))

    def _ruta_txt_pasada(self, rep) -> str:
        return os.path.join(self._dir_reportes(rep.inicio), self._nombre_base_pasada(rep) + ".txt")

    def _guardar_reporte_disco(self, rep) -> None:
        """Guarda la pasada en reportes/AAAA-MM-DD/: el .txt (legible, se abre desde la
        app o desde la carpeta) y un .json en datos/ (para reconstruir el desplegable y
        el resumen del dia si cerras y volves a abrir la app)."""
        from ..core.reporte import render_pasada
        import json
        base = self._nombre_base_pasada(rep)
        try:
            self._dir_reportes(rep.inicio, crear=True)
            with open(self._ruta_txt_pasada(rep), "w", encoding="utf-8") as f:
                f.write(render_pasada(rep))
        except Exception:  # noqa: BLE001
            pass   # que no falle nunca: es solo el respaldo en disco
        try:
            self._dir_datos(rep.inicio, crear=True)
            with open(os.path.join(self._dir_datos(rep.inicio), base + ".json"), "w",
                      encoding="utf-8") as f:
                json.dump(rep.to_dict(), f, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            pass

    def _cargar_reportes_de_hoy(self) -> None:
        """Al abrir la app, trae del disco las pasadas de HOY (si las hay) para que el
        desplegable y el resumen del dia sigan disponibles tras cerrar y reabrir."""
        from ..core.reporte import ReportePasada
        import glob
        import json
        try:
            carpeta = self._dir_datos()   # datos de hoy (no la crea si no existe)
            cargados = []
            for ruta in sorted(glob.glob(os.path.join(carpeta, "pasada_*.json"))):
                try:
                    with open(ruta, "r", encoding="utf-8") as f:
                        cargados.append(ReportePasada.from_dict(json.load(f)))
                except Exception:  # noqa: BLE001
                    continue   # un archivo roto no tira abajo el resto
            cargados.sort(key=lambda r: r.inicio)
            self._reportes_dia = cargados
            if cargados:
                self.control.append_log(
                    f"Reportes: recupere {len(cargados)} pasada(s) de hoy de la carpeta."
                )
        except Exception:  # noqa: BLE001
            self._reportes_dia = []
        self._refrescar_combo_reportes()

    def _refrescar_combo_reportes(self) -> None:
        """Llena el desplegable: resumen del dia + una entrada por pasada (por horario)."""
        combo = self.control.combo_reportes
        combo.blockSignals(True)
        combo.clear()
        if self._reportes_dia:
            combo.addItem(f"Resumen del dia ({len(self._reportes_dia)} pasadas)", "resumen")
            for i, rep in enumerate(self._reportes_dia):
                combo.addItem(rep.rango_horario(), i)
            self.control.btn_descargar_reporte.setEnabled(True)
        else:
            combo.addItem("(todavia no hay pasadas)", None)
            self.control.btn_descargar_reporte.setEnabled(False)
        combo.blockSignals(False)

    def _abrir_archivo(self, ruta: str) -> bool:
        """Abre un archivo con el programa por defecto de Windows (Bloc de notas)."""
        try:
            os.startfile(ruta)  # noqa: S606  (Windows)
            return True
        except Exception as e:  # noqa: BLE001
            self.control.append_log(f"No pude abrir el archivo ({e}). Esta en: {ruta}")
            return False

    def _abrir_reporte(self) -> None:
        """Las pasadas ya estan guardadas: se abren. El resumen del dia se genera en el
        momento, se guarda en la carpeta del dia y se abre."""
        from ..core.reporte import render_pasada, render_resumen_dia
        import time as _t
        if not self._reportes_dia:
            self.control.append_log("Todavia no hay ninguna pasada.")
            return
        dato = self.control.combo_reportes.currentData()
        if dato == "resumen":
            try:
                self._dir_reportes(crear=True)
                ruta = os.path.join(self._dir_reportes(),
                                    _t.strftime("resumen_dia_%Y-%m-%d.txt"))
                with open(ruta, "w", encoding="utf-8") as f:
                    f.write(render_resumen_dia(self._reportes_dia))
            except Exception as e:  # noqa: BLE001
                self.control.append_log(f"No pude generar el resumen del dia: {e}")
                return
            if self._abrir_archivo(ruta):
                self.control.append_log(f"Resumen del dia generado y abierto: {ruta}")
        elif isinstance(dato, int) and 0 <= dato < len(self._reportes_dia):
            rep = self._reportes_dia[dato]
            ruta = self._ruta_txt_pasada(rep)
            if not os.path.exists(ruta):     # por si falto el .txt: lo re-genero
                try:
                    self._dir_reportes(rep.inicio, crear=True)
                    with open(ruta, "w", encoding="utf-8") as f:
                        f.write(render_pasada(rep))
                except Exception as e:  # noqa: BLE001
                    self.control.append_log(f"No pude abrir el reporte: {e}")
                    return
            self._abrir_archivo(ruta)
        else:
            self.control.append_log("Elegi una pasada o el resumen del dia primero.")

    def _lista_etb(self, accion: str, ruta: str | None = None) -> None:
        """Trae las acciones EASY TO BORROW y las carga en la watchlist o las guarda
        en un archivo.

        La lista se le pide al broker donde se OPERA (con el perfil hibrido, el que
        ejecuta, no el que da los precios): es el que acepta o rechaza el short.

        Se pide en OTRO HILO porque en Alpaca la respuesta trae ~14.000 activos y
        tarda unos segundos; si se pidiera en el hilo de la pantalla, la app quedaria
        congelada mientras tanto.
        """
        if accion == "bajar" and not ruta:
            # El cuadro de "guardar como" va ACA, ANTES de arrancar el hilo. Abrirlo
            # despues, desde el manejador de la señal del hilo, colgaba la app en
            # Windows (dialogo modal mientras el hilo esta terminando).
            ruta, _ = QFileDialog.getSaveFileName(
                self, "Guardar la lista ETB",
                f"etb_{self._perfil.broker_nombre.lower()}.txt",
                "Texto (*.txt);;CSV (*.csv)",
            )
            if not ruta:
                self.control.append_log("Lista ETB: descarga cancelada.")
                return
        try:
            # conexion propia: compartir la del ladder entre hilos puede trabarse
            broker = self._perfil.crear_broker()
        except Exception as e:  # noqa: BLE001
            self.control.append_log(f"Lista ETB: no hay conexion con el broker ({e})")
            return
        for b in (self.control.btn_etb_cargar, self.control.btn_etb_bajar):
            b.setEnabled(False)
        self.control.append_log(
            f"Pidiendo la lista ETB a {self._perfil.broker_nombre} (donde operas)..."
        )

        # Hilo SIMPLE de Python + señal Qt, el mismo patron que ya usa el streaming.
        # Se probo con QThread + moveToThread y trajo dos problemas seguidos (el
        # trabajador descartado por Python, y la app colgada); esto no tiene ciclo de
        # vida que administrar: el hilo termina solo y la señal llega al hilo de la
        # pantalla como corresponde.
        aviso = _AvisoETB()                 # vive en el hilo de la pantalla
        aviso.listo.connect(lambda syms, a=accion, r=ruta: self._etb_recibida(syms, a, r))
        aviso.error.connect(
            lambda m: self.control.append_log(f"Lista ETB: no se pudo traer ({m})")
        )
        for senal in (aviso.listo, aviso.error):
            senal.connect(lambda *_: self._soltar_botones_etb())
        self._aviso_etb = aviso             # referencia (si no, Python lo descarta)

        def _trabajo():
            try:
                aviso.listo.emit(broker.lista_etb())
            except Exception as e:  # noqa: BLE001
                aviso.error.emit(str(e))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _soltar_botones_etb(self) -> None:
        for b in (self.control.btn_etb_cargar, self.control.btn_etb_bajar):
            b.setEnabled(True)

    def _etb_recibida(self, symbols, accion: str, ruta: str | None = None) -> None:
        """Ya llego la lista. NO se abre ningun dialogo aca: la carpeta se eligio
        antes de arrancar el hilo (abrir uno desde este punto colgaba la app)."""
        if not symbols:
            self.control.append_log(
                f"Lista ETB: {self._perfil.broker_nombre} no devolvio simbolos."
            )
            return
        origen = self._perfil.broker_nombre
        if accion == "cargar":
            self.control.txt_watchlist.setPlainText(" ".join(symbols))
            self.control.append_log(
                f"Watchlist cargada con {len(symbols):,} acciones ETB de {origen}."
            )
            return
        if not ruta:
            self.control.append_log("Lista ETB: no se eligio donde guardar.")
            return
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write("\n".join(symbols) + "\n")
            self.control.append_log(
                f"Lista ETB de {origen} guardada: {len(symbols):,} acciones en {ruta}"
            )
        except Exception as e:  # noqa: BLE001
            self.control.append_log(f"Lista ETB: no se pudo guardar ({e})")

    # ---------- catalogo del broker (excluidas + descarga a Excel) ----------
    def _pedir_catalogo(self, al_llegar, al_fallar, etiqueta: str) -> None:
        """Le pide al broker donde se OPERA todo lo que sabe de cada simbolo.

        Es el pedido mas pesado de la app (Tasty son 14 paginas, ~7 s; Alpaca una
        sola llamada, ~2 s), asi que va en otro hilo si o si. Mismo patron que la
        lista ETB: hilo simple de Python + señal Qt, y conexion propia para no
        compartir la del ladder entre hilos.
        """
        try:
            broker = self._perfil.crear_broker()
        except Exception as e:  # noqa: BLE001
            self.control.append_log(f"{etiqueta}: no hay conexion con el broker ({e})")
            al_fallar(str(e))
            return
        self.control.append_log(
            f"{etiqueta}: pidiendole el catalogo a {self._perfil.broker_nombre} "
            f"(donde operas). Puede tardar unos segundos..."
        )
        aviso = _AvisoCatalogo()
        # va PRIMERO: si el conector tuvo que sacar la lista de otro lado, se lee
        # antes que nada (el sandbox de Tasty no marca ninguna bloqueada)
        aviso.listo.connect(lambda _f: self._nota_catalogo(broker, etiqueta))
        aviso.listo.connect(al_llegar)
        aviso.error.connect(al_fallar)
        aviso.error.connect(
            lambda m: self.control.append_log(f"{etiqueta}: no se pudo traer ({m})")
        )
        self._aviso_catalogo = aviso        # referencia (si no, Python lo descarta)

        def _trabajo():
            try:
                aviso.listo.emit(broker.catalogo())
            except Exception as e:  # noqa: BLE001
                aviso.error.emit(str(e))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _nota_catalogo(self, broker, etiqueta: str) -> None:
        nota = getattr(broker, "catalogo_origen", None)
        if nota:
            self.control.append_log(f"{etiqueta}: {nota}")

    def _traer_bloqueadas(self, dlg) -> None:
        """Boton 'Traer del broker' del cuadro de excluidas: carga SOLO la seccion
        del broker con los simbolos que tiene bloqueados para abrir posicion."""
        nombre = self._perfil.broker_nombre
        dlg.btn_traer.setEnabled(False)
        dlg.lbl_estado.setText(f"Preguntandole a {nombre}...")

        def _llego(filas):
            try:
                dlg.btn_traer.setEnabled(True)
                if not filas:
                    # Tradier no tiene catalogo: mejor no tocar nada que vaciar la lista
                    dlg.lbl_estado.setText(
                        f"{nombre} no informa esta lista. No se toco nada.")
                    return
                bloqueadas = [f["symbol"] for f in filas if f.get("bloqueada")]
                dlg.poner_del_broker(bloqueadas)
                self.control.append_log(
                    f"Excluidas: {nombre} tiene {len(bloqueadas):,} simbolo(s) "
                    f"bloqueado(s) de {len(filas):,}. Acordate de guardar."
                )
            except RuntimeError:
                pass        # cerraste el cuadro antes de que llegara la respuesta

        def _fallo(msg):
            try:
                dlg.btn_traer.setEnabled(True)
                dlg.lbl_estado.setText(f"No se pudo traer: {msg}")
            except RuntimeError:
                pass

        self._pedir_catalogo(_llego, _fallo, "Excluidas")

    def _bajar_catalogo(self) -> None:
        """Baja el catalogo completo a un CSV que abre Excel."""
        # el 'guardar como' va ANTES de arrancar el hilo (abrirlo despues, desde el
        # manejador de la señal, colgaba la app en Windows)
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar el catalogo del broker",
            f"catalogo_{self._perfil.broker_nombre.lower()}.csv",
            "CSV para Excel (*.csv)",
        )
        if not ruta:
            self.control.append_log("Catalogo: descarga cancelada.")
            return
        self.control.btn_catalogo.setEnabled(False)
        self._pedir_catalogo(
            lambda filas: self._catalogo_recibido(filas, ruta),
            lambda _m: self.control.btn_catalogo.setEnabled(True),
            "Catalogo",
        )

    def _catalogo_recibido(self, filas, ruta: str) -> None:
        self.control.btn_catalogo.setEnabled(True)
        if not filas:
            self.control.append_log(
                f"Catalogo: {self._perfil.broker_nombre} no lo ofrece "
                f"(Tradier no tiene esta lista)."
            )
            return
        try:
            guardar_catalogo(filas, ruta)
        except Exception as e:  # noqa: BLE001
            self.control.append_log(f"Catalogo: no se pudo guardar ({e})")
            return
        bloqueadas = sum(1 for f in filas if f.get("bloqueada"))
        self.control.append_log(
            f"Catalogo de {self._perfil.broker_nombre}: {len(filas):,} simbolo(s), "
            f"{bloqueadas:,} bloqueado(s) para abrir. Guardado en {ruta}"
        )

    # ---------- reportes de la cuenta (ejecuciones / ordenes / trades) ----------
    def _bajar_operaciones(self) -> None:
        """Baja a un archivo un reporte de la cuenta entre dos fechas.

        Los dos cuadros (el del reporte y el 'guardar como') se abren ANTES de
        arrancar el hilo: abrir uno desde el aviso del hilo colgaba la app."""
        from .operaciones_dialog import ORDENES, TRADES, DialogoOperaciones

        dlg = DialogoOperaciones(self, broker=self._perfil.broker_nombre)
        if not dlg.exec():
            return
        tipo = dlg.tipo()
        estados = dlg.estados()
        desde, hasta = dlg.fechas()
        nombre = {TRADES: "trades", ORDENES: "ordenes"}.get(tipo, "ejecuciones")
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar el reporte",
            f"{nombre}_{self._perfil.broker_nombre.lower()}_{desde}_a_{hasta}.csv",
            "CSV para Excel (*.csv)",
        )
        if not ruta:
            self.control.append_log("Reportes: descarga cancelada.")
            return
        try:
            # conexion propia: compartir la del ladder entre hilos puede trabarse
            broker = self._perfil.crear_broker()
        except Exception as e:  # noqa: BLE001
            self.control.append_log(f"Reportes: no hay conexion con el broker ({e})")
            return
        self.control.btn_operaciones.setEnabled(False)
        self.control.append_log(
            f"Reportes: pidiendo a {self._perfil.broker_nombre} las {nombre} "
            f"del {desde} al {hasta}..."
        )
        aviso = _AvisoOperaciones()
        aviso.listo.connect(
            lambda filas: self._reporte_recibido(filas, ruta, tipo, estados))
        aviso.error.connect(
            lambda m: self.control.append_log(f"Reportes: no se pudo traer ({m})")
        )
        for senal in (aviso.listo, aviso.error):
            senal.connect(lambda *_: self.control.btn_operaciones.setEnabled(True))
        self._aviso_ops = aviso             # referencia (si no, Python lo descarta)

        def _trabajo():
            try:
                # los trades salen de las ejecuciones: no cuestan una llamada aparte
                if tipo == ORDENES:
                    aviso.listo.emit(broker.ordenes_historicas(desde, hasta))
                else:
                    aviso.listo.emit(broker.operaciones(desde, hasta))
            except Exception as e:  # noqa: BLE001
                aviso.error.emit(str(e))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _reporte_recibido(self, filas, ruta: str, tipo: str, estados) -> None:
        """Ya llego. NO se abre ningun dialogo aca (ver _bajar_operaciones)."""
        from .operaciones_dialog import ORDENES, TRADES

        if not filas:
            falta = (" Tradier no ofrece el historial de ordenes: su API solo guarda "
                     "las del dia." if tipo == ORDENES else "")
            self.control.append_log(
                f"Reportes: {self._perfil.broker_nombre} no devolvio nada en esas "
                f"fechas.{falta}"
            )
            return
        try:
            if tipo == ORDENES:
                elegidas = filtrar_por_estado(filas, estados)
                if not elegidas:
                    self.control.append_log(
                        f"Reportes: de {len(filas):,} orden(es), ninguna esta en los "
                        f"estados que pediste. No se guardo nada."
                    )
                    return
                guardar_ordenes(elegidas, ruta)
                detalle = resumen_ordenes(elegidas)
            elif tipo == TRADES:
                cerrados, sueltas = armar_round_trips(filas)
                if not cerrados:
                    self.control.append_log(
                        f"Reportes: {len(filas):,} ejecucion(es), pero no se cerro "
                        f"ningun trade completo en esas fechas. Probá un rango mas "
                        f"largo: la salida puede haber quedado afuera."
                    )
                    return
                guardar_planilla(cerrados, COLUMNAS_TRADES, ruta)
                detalle = resumen_trades(cerrados, sueltas)
            else:
                guardar_operaciones(filas, ruta)
                detalle = resumen_operaciones(filas)
        except Exception as e:  # noqa: BLE001
            self.control.append_log(f"Reportes: no se pudo guardar ({e})")
            return
        self.control.append_log(
            f"Reportes de {self._perfil.broker_nombre}: {detalle}. Guardado en {ruta}"
        )

    def _bot_escaneando(self, valor: bool) -> None:
        """Le avisa al monitoreo si el bot esta escaneando la watchlist. Mientras lo
        este, se apagan los refrescos por aviso (si no, con el bot metiendo ordenes
        rapido se agota el cupo de la API). En manual quedan activos."""
        if getattr(self, "_market_worker", None) is not None:
            self._market_worker.set_bot_escaneando(valor)

    def _set_running(self, running: bool, pausado: bool = False) -> None:
        """Prende y apaga los botones segun en que estado esta el bot:

            DETENIDO  -> solo Iniciar
            CORRIENDO -> Pausar y Detener
            PAUSADO   -> Reanudar y Detener

        Asi el boton que apretas siempre hace algo, y el que no corresponde no se
        puede apretar (antes Reanudar quedaba activo con el bot ya corriendo).
        """
        self._pausado = bool(pausado) and bool(running)
        self.control.btn_iniciar.setEnabled(not running)
        self.control.btn_pausar.setEnabled(running and not self._pausado)
        self.control.btn_reanudar.setEnabled(running and self._pausado)
        self.control.btn_detener.setEnabled(running)

    def _on_pausado(self, pausado: bool) -> None:
        """El motor avisa que se pauso o siguio (incluidas las pausas que se toma
        solo: posicion en manual, 'pausar tras operar', ya habia posicion abierta)."""
        if self._runner is not None:
            self._set_running(True, pausado)

    # ---------- monitoreo en vivo (en hilo aparte) ----------
    def _arrancar_monitoreo(self) -> None:
        self._market_thread: QThread | None = None
        self._market_worker: MarketWorker | None = None
        try:
            broker = self._perfil.crear_broker()
            self._manual_broker = self._perfil.crear_broker()
        except Exception as e:  # noqa: BLE001
            self.control.append_log(
                f"Monitoreo/Ladder sin datos (no conecto a {self._perfil.broker_nombre}): {e}"
            )
            return
        if self._perfil.es_live:
            self.control.append_log(
                "*** MODO LIVE: el bot y el ladder operan sobre tu CUENTA REAL. "
                "Cada click en el ladder es una orden con dinero de verdad. ***"
            )
        self._market_thread = QThread()
        self._market_worker = MarketWorker(broker, interval=4.0)
        self._market_worker.moveToThread(self._market_thread)
        self._market_worker.positions.connect(self.monitor.set_positions)
        self._market_worker.positions.connect(self._on_positions)
        self._market_worker.orders.connect(self.monitor.set_orders)
        self._market_worker.closed_orders.connect(self.monitor.set_closed_orders)
        self._market_worker.closed_orders.connect(self._on_closed_orders)
        self._market_worker.day_pnl.connect(self.monitor.set_day_pnl)
        self._market_worker.day_pnl.connect(self._recordar_realizado)
        # el sondeo por REST es el RESPALDO del ladder (para simbolos poco liquidos,
        # donde el streaming se queda mudo). No pisa al streaming si esta despachando:
        # el REST redondea los tamanos al lote y borraria los odd lots de Tastytrade.
        self._market_worker.quote.connect(self.ladder.actualizar_quote_rest)
        self._market_worker.orders.connect(self.ladder.set_orders)
        self._market_worker.positions.connect(self.ladder.set_positions)
        self._market_worker.error.connect(self.control.append_log)
        self._market_thread.started.connect(self._market_worker.run)
        self._market_thread.start()

    def _arrancar_streaming(self) -> None:
        try:
            self._stream = self._perfil.crear_stream()
        except Exception as e:  # noqa: BLE001
            self._stream = None
            self.control.append_log(f"Ladder sin tiempo real (uso precios por REST): {e}")
            return
        if self._stream is None:
            self.control.append_log(
                f"{self._perfil.broker_nombre}: ladder por REST (streaming aun no cableado)."
            )
            return
        self._stream.quote.connect(self._anotar_movimiento)
        self._stream.quote.connect(self.ladder.actualizar_quote)
        # el ladder consulta si el streaming sigue vivo: mientras lo este, ignora el
        # sondeo por REST (que da un mercado peor: redondea al lote y esconde los
        # odd lots). Si se cae, el respaldo vuelve a entrar solo.
        self.ladder.set_stream_vivo(self._stream.esta_conectado)
        # y si ese feed trae odd lots (solo Tastytrade): entonces el streaming NO es
        # el NBBO, y los carteles/botones tienen que ir con el NBBO real del REST
        self.ladder.set_stream_odd_lots(self._stream.trae_odd_lots)
        if self._stream.trae_odd_lots():
            self.control.append_log(
                "Este feed trae ODD LOTS: la escalera los muestra dentro del spread, "
                "pero los carteles y los botones van con el NBBO real (lotes redondos)."
            )
        # Time & Sales: el mismo stream ya abierto trae las operaciones ejecutadas
        self._stream.quote.connect(self.tape.actualizar_quote)
        self._stream.trade.connect(self._anotar_operacion)
        self._stream.trade.connect(self.tape.agregar_trade)
        self.control.append_log("Streaming en vivo activo (produccion, SOLO lectura de precios).")

    def _anotar_movimiento(self, sym, bid, ask, *resto) -> None:
        """Cada quote del streaming alimenta al observador de movimiento."""
        self._observador.anotar(sym, bid, ask)

    def _anotar_operacion(self, sym, precio, cantidad, *resto) -> None:
        """Cada operacion del streaming alimenta el volumen reciente del observador."""
        self._observador.anotar_operacion(sym, cantidad)

    def _arrancar_avisos(self) -> None:
        """Canal de avisos del broker: cuando una orden cambia de estado, refresca
        el monitoreo y el ladder EN EL MOMENTO (medido: ~200 ms) en vez de esperar
        el sondeo de cada 4 segundos."""
        try:
            # el broker va como TRADUCTOR del aviso (no se le pide nada)
            self._avisos = self._perfil.crear_avisos(self._manual_broker)
        except Exception as e:  # noqa: BLE001
            self._avisos = None
            self.control.append_log(f"Sin avisos instantaneos del broker: {e}")
            return
        if self._avisos is None:
            self.control.append_log(
                "Este broker no ofrece avisos de cuenta: las ordenes se refrescan "
                "por sondeo (puede tardar unos segundos)."
            )
            return
        self._avisos.cambio.connect(self._refrescar_ordenes_ya)
        # camino rapido: el aviso ya trae la orden (o su estado), asi que la pantalla
        # se actualiza con ESO, sin esperar la lectura ni gastar una llamada
        self._avisos.orden.connect(self._aviso_de_orden)
        self._avisos.start()
        self.control.append_log("Avisos de cuenta activos: las ordenes aparecen al instante.")

    def _refrescar_ordenes_ya(self) -> None:
        if getattr(self, "_market_worker", None) is not None:
            self._market_worker.refrescar_ya()

    def _aviso_de_orden(self, oid, estado, orden) -> None:
        """Llega con lo que el broker mando en el aviso. La lectura de respaldo se
        dispara igual (por 'cambio'): esto solo adelanta lo que ya sabemos."""
        if getattr(self, "_market_worker", None) is not None:
            self._market_worker.aplicar_aviso(oid, estado, orden)

    def _on_positions(self, positions) -> None:
        """Al abrir la app, avisa UNA vez si ya habia una posicion abierta de antes
        (ej. quedo de una sesion anterior o de un cierre inesperado)."""
        if self._pos_warned:
            return
        self._pos_warned = True
        if positions:
            resumen = ", ".join(f"{p.symbol} {p.quantity}" for p in positions)
            self.control.append_log(
                f"*** ATENCION: hay posicion(es) abierta(s) de antes: {resumen}. Revisala(s). ***"
            )

    def _on_closed_orders(self, closed) -> None:
        """Detecta ordenes cerradas NUEVAS: suena en las ejecuciones (si el check
        esta tildado) y avisa + suena en los RECHAZOS."""
        if self._closed_seen is None:
            self._closed_seen = {o.id for o in closed}  # baseline: no avisa por las viejas
            return
        for o in closed:
            if o.id in self._closed_seen:
                continue
            self._closed_seen.add(o.id)
            if o.status == OrderStatus.FILLED:
                if self.control.chk_sound.isChecked():
                    sonar_ejecucion()
            elif o.status == OrderStatus.REJECTED:
                self.control.append_log(
                    f"*** Orden RECHAZADA: {o.side.value} {o.quantity} {o.symbol} "
                    f"@ {o.price:.2f} ***"
                )

    def _cambiar_tema(self) -> None:
        aplicar_tema(not es_oscuro())
        self._actualizar_boton_tema()
        # el ladder y la cinta pintan sus celdas a mano: hay que redibujarlas para
        # que tomen los colores del tema nuevo
        self.ladder.repintar_por_tema()
        self.tape.repintar_por_tema()
        self.monitor.repintar_por_tema()

    def _actualizar_boton_tema(self) -> None:
        self.btn_tema.setText("Modo claro" if es_oscuro() else "Modo oscuro")

    def _actualizar_conexion(self) -> None:
        if self._stream is None:
            self.lbl_conexion.setText("streaming: no disponible")
            return
        estado = self._stream.estado()
        textos = {
            "conectado": "streaming: conectado",
            "reconectando": "streaming: intentando conectar...",
            "inactivo": "streaming: en espera",
        }
        self.lbl_conexion.setText(textos.get(estado, f"streaming: {estado}"))

    def _set_ladder_symbol(self, sym: str) -> None:
        self.tape.set_symbol(sym)          # la cinta sigue al simbolo del ladder
        if self._stream is not None:
            self._stream.set_symbol(sym)                       # tiempo real
        # SIEMPRE tambien por REST: el streaming solo manda datos cuando el precio
        # cambia, asi que en acciones poco liquidas la escalera puede tardar minutos
        # en aparecer (o no aparecer). El pedido por REST la llena al instante y la
        # mantiene fresca; el streaming sigue dando el tiempo real cuando hay movimiento.
        if getattr(self, "_market_worker", None) is not None:
            self._market_worker.set_ladder_symbol(sym)

    def closeEvent(self, e) -> None:
        # recordar como dejaste las columnas (anchos y orden) para la proxima vez
        guardar_splitter(self._splitter)
        guardar_columnas(self.monitor.tbl_pos, self.monitor.tbl_ord,
                         self.monitor.tbl_exec, self.monitor.tbl_canc,
                         self.ladder.tabla, self.tape.tabla)
        if self._runner is not None:
            self._runner.stop()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
        if self._market_worker is not None:
            self._market_worker.stop()
        if self._market_thread is not None:
            self._market_thread.quit()
            self._market_thread.wait(3000)
        self.ladder.detener()      # hilo que manda/mueve/cancela desde el ladder
        if self._stream is not None:
            self._stream.stop()
        if self._avisos is not None:
            self._avisos.stop()
        try:
            from ..connectors.alpaca import detener_streams_de_cuenta
            detener_streams_de_cuenta()
        except Exception:  # noqa: BLE001
            pass
        e.accept()
