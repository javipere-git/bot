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
from PySide6.QtGui import QGuiApplication
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
from ..core import excluidas, watchlists
from ..core.models import Side
from ..core.watchlist import parse_watchlist
from .estado_ui import guardar_tilde, leer_tilde, poner_titulo


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
    def __init__(self, parent=None, ruta_watchlists: str | None = None) -> None:
        super().__init__(parent)
        self.exit_rows: list[dict] = []
        # lo completa la ventana principal (es la unica que tiene el broker):
        # recibe el dialogo de excluidas y le carga las bloqueadas cuando lleguen
        self.traer_bloqueadas = None
        # None = el archivo de siempre (config/watchlists.txt). Los tests le pasan
        # uno temporal para no pisar el tuyo.
        self._ruta_wl = ruta_watchlists

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        titulo = QLabel("Control del bot")
        poner_titulo(titulo)
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

        # --- registro (log) + descarga de reportes de pasadas ---
        fila_reg = QHBoxLayout()
        fila_reg.addWidget(QLabel("Registro:"))
        fila_reg.addStretch(1)
        self.combo_reportes = QComboBox()
        self.combo_reportes.setMinimumWidth(190)
        self.combo_reportes.setToolTip(
            "Elegi una pasada (por su horario de inicio-fin) o el resumen del dia, "
            "y apreta Abrir.\n\n"
            "Cada pasada es una corrida completa, de Iniciar a Detener. Su reporte ya "
            "quedo guardado en la carpeta 'reportes' al terminar; el boton lo abre.\n"
            "El resumen del dia se genera, se guarda y se abre al pedirlo."
        )
        self.btn_descargar_reporte = QPushButton("Abrir")
        self.btn_descargar_reporte.setToolTip(
            "Abre el reporte elegido. Las pasadas ya estan guardadas en 'reportes'; "
            "el resumen del dia se arma en el momento, se guarda y se abre."
        )
        self.btn_descargar_reporte.setEnabled(False)   # se habilita cuando hay pasadas
        self.btn_operaciones = QPushButton("Reportes")
        self.btn_operaciones.setToolTip(
            "Baja a un archivo (se abre con Excel) lo que el broker tiene de la\n"
            "cuenta entre dos fechas. Tres reportes, que contestan tres preguntas:\n\n"
            "  TRADES CERRADOS - entrada + salida + resultado de cada operacion.\n"
            "     Es el unico que dice como te fue.\n"
            "  EJECUCIONES     - lo que de verdad se opero, pedazo por pedazo.\n"
            "  ORDENES         - lo que pediste, se haya hecho o no: cuales se\n"
            "     cancelaron, cuales se rechazaron y por que. Se puede filtrar\n"
            "     por estado.\n\n"
            "Sale del broker donde OPERAS, e incluye lo que hayas operado a mano o\n"
            "desde otra PC. Es lo que la pagina del broker no te deja bajar de una."
        )
        fila_reg.addWidget(self.combo_reportes)
        fila_reg.addWidget(self.btn_descargar_reporte)
        fila_reg.addWidget(self.btn_operaciones)
        root.addLayout(fila_reg)

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
        self.txt_watchlist.setMaximumHeight(102)

        # A la derecha del campo, los accesos a las watchlists guardadas. El campo
        # sigue siendo el que manda: estos botones SOLO lo llenan, asi que todo lo
        # de siempre (escribir a mano, cargar un archivo, pegar) funciona igual.
        con_wl = QHBoxLayout()
        con_wl.addWidget(self.txt_watchlist, 1)
        columna = QVBoxLayout()
        columna.setSpacing(2)
        self.btn_wl = []
        for i in range(watchlists.CUANTAS):
            b = QPushButton(f"WL {i + 1}")
            b.setFixedHeight(24)
            b.clicked.connect(lambda _=False, n=i: self._cargar_wl(n))
            columna.addWidget(b)
            self.btn_wl.append(b)
        self.btn_wl_config = QPushButton("⚙")      # ruedita
        self.btn_wl_config.setFixedHeight(24)
        self.btn_wl_config.setToolTip(
            "Precargar las watchlists de los botones WL y ponerles nombre.\n\n"
            "Adentro hay un boton para guardar de una la lista que tengas AHORA\n"
            "en la pantalla (por ejemplo, la que trajo el boton de ETB)."
        )
        self.btn_wl_config.clicked.connect(self._editar_wl)
        columna.addWidget(self.btn_wl_config)
        con_wl.addLayout(columna)
        lay.addLayout(con_wl)
        self._refrescar_wl()
        # Cargar archivo (mitad del ancho) + Limpiar y Pegar (un cuarto cada uno)
        fila_botones = QHBoxLayout()
        self.btn_cargar = QPushButton("Cargar archivo...")
        self.btn_cargar.clicked.connect(self._cargar_archivo)
        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.setToolTip("Borra todos los simbolos de la watchlist.")
        self.btn_limpiar.clicked.connect(self._limpiar_watchlist)
        self.btn_pegar = QPushButton("Pegar")
        self.btn_pegar.setToolTip("Pega los simbolos que tengas copiados en el portapapeles.")
        self.btn_pegar.clicked.connect(self._pegar_watchlist)
        # los factores de estiramiento reparten el ancho: 2 + 1 + 1 = 1/2, 1/4, 1/4
        fila_botones.addWidget(self.btn_cargar, 2)
        fila_botones.addWidget(self.btn_limpiar, 1)
        fila_botones.addWidget(self.btn_pegar, 1)
        lay.addLayout(fila_botones)

        # Easy To Borrow: las acciones que el broker DONDE OPERAS deja vender en corto.
        # Los cuatro botones van en UNA linea: medidos con la letra de Windows piden
        # 394 pixeles y el panel ya reserva 419, asi que entran enteros.
        etb = QHBoxLayout()
        self.btn_etb_cargar = QPushButton("Cargar lista ETB")
        self.btn_etb_bajar = QPushButton("Descargar lista ETB")
        AYUDA_ETB = (
            "ETB = Easy To Borrow: las acciones que se pueden vender en CORTO.\n\n"
            "La lista se pide al broker donde OPERAS, no al que da los precios. Con el "
            "perfil 'Alpaca con datos de Tradier' trae la lista de ALPACA, que es quien "
            "acepta o rechaza el short.\n\n"
            "En Alpaca, ademas, las ETB no pagan costo de prestamo, y las que NO estan "
            "en la lista directamente no se pueden shortear."
        )
        for b in (self.btn_etb_cargar, self.btn_etb_bajar):
            b.setToolTip(AYUDA_ETB)
            etb.addWidget(b)

        self.btn_excluidas = QPushButton("Excluidas")
        self.btn_excluidas.setToolTip(
            "Simbolos que el bot NO va a operar, aunque esten en la watchlist.\n\n"
            "Son dos listas separadas: las TUYAS (por el motivo que sea) y las que\n"
            "el BROKER tiene bloqueadas. Asi podes renovar la del broker sin volver\n"
            "a cargar las tuyas.\n\n"
            "Se guardan en config/excluidas.txt, que viaja con el repositorio: la\n"
            "misma lista te sigue a las otras PCs."
        )
        self.btn_excluidas.clicked.connect(self._editar_excluidas)
        self.btn_catalogo = QPushButton("Bajar catalogo")
        self.btn_catalogo.setToolTip(
            "Baja a un archivo (se abre con Excel) TODO lo que el broker donde operas\n"
            "sabe de cada simbolo: si esta bloqueado para abrir, si es prestable, su\n"
            "costo de prestamo, si lo marca iliquido...\n\n"
            "Sirve para mirarlo con calma y decidir que poner en las excluidas."
        )
        etb.addWidget(self.btn_excluidas)
        etb.addWidget(self.btn_catalogo)
        lay.addLayout(etb)
        return g

    # ---------- watchlists guardadas ----------
    def _refrescar_wl(self) -> None:
        """Pone en cada boton su ayuda: el nombre y cuantos simbolos tiene.

        En la pantalla el boton dice 'WL 1' por una cuestion de lugar; el nombre
        que le pusiste aparece al pasarle el mouse por encima."""
        for i, (nombre, simbolos) in enumerate(watchlists.leer(self._ruta_wl)):
            if i >= len(self.btn_wl):
                break
            b = self.btn_wl[i]
            b.setEnabled(bool(simbolos))
            if simbolos:
                b.setToolTip(f"{nombre}\n\n{len(simbolos):,} simbolo(s). "
                             f"Al apretar, reemplaza lo que haya en la watchlist.\n"
                             f"{' '.join(simbolos[:12])}"
                             f"{'...' if len(simbolos) > 12 else ''}")
            else:
                b.setToolTip(f"{nombre}: vacia.\n"
                             f"Cargala con el boton de la ruedita.")

    def _cargar_wl(self, i: int) -> None:
        listas = watchlists.leer(self._ruta_wl)
        if i >= len(listas):
            return
        nombre, simbolos = listas[i]
        if not simbolos:
            self.append_log(f"WL {i + 1} ({nombre}) esta vacia. "
                            f"Cargala con el boton de la ruedita.")
            return
        self.txt_watchlist.setPlainText(" ".join(simbolos))
        self.append_log(f"Watchlist cargada desde WL {i + 1} ({nombre}): "
                        f"{len(simbolos):,} simbolo(s).")

    def _editar_wl(self) -> None:
        from .watchlists_dialog import DialogoWatchlists
        dlg = DialogoWatchlists(self, ruta=self._ruta_wl,
                                en_pantalla=self.txt_watchlist.toPlainText())
        if dlg.exec():
            listas = dlg.listas()
            ruta = watchlists.guardar(listas, self._ruta_wl)
            self._refrescar_wl()
            detalle = ", ".join(f"WL {i + 1} ({n}): {len(s)}"
                                for i, (n, s) in enumerate(listas) if s) or "todas vacias"
            self.append_log(f"Watchlists guardadas: {detalle}. En {ruta}")

    def _editar_excluidas(self) -> None:
        from .excluidas_dialog import DialogoExcluidas
        dlg = DialogoExcluidas(self)
        if self.traer_bloqueadas is None:
            # sin ventana principal (o sin broker) el boton no tiene a quien preguntarle
            dlg.btn_traer.setEnabled(False)
            dlg.btn_traer.setToolTip("Sin conexion con el broker.")
        else:
            dlg.btn_traer.clicked.connect(lambda: self.traer_bloqueadas(dlg))
        if dlg.exec():
            mias, broker = dlg.listas()
            ruta = excluidas.guardar(mias, broker)
            detalle = ", ".join(f"{n}: {len(s)}" for n, s in mias if s) or "ninguna tuya"
            self.append_log(
                f"Excluidas: {detalle} | del broker: {len(broker)}. "
                f"En total {len(excluidas.todas(dlg.ruta)):,} simbolo(s). "
                f"Guardado en {ruta}"
            )

    def _grupo_entrada(self) -> QGroupBox:
        g = QGroupBox("Entrada")
        form = QFormLayout(g)

        self.spin_cant = QSpinBox()
        self.spin_cant.setRange(1, 1_000_000)
        self.spin_cant.setValue(50)
        self.spin_cant.setMaximumWidth(90)
        form.addRow("Cantidad:", self._wrap_izq(self.spin_cant))

        # Pausa antes de entrar a un simbolo nuevo. 0 = apagada (como siempre).
        self.spin_pausa = _spin(0.0, 60, 0.0, decimals=1, step=0.5, suffix=" s")
        self.spin_pausa.setMaximumWidth(90)
        self.spin_pausa.setToolTip(
            "Espera despues de que el simbolo pasa los filtros y ANTES de mandar la\n"
            "orden (con cotizacion fresca). Sirve para brokers que tardan en liberar\n"
            "el poder de compra de la orden anterior, como Tastytrade.\n"
            "0 = sin pausa, el bot va de un simbolo al otro como siempre."
        )
        form.addRow("Pausa nuevo simbolo:", self._wrap_izq(self.spin_pausa))

        self.combo_lado = QComboBox()
        self.combo_lado.addItems(["Compra (bid +)", "Venta (ask -)"])
        self.combo_lado.setMaximumWidth(130)
        form.addRow("Lado:", self._wrap_izq(self.combo_lado))

        # Cada orden con su propio timeout: cuanto se la deja viva antes de pasar a
        # la siguiente. El motor ya lo soportaba (OrderConfig.timeout_s); antes la
        # pantalla le mandaba el mismo valor a las dos.
        o1 = QHBoxLayout()
        self.spin_o1 = _spin(-100, 100, 0.00)
        self.combo_o1 = QComboBox()
        self.combo_o1.addItems(["%", "$"])
        self.combo_o1.setToolTip("% del spread, o $ fijo")
        self.combo_o1.setMaximumWidth(60)
        self.spin_to1 = _spin(0.1, 600, 1.5, decimals=1, step=0.5, suffix=" s")
        self.spin_to1.setMaximumWidth(80)
        self.spin_to1.setToolTip("Cuanto espera el llenado de la Orden 1 antes de\n"
                                 "pasar a la Orden 2 (o de cancelar, si no hay 2)")
        o1.addWidget(self.spin_o1)
        o1.addWidget(self.combo_o1)
        o1.addWidget(self.spin_to1)
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
        self.spin_to2 = _spin(0.1, 600, 1.5, decimals=1, step=0.5, suffix=" s")
        self.spin_to2.setMaximumWidth(80)
        self.spin_to2.setToolTip("Cuanto espera el llenado de la Orden 2 antes de\n"
                                 "cancelar y pasar al simbolo siguiente")
        o2.addWidget(self.spin_o2)
        o2.addWidget(self.combo_o2)
        o2.addWidget(self.spin_to2)
        self._fila_o2 = self._wrap(o2)
        form.addRow("Orden 2:", self._fila_o2)
        # si la Orden 2 no se usa, su fila queda apagada (se ve que no aplica)
        self._lbl_o2 = form.labelForField(self._fila_o2)
        self.chk_o2.toggled.connect(self._habilitar_orden2)
        self._habilitar_orden2(self.chk_o2.isChecked())

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

        AYUDA_MOV = (
            "Cuantas VECES se movio ese precio (no importa cuanto). Sirve para "
            "saltear acciones nerviosas: una que hace 10 minutos esta clavada en "
            "100.00 x 100.50 no es lo mismo que una que se mueve cada 2 segundos.\n\n"
            "Se mide justo ANTES de operar cada simbolo, contando los segundos "
            "literalmente hacia atras desde ese momento. Si se movio MAS veces que "
            "el tope, saltea el simbolo.\n\n"
            "El bid y el ask van por separado: podes usar los dos, uno solo, o "
            "ninguno. Vacio = ese lado no filtra nada.\n\n"
            "Necesita el streaming conectado."
        )
        self.ed_mov_bid_max, self.ed_mov_bid_seg = self._fila_movimiento(
            form, "Max cambios bid:", AYUDA_MOV
        )
        self.ed_mov_ask_max, self.ed_mov_ask_seg = self._fila_movimiento(
            form, "Max cambios ask:", AYUDA_MOV
        )

        spr = QHBoxLayout()
        self.ed_spr_pct = QLineEdit()
        self.ed_spr_pct.setPlaceholderText("%")
        self.ed_spr_pct.setMaximumWidth(50)
        self.ed_spr_seg = QLineEdit()
        self.ed_spr_seg.setPlaceholderText("seg")
        self.ed_spr_seg.setMaximumWidth(50)
        spr.addWidget(self.ed_spr_pct)
        spr.addWidget(QLabel("% del actual, en los ultimos"))
        spr.addWidget(self.ed_spr_seg)
        spr.addWidget(QLabel("segundos"))
        caja_spr = self._wrap(spr)
        caja_spr.setToolTip(
            "Saltea las acciones cuyo spread estuvo MUCHO mas ancho hace un rato que "
            "ahora (el spread actual es el que se usa para calcular la orden).\n\n"
            "Ejemplo con 150%: si el spread mas ancho de los ultimos 30s fue 0.20 y "
            "el actual es 0.10, eso es 200% -> SALTEA. Si el mas ancho hubiera sido "
            "0.14 (140%), entra.\n\n"
            "Se mide justo ANTES de operar cada simbolo, contando los segundos "
            "literalmente hacia atras.\n\n"
            "Necesita el streaming conectado. Vacio = filtro apagado."
        )
        form.addRow("Max spread:", caja_spr)

        vs = QHBoxLayout()
        self.ed_vol_seg_max = QLineEdit()
        self.ed_vol_seg_max.setPlaceholderText("max")
        self.ed_vol_seg_max.setMaximumWidth(70)
        self.ed_vol_seg_seg = QLineEdit()
        self.ed_vol_seg_seg.setPlaceholderText("seg")
        self.ed_vol_seg_seg.setMaximumWidth(50)
        vs.addWidget(self.ed_vol_seg_max)
        vs.addWidget(QLabel("acciones, en los ultimos"))
        vs.addWidget(self.ed_vol_seg_seg)
        vs.addWidget(QLabel("segundos"))
        caja_vs = self._wrap(vs)
        caja_vs.setToolTip(
            "Acciones OPERADAS en los ultimos segundos (no el volumen del dia). "
            "Saltea las acciones con demasiada actividad justo antes de entrar.\n\n"
            "Se mide justo ANTES de operar cada simbolo, contando los segundos "
            "literalmente hacia atras.\n\n"
            "OJO con el feed: el timesale de TRADIER viene muestreado (~7x menos "
            "operaciones que Alpaca SIP), asi que en Tradier el volumen contado sale "
            "por debajo del real. Como esto es un MAXIMO, quedarse corto hace que "
            "filtre de MENOS, nunca de mas: no saltea simbolos que si cumplian.\n\n"
            "Necesita el streaming conectado. Vacio = filtro apagado."
        )
        form.addRow("Max volumen:", caja_vs)

        spp = QHBoxLayout()
        self.ed_spr_pct_precio = QLineEdit()
        self.ed_spr_pct_precio.setPlaceholderText("%")
        self.ed_spr_pct_precio.setMaximumWidth(50)
        spp.addWidget(self.ed_spr_pct_precio)
        spp.addWidget(QLabel("% del precio"))
        spp.addStretch(1)
        caja_spp = self._wrap(spp)
        caja_spp.setToolTip(
            "Que tan ancho es el spread comparado con lo que VALE la accion.\n\n"
            "Un spread de 0.10 es angosto en una accion de 200 (0.05%) y carisimo en "
            "una de 1.00 (10%). Sirve para dejar afuera las iliquidas, donde el spread "
            "se come la ganancia.\n\n"
            "Ejemplo con 5: una accion 9.75 x 10.25 tiene spread 0.50 sobre un precio "
            "de 10.00 = 5% -> SALTEA (es 'igual o mayor'). Si el spread fuera 0.40 "
            "(4%), entra.\n\n"
            "El precio de referencia es el punto MEDIO entre bid y ask.\n\n"
            "Este NO necesita streaming: usa la cotizacion del momento. Vacio = "
            "filtro apagado."
        )
        form.addRow("Max spread:", caja_spp)
        return g

    def _fila_movimiento(self, form, etiqueta: str, ayuda: str):
        """Una linea del filtro de movimiento: [max] en los ultimos [seg] segundos."""
        fila = QHBoxLayout()
        ed_max = QLineEdit()
        ed_max.setPlaceholderText("max")
        ed_max.setMaximumWidth(50)
        ed_seg = QLineEdit()
        ed_seg.setPlaceholderText("seg")
        ed_seg.setMaximumWidth(50)
        fila.addWidget(ed_max)
        fila.addWidget(QLabel("en los ultimos"))
        fila.addWidget(ed_seg)
        fila.addWidget(QLabel("segundos"))
        caja = self._wrap(fila)
        caja.setToolTip(ayuda)
        form.addRow(etiqueta, caja)
        return ed_max, ed_seg

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
        # se recuerda entre sesiones: antes arrancaba apagado siempre y parecia
        # que los sonidos no funcionaban
        self.chk_sound.setChecked(leer_tilde("sonido_ejecucion", False))
        self.chk_sound.toggled.connect(
            lambda v: guardar_tilde("sonido_ejecucion", v))
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
        self.chk_guard_alarma.setChecked(leer_tilde("alarma_guardia", True))
        self.chk_guard_alarma.toggled.connect(
            lambda v: guardar_tilde("alarma_guardia", v))
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

    def _limpiar_watchlist(self) -> None:
        if not self.txt_watchlist.toPlainText().strip():
            return
        self.txt_watchlist.clear()
        self.append_log("Watchlist vaciada.")

    def _pegar_watchlist(self) -> None:
        texto = QGuiApplication.clipboard().text()
        simbolos = parse_watchlist(texto)
        if not simbolos:
            self.append_log("El portapapeles no tenia simbolos reconocibles.")
            return
        self.txt_watchlist.setPlainText(" ".join(simbolos))
        self.append_log(f"Pegados {len(simbolos)} simbolos del portapapeles.")

    def build_config(self) -> EngineConfig:
        """Arma la configuracion del motor leyendo todos los campos del panel."""
        side = Side.BUY if self.combo_lado.currentIndex() == 0 else Side.SELL_SHORT
        # cada orden con SU timeout (antes las dos compartian uno solo)
        order1 = OrderConfig(self.spin_o1.value(), self._unit(self.combo_o1),
                             self.spin_to1.value())
        order2 = None
        if self.chk_o2.isChecked():
            order2 = OrderConfig(self.spin_o2.value(), self._unit(self.combo_o2),
                                 self.spin_to2.value())

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
            pausa_simbolo_s=self.spin_pausa.value(),
            spread_min=self._parse_float(self.ed_spread_min.text()),
            spread_max=self._parse_float(self.ed_spread_max.text()),
            extended_hours=self.chk_ext.isChecked(),
            max_cambios_bid=self._parse_int(self.ed_mov_bid_max.text()),
            ventana_bid_s=float(self._parse_int(self.ed_mov_bid_seg.text()) or 30),
            max_cambios_ask=self._parse_int(self.ed_mov_ask_max.text()),
            ventana_ask_s=float(self._parse_int(self.ed_mov_ask_seg.text()) or 30),
            max_spread_pct=self._parse_float(self.ed_spr_pct.text()),
            ventana_spread_s=float(self._parse_int(self.ed_spr_seg.text()) or 30),
            max_volumen_seg=self._parse_int(self.ed_vol_seg_max.text()),
            ventana_volumen_s=float(self._parse_int(self.ed_vol_seg_seg.text()) or 30),
            volume_min=self._parse_int(self.ed_vol_min.text()),
            volume_max=self._parse_int(self.ed_vol_max.text()),
            max_spread_pct_precio=self._parse_float(self.ed_spr_pct_precio.text()),
            exit_levels=exit_levels,
            wait_before_exit_s=self.spin_wait.value() if self.grp_cierre.isChecked() else 0.0,
            no_cerrar_bajo_promedio=self.chk_no_perder.isChecked(),
            guard=guard,
            pause_on_fill=self.chk_pause.isChecked(),
            loop_watchlist=self.chk_loop.isChecked(),
            # se lee del archivo en el momento de arrancar: si las editas con el bot
            # detenido y volves a arrancar, ya rigen las nuevas
            excluidas=excluidas.todas(),
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

    @staticmethod
    def _wrap_izq(widget) -> QWidget:
        """Deja el campo con su ancho y el resto vacio, en vez de estirarlo a lo
        ancho de la columna (cantidad, pausa y lado no necesitan tanto lugar)."""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(widget)
        lay.addStretch(1)
        return w

    def _habilitar_orden2(self, activo: bool) -> None:
        """Apaga la fila de la Orden 2 cuando no se usa, para que se vea que no
        aplica (antes quedaba editable aunque el bot la ignorara)."""
        self._fila_o2.setEnabled(activo)
        if self._lbl_o2 is not None:
            self._lbl_o2.setEnabled(activo)

    def append_log(self, msg: str) -> None:
        self.log.appendPlainText(msg)
        from ..registro import log as log_archivo
        log_archivo(msg)  # todo lo del registro de pantalla queda tambien en el archivo
        if "***" in msg:  # alertas (paso a manual / bot detenido) -> sonido de alerta
            from .sonidos import sonar_alerta
            sonar_alerta()
