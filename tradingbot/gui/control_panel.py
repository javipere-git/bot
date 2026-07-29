"""
Panel de Control del bot (zona izquierda).

Por ahora arma TODOS los controles visuales: watchlist, parametros de entrada,
filtro de spread, opciones, cierre automatico de 4 niveles, guardia de
movimiento en contra, botones (Iniciar/Pausar/Reanudar/Detener) y el registro.

Todavia NO esta cableado al motor: los botones solo escriben en el log. El
cableado al cerebro (tradingbot/core/engine.py) viene en el paso siguiente.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.config import (
    EngineConfig,
    ExitLevel,
    GuardAction,
    GuardConfig,
    GuardReference,
    GuardUnit,
    OffsetUnit,
    OrderConfig,
)
from ..core.models import Side
from ..core.watchlist import parse_watchlist


def _spin(minimum, maximum, value, decimals=2, step=0.01, suffix=""):
    s = QDoubleSpinBox()
    s.setRange(minimum, maximum)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setValue(value)
    if suffix:
        s.setSuffix(suffix)
    s.setMaximumWidth(90)
    return s


class ControlPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.exit_rows: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        titulo = QLabel("Control del bot")
        titulo.setStyleSheet("font-weight: bold; font-size: 13px;")
        root.addWidget(titulo)

        # --- zona scrolleable con toda la configuracion ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cont = QWidget()
        cfg = QVBoxLayout(cont)
        cfg.setContentsMargins(0, 0, 0, 0)
        cfg.setSpacing(6)
        cfg.addWidget(self._grupo_watchlist())
        cfg.addWidget(self._grupo_entrada())
        cfg.addWidget(self._grupo_opciones())
        cfg.addWidget(self._grupo_cierre())
        cfg.addWidget(self._grupo_guardia())
        cfg.addStretch()
        scroll.setWidget(cont)
        root.addWidget(scroll, 1)

        # --- botones ---
        root.addLayout(self._botones())

        # --- registro (log) ---
        root.addWidget(QLabel("Registro:"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setMinimumHeight(110)
        root.addWidget(self.log)

        self.append_log("Listo. Carga la watchlist, configura y apreta Iniciar.")

    # ---------- grupos de configuracion ----------
    def _grupo_watchlist(self) -> QGroupBox:
        g = QGroupBox("Watchlist")
        lay = QVBoxLayout(g)
        self.txt_watchlist = QPlainTextEdit()
        self.txt_watchlist.setPlaceholderText(
            "Simbolos separados por espacio, coma, ; o salto de linea"
        )
        self.txt_watchlist.setMaximumHeight(80)
        lay.addWidget(self.txt_watchlist)
        self.btn_cargar = QPushButton("Cargar archivo...")
        self.btn_cargar.clicked.connect(self._cargar_archivo)
        lay.addWidget(self.btn_cargar)
        return g

    def _grupo_entrada(self) -> QGroupBox:
        g = QGroupBox("Entrada")
        form = QFormLayout(g)

        self.spin_cant = QSpinBox()
        self.spin_cant.setRange(1, 1_000_000)
        self.spin_cant.setValue(50)
        form.addRow("Cantidad:", self.spin_cant)

        self.spin_timeout = _spin(0.1, 600, 1.0, decimals=1, step=0.5, suffix=" s")
        form.addRow("Timeout:", self.spin_timeout)

        self.combo_lado = QComboBox()
        self.combo_lado.addItems(["Compra (bid +)", "Venta (ask -)"])
        form.addRow("Lado:", self.combo_lado)

        o1 = QHBoxLayout()
        self.spin_o1 = _spin(-100, 100, 0.00)
        self.combo_o1 = QComboBox()
        self.combo_o1.addItems(["%", "$"])
        self.combo_o1.setToolTip("% del spread, o $ fijo")
        self.combo_o1.setMaximumWidth(60)
        o1.addWidget(self.spin_o1)
        o1.addWidget(self.combo_o1)
        form.addRow("Orden 1:", self._wrap(o1))

        self.chk_o2 = QCheckBox("Usar Orden 2")
        self.chk_o2.setChecked(True)
        form.addRow("", self.chk_o2)

        o2 = QHBoxLayout()
        self.spin_o2 = _spin(-100, 100, 0.00)
        self.combo_o2 = QComboBox()
        self.combo_o2.addItems(["%", "$"])
        self.combo_o2.setToolTip("% del spread, o $ fijo")
        self.combo_o2.setMaximumWidth(60)
        o2.addWidget(self.spin_o2)
        o2.addWidget(self.combo_o2)
        form.addRow("Orden 2:", self._wrap(o2))

        sp = QHBoxLayout()
        self.ed_spread_min = QLineEdit()
        self.ed_spread_min.setPlaceholderText("min")
        self.ed_spread_min.setMaximumWidth(70)
        self.ed_spread_max = QLineEdit()
        self.ed_spread_max.setPlaceholderText("max")
        self.ed_spread_max.setMaximumWidth(70)
        sp.addWidget(self.ed_spread_min)
        sp.addWidget(QLabel("a"))
        sp.addWidget(self.ed_spread_max)
        form.addRow("Spread $:", self._wrap(sp))

        vol = QHBoxLayout()
        self.ed_vol_min = QLineEdit()
        self.ed_vol_min.setPlaceholderText("min")
        self.ed_vol_min.setMaximumWidth(70)
        self.ed_vol_max = QLineEdit()
        self.ed_vol_max.setPlaceholderText("max")
        self.ed_vol_max.setMaximumWidth(70)
        vol.addWidget(self.ed_vol_min)
        vol.addWidget(QLabel("a"))
        vol.addWidget(self.ed_vol_max)
        caja_vol = self._wrap(vol)
        caja_vol.setToolTip(
            "Volumen TOTAL operado en el dia (acumulado hasta ese momento), en acciones.\n"
            "Los simbolos fuera del rango se saltean. Vacio = sin limite por ese lado."
        )
        form.addRow("Volumen dia:", caja_vol)
        return g

    def _grupo_opciones(self) -> QGroupBox:
        g = QGroupBox("Opciones")
        lay = QVBoxLayout(g)
        self.chk_pause = QCheckBox("Pausar al ejecutar una orden")
        self.chk_pause.setChecked(True)
        self.chk_pause.setToolTip(
            "Tras CERRAR una posicion, el bot se pausa; lo reanudas vos para seguir "
            "con el siguiente simbolo. Destildado: sigue solo."
        )
        self.chk_loop = QCheckBox("Repetir watchlist (loop)")
        self.chk_loop.setChecked(True)
        self.chk_loop.setToolTip(
            "Tildado: recorre la lista una y otra vez hasta Detener. "
            "Destildado: una pasada y se detiene."
        )
        self.chk_ext = QCheckBox("Extended hours (pre/post)")
        self.chk_sound = QCheckBox("Sonido al ejecutar")
        for c in (self.chk_pause, self.chk_loop, self.chk_ext, self.chk_sound):
            lay.addWidget(c)
        return g

    def _grupo_cierre(self) -> QGroupBox:
        g = QGroupBox("Cierre automatico (4 niveles)")
        g.setCheckable(True)
        g.setChecked(False)
        self.grp_cierre = g
        lay = QVBoxLayout(g)

        grid = QGridLayout()
        for col, txt in enumerate(["", "Offset", "Unid", "Timeout", "Cruzar"]):
            grid.addWidget(QLabel(txt), 0, col)
        for i in range(1, 5):
            chk = QCheckBox()
            off = _spin(-100, 100, 0.0)
            uni = QComboBox()
            uni.addItems(["%", "$"])
            uni.setMaximumWidth(55)
            tmo = _spin(0.1, 600, 1.0, decimals=1, step=0.5)
            cross = QCheckBox()
            grid.addWidget(chk, i, 0)
            grid.addWidget(off, i, 1)
            grid.addWidget(uni, i, 2)
            grid.addWidget(tmo, i, 3)
            grid.addWidget(cross, i, 4)
            self.exit_rows.append(
                {"on": chk, "off": off, "uni": uni, "tmo": tmo, "cross": cross}
            )
        lay.addLayout(grid)

        wait = QHBoxLayout()
        self.spin_wait = _spin(0, 600, 0.0, decimals=1, step=0.5, suffix=" s")
        wait.addWidget(QLabel("Espera antes de cubrir:"))
        wait.addWidget(self.spin_wait)
        lay.addLayout(wait)

        self.chk_no_perder = QCheckBox("No cerrar a peor precio que el promedio (salvo cruzar)")
        self.chk_no_perder.setChecked(True)
        self.chk_no_perder.setToolTip(
            "Los escalones normales nunca mandan una orden por debajo del promedio\n"
            "(si estas largo) o por encima (si estas corto). Para salir con perdida\n"
            "esta 'Cruzar', que ignora este tope. Si un escalon queda topado al\n"
            "promedio, no se reprecia hasta que cambie."
        )
        lay.addWidget(self.chk_no_perder)

        for fila in self.exit_rows:
            fila["cross"].toggled.connect(self._actualizar_niveles)
            fila["on"].toggled.connect(self._actualizar_niveles)
        self._actualizar_niveles()
        return g

    def _grupo_guardia(self) -> QGroupBox:
        g = QGroupBox("Guardia de movimiento en contra")
        g.setCheckable(True)
        g.setChecked(False)
        self.grp_guard = g
        form = QFormLayout(g)

        gu = QHBoxLayout()
        self.spin_guard = _spin(0, 100, 0.25)
        self.combo_guard_uni = QComboBox()
        self.combo_guard_uni.addItems(["$", "%"])
        self.combo_guard_uni.setToolTip("$ (centavos) o % del precio")
        self.combo_guard_uni.setMaximumWidth(60)
        gu.addWidget(self.spin_guard)
        gu.addWidget(self.combo_guard_uni)
        form.addRow("Umbral:", self._wrap(gu))

        self.combo_guard_act = QComboBox()
        self.combo_guard_act.addItems(
            ["Pasar a manual (A)", "Salida forzada (B)", "Seguir (C)"]
        )
        form.addRow("Si se dispara:", self.combo_guard_act)

        self.combo_guard_ref = QComboBox()
        self.combo_guard_ref.addItems(
            ["Precio de calculo de la entrada", "Precio al iniciar el cierre"]
        )
        self.combo_guard_ref.setToolTip(
            "Desde donde se mide el umbral:\n"
            "- Precio de calculo de la entrada: el bid (largo) / ask (corto) con el que\n"
            "  se calculo la orden de entrada. Si el precio se desploma JUSTO al entrar,\n"
            "  el guardia lo ve y salta.\n"
            "- Precio al iniciar el cierre: el bid/ask leido al arrancar la salida\n"
            "  (comportamiento anterior); un golpe en el instante de la entrada no lo ve."
        )
        form.addRow("Referencia:", self.combo_guard_ref)

        self.chk_guard_alarma = QCheckBox("Alarma continua hasta confirmar")
        self.chk_guard_alarma.setChecked(True)
        self.chk_guard_alarma.setToolTip(
            "Si el guardia se dispara: la alarma suena REPETIDA y aparece un cartel;\n"
            "no se apaga hasta que aprietes Aceptar. Destildado: un solo aviso, como siempre."
        )
        form.addRow("", self.chk_guard_alarma)
        return g

    def _botones(self) -> QHBoxLayout:
        lay = QHBoxLayout()
        self.btn_iniciar = QPushButton("Iniciar")
        self.btn_pausar = QPushButton("Pausar")
        self.btn_reanudar = QPushButton("Reanudar")
        self.btn_detener = QPushButton("Detener")
        for b in (self.btn_iniciar, self.btn_pausar, self.btn_reanudar, self.btn_detener):
            lay.addWidget(b)
        return lay

    # ---------- logica de niveles / config ----------
    def _actualizar_niveles(self) -> None:
        """Si un nivel de cierre tiene 'cruzar' tildado, deshabilita los niveles
        siguientes (una vez que se cruza el spread, la posicion ya se cierra)."""
        cortar = False
        for fila in self.exit_rows:
            habilitado = not cortar
            for k in ("on", "off", "uni", "tmo", "cross"):
                fila[k].setEnabled(habilitado)
            if not cortar and fila["on"].isChecked() and fila["cross"].isChecked():
                cortar = True

    def get_symbols(self) -> list[str]:
        return parse_watchlist(self.txt_watchlist.toPlainText())

    def _cargar_archivo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Cargar watchlist", "",
            "Texto (*.txt *.csv);;Todos los archivos (*)",
        )
        if not ruta:
            return
        try:
            with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
                contenido = f.read()
        except Exception as e:  # noqa: BLE001
            self.append_log(f"No pude leer el archivo: {e}")
            return
        simbolos = parse_watchlist(contenido)
        if not simbolos:
            self.append_log("El archivo no tenia simbolos reconocibles.")
            return
        self.txt_watchlist.setPlainText(" ".join(simbolos))
        self.append_log(f"Cargados {len(simbolos)} simbolos del archivo.")

    def build_config(self) -> EngineConfig:
        """Arma la configuracion del motor leyendo todos los campos del panel."""
        side = Side.BUY if self.combo_lado.currentIndex() == 0 else Side.SELL_SHORT
        timeout = self.spin_timeout.value()
        order1 = OrderConfig(self.spin_o1.value(), self._unit(self.combo_o1), timeout)
        order2 = None
        if self.chk_o2.isChecked():
            order2 = OrderConfig(self.spin_o2.value(), self._unit(self.combo_o2), timeout)

        exit_levels: list[ExitLevel] = []
        if self.grp_cierre.isChecked():
            for fila in self.exit_rows:
                if not fila["on"].isChecked():
                    continue
                cross = fila["cross"].isChecked()
                exit_levels.append(
                    ExitLevel(fila["off"].value(), self._unit(fila["uni"]),
                              fila["tmo"].value(), enabled=True, cross=cross)
                )
                if cross:
                    break  # despues de cruzar, los niveles siguientes no se usan

        guard = None
        if self.grp_guard.isChecked():
            gunit = (GuardUnit.DOLLARS if self.combo_guard_uni.currentText() == "$"
                     else GuardUnit.PERCENT)
            gact = [GuardAction.MANUAL, GuardAction.FORCE_EXIT, GuardAction.CONTINUE][
                self.combo_guard_act.currentIndex()
            ]
            gref = (GuardReference.ENTRY_CALC if self.combo_guard_ref.currentIndex() == 0
                    else GuardReference.EXIT_START)
            guard = GuardConfig(self.spin_guard.value(), gunit, gact, reference=gref)

        return EngineConfig(
            side=side,
            quantity=self.spin_cant.value(),
            order1=order1,
            order2=order2,
            spread_min=self._parse_float(self.ed_spread_min.text()),
            spread_max=self._parse_float(self.ed_spread_max.text()),
            extended_hours=self.chk_ext.isChecked(),
            volume_min=self._parse_int(self.ed_vol_min.text()),
            volume_max=self._parse_int(self.ed_vol_max.text()),
            exit_levels=exit_levels,
            wait_before_exit_s=self.spin_wait.value() if self.grp_cierre.isChecked() else 0.0,
            no_cerrar_bajo_promedio=self.chk_no_perder.isChecked(),
            guard=guard,
            pause_on_fill=self.chk_pause.isChecked(),
            loop_watchlist=self.chk_loop.isChecked(),
        )

    @staticmethod
    def _unit(combo) -> OffsetUnit:
        return OffsetUnit.DOLLARS if combo.currentText() == "$" else OffsetUnit.PERCENT_SPREAD

    @staticmethod
    def _parse_float(txt: str):
        txt = txt.strip().replace(",", ".")
        if not txt:
            return None
        try:
            return float(txt)
        except ValueError:
            return None

    @staticmethod
    def _parse_int(txt: str):
        """Cantidad de acciones. Acepta 100000, 100.000, 100,000 o '100 000'."""
        txt = txt.strip().replace(".", "").replace(",", "").replace(" ", "")
        if not txt:
            return None
        try:
            return int(txt)
        except ValueError:
            return None

    # ---------- helpers ----------
    @staticmethod
    def _wrap(layout) -> QWidget:
        w = QWidget()
        layout.setContentsMargins(0, 0, 0, 0)
        w.setLayout(layout)
        return w

    def append_log(self, msg: str) -> None:
        self.log.appendPlainText(msg)
        from ..registro import log as log_archivo
        log_archivo(msg)  # todo lo del registro de pantalla queda tambien en el archivo
        if "***" in msg:  # alertas (paso a manual / bot detenido) -> sonido de alerta
            from .sonidos import sonar_alerta
            sonar_alerta()
