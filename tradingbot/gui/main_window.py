"""
Ventana principal de la app: el cartel de broker + cuenta (PAPER/LIVE) arriba y
las tres zonas (control / monitoreo / ladder) con divisores arrastrables.

Habla SIEMPRE con NUESTRO motor (core/engine.py) y NUESTRA interfaz comun
(core/broker.py). El broker concreto lo define el Perfil elegido al abrir
(Tradier, Alpaca...): la ventana no sabe con cual esta hablando.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtWidgets import (
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
from .estado_ui import guardar_columnas, guardar_splitter, restaurar_splitter
from .tema import aplicar_tema, es_oscuro
from ..core.models import OrderStatus, Side
from .sonidos import sonar_alerta, sonar_ejecucion

import configparser
import os


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
    t.setStyleSheet("font-weight: bold; font-size: 13px;")
    desc = QLabel(descripcion)
    desc.setWordWrap(True)
    desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    desc.setStyleSheet("color: palette(mid);")

    lay.addWidget(t)
    lay.addWidget(desc)
    lay.addStretch()
    return marco


class MainWindow(QMainWindow):
    def __init__(self, perfil: Perfil) -> None:
        super().__init__()
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
        self._set_running(False)

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

        aplicar_tema(es_oscuro())          # el tema que elegiste la vez pasada
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
        self._runner = BotRunner(broker, config, symbols)
        self._runner.moveToThread(self._thread)
        self._runner.log.connect(self.control.append_log)
        self._runner.manual.connect(self._on_manual)
        self._runner.finished.connect(self._on_finished)
        self._thread.started.connect(self._runner.run)
        self._thread.start()
        self._set_running(True)

    def _detener(self) -> None:
        if self._runner is not None:
            self.control.append_log("Deteniendo (al terminar la accion en curso)...")
            self._runner.stop()

    def _pausar(self) -> None:
        if self._runner is not None:
            self._runner.pause()
            self.control.append_log("Pausado (entre simbolos).")

    def _reanudar(self) -> None:
        if self._runner is not None:
            self._runner.resume()
            self.control.append_log("Reanudado.")

    def _on_manual(self, sym: str, por_guardia: bool = False) -> None:
        """El bot dejo una posicion abierta para cerrar a mano (guardia disparado o
        los niveles no cerraron): traigo ese simbolo al ladder solo, asi lo tenes
        listo para operar sin tener que buscarlo y cargarlo. Si fue el GUARDIA y la
        opcion esta tildada, ademas suena la alarma continua hasta que confirmes."""
        if not sym:
            return
        self.ladder.cargar_symbol(sym)
        self.control.append_log(f"Ladder: cargue {sym} solo (quedo para cerrar a mano).")
        if por_guardia and self.control.chk_guard_alarma.isChecked():
            self._alarma_guardia(sym)

    def _alarma_guardia(self, sym: str) -> None:
        """Alarma sostenida del guardia: suena repetida hasta que aceptes el cartel."""
        timer = QTimer(self)
        timer.setInterval(1200)
        timer.timeout.connect(sonar_alerta)
        timer.start()
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
        timer.stop()
        timer.deleteLater()

    def _on_finished(self, outcome: str) -> None:
        self.control.append_log(f"Bot finalizo: {outcome}")
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._runner = None
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self.control.btn_iniciar.setEnabled(not running)
        self.control.btn_pausar.setEnabled(running)
        self.control.btn_reanudar.setEnabled(running)
        self.control.btn_detener.setEnabled(running)

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
        self._market_worker.quote.connect(self.ladder.actualizar_quote)
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
        self._stream.quote.connect(self.ladder.actualizar_quote)
        # Time & Sales: el mismo stream ya abierto trae las operaciones ejecutadas
        self._stream.quote.connect(self.tape.actualizar_quote)
        self._stream.trade.connect(self.tape.agregar_trade)
        self.control.append_log("Streaming en vivo activo (produccion, SOLO lectura de precios).")

    def _arrancar_avisos(self) -> None:
        """Canal de avisos del broker: cuando una orden cambia de estado, refresca
        el monitoreo y el ladder EN EL MOMENTO (medido: ~200 ms) en vez de esperar
        el sondeo de cada 4 segundos."""
        try:
            self._avisos = self._perfil.crear_avisos()
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
        self._avisos.start()
        self.control.append_log("Avisos de cuenta activos: las ordenes aparecen al instante.")

    def _refrescar_ordenes_ya(self) -> None:
        if getattr(self, "_market_worker", None) is not None:
            self._market_worker.refrescar_ya()

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
