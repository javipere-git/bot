"""
Pantalla de inicio: elegir broker, cuenta y de donde salen los precios.

Antes era una lista de opciones sueltas (un renglon por combinacion). Con tres
brokers esa lista se hizo larga y costaba encontrarse. Ahora se elige por partes:

    BROKER (donde salen las ordenes)  ->  CUENTA (paper / live)  ->  DATOS (precios)

Cada desplegable se rearma segun lo anterior, asi que solo aparecen combinaciones
que existen de verdad. Adentro se sigue eligiendo el mismo Perfil de siempre:
perfil_elegido() devuelve lo mismo que antes y el resto de la app no cambia.

El estilo (oscuro) es PROPIO de esta ventana: se aplica solo a este dialogo, no
toca el tema del resto de la app, que se decide despues.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .perfiles import Perfil

SIN_PRECIOS = "(sin precios)"

# Paleta de esta ventana. Los verdes/rojos son los mismos que usa el ladder en
# modo oscuro, para que la app se sienta de una sola pieza.
_QSS = """
#raiz {
    background: #22252a;
    border: 1px solid #3a3f47;
    border-radius: 10px;
}
#cabecera {
    background: #1b1e22;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    border-bottom: 1px solid #3a3f47;
}
#titulo   { color: #e8eaed; font-size: 15px; font-weight: bold; }
#version  { color: #7d848d; font-size: 11px; }
#cerrar   { border: none; border-radius: 6px; color: #9aa0a8; font-size: 15px; }
#cerrar:hover { background: #3a2226; color: #ff6b7a; }

#etiqueta { color: #9aa0a8; font-size: 11px; font-weight: bold; }
#ayuda    { color: #7d848d; font-size: 11px; }
#resumen  { color: #cfd4da; font-size: 12px; }

QComboBox {
    background: #2a2e34; color: #e8eaed;
    border: 1px solid #3a3f47; border-radius: 6px;
    padding: 7px 10px; font-size: 13px; min-height: 18px;
}
QComboBox:hover { border-color: #4a5058; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow {
    image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid #9aa0a8; margin-right: 8px;
}
QComboBox QAbstractItemView {
    background: #2a2e34; color: #e8eaed;
    border: 1px solid #3a3f47; border-radius: 6px;
    selection-background-color: #35507a; outline: none;
}

/* Tarjetas de cuenta. Los colores son los MISMOS del banner de la app abierta:
   NARANJA #E8820C = paper (simulado), VERDE #1e7d34 = live (dinero real).
   OJO: el estilo base tiene que nombrar a las DOS. Si solo se nombra #tarjeta, la
   de live sin marcar se queda sin estilo y Qt la pinta con el look por defecto
   (fondo BLANCO en medio de una ventana oscura). */
#tarjeta, #tarjetaLive {
    background: #2a2e34; border: 1px solid #3a3f47; border-radius: 8px;
    color: #cfd4da; padding: 9px 6px; font-size: 13px; text-align: center;
}
#tarjeta:hover, #tarjetaLive:hover { border-color: #4a5058; }
#tarjeta:checked {
    background: #E8820C; border: 1px solid #E8820C; color: #ffffff; font-weight: bold;
}
#tarjetaLive:checked {
    background: #1e7d34; border: 1px solid #1e7d34; color: #ffffff; font-weight: bold;
}

#avisoLive {
    background: #1e7d34; border: 1px solid #1e7d34; border-radius: 8px;
    color: #ffffff; padding: 9px; font-size: 12px;
}
QLineEdit {
    background: #2a2e34; color: #e8eaed; border: 1px solid #1e7d34;
    border-radius: 6px; padding: 7px 10px; font-size: 13px;
}

#cancelar {
    background: transparent; color: #9aa0a8; border: 1px solid #3a3f47;
    border-radius: 7px; padding: 9px 18px; font-size: 13px;
}
#cancelar:hover { background: #2a2e34; color: #e8eaed; }
/* El boton acompania el color de la cuenta elegida (igual que el banner).
   Igual que con las tarjetas: la regla base tiene que nombrar a los DOS. Si
   #conectarLive solo trae 'background', se queda sin 'border: none' y Qt le dibuja
   su marco con degrade encima -> el verde sale aclarado y no es el del banner. */
#conectar, #conectarLive {
    color: white; border: none; border-radius: 7px;
    padding: 9px 26px; font-size: 13px; font-weight: bold;
}
#conectar { background: #E8820C; }
#conectar:hover { background: #ff9420; }
#conectarLive { background: #1e7d34; }
#conectarLive:hover { background: #259940; }
"""


class StartupDialog(QDialog):
    def __init__(self, perfiles: list[Perfil], parent=None) -> None:
        super().__init__(parent)
        self._perfiles = perfiles
        self._arrastre = None

        self.setWindowTitle("Elegi broker y cuenta")
        self.setAttribute(Qt.WA_TranslucentBackground)      # esquinas redondeadas
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(_QSS)
        self.setMinimumWidth(430)

        fuera = QVBoxLayout(self)
        fuera.setContentsMargins(0, 0, 0, 0)
        raiz = QFrame()
        raiz.setObjectName("raiz")
        fuera.addWidget(raiz)
        col = QVBoxLayout(raiz)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        col.addWidget(self._cabecera())

        cuerpo = QWidget()
        cw = QVBoxLayout(cuerpo)
        cw.setContentsMargins(20, 16, 20, 16)
        cw.setSpacing(12)

        # --- broker (donde salen las ordenes) ---
        cw.addWidget(self._etiqueta("BROKER  ·  donde salen las ordenes"))
        self.combo_broker = QComboBox()
        self.combo_broker.setCursor(Qt.PointingHandCursor)
        cw.addWidget(self.combo_broker)

        # --- cuenta (paper / live) ---
        cw.addWidget(self._etiqueta("CUENTA"))
        fila = QHBoxLayout()
        fila.setSpacing(8)
        self._grupo_modo = QButtonGroup(self)
        self._grupo_modo.setExclusive(True)
        self._botones_modo: list[QPushButton] = []
        self._fila_modo = fila
        cw.addLayout(fila)

        # --- datos de mercado ---
        cw.addWidget(self._etiqueta("DATOS DE MERCADO  ·  de donde salen los precios"))
        self.combo_datos = QComboBox()
        self.combo_datos.setCursor(Qt.PointingHandCursor)
        cw.addWidget(self.combo_datos)

        self.lbl_resumen = QLabel("")
        self.lbl_resumen.setObjectName("resumen")
        self.lbl_resumen.setWordWrap(True)
        cw.addWidget(self.lbl_resumen)

        # --- aviso + confirmacion de LIVE ---
        self.aviso = QLabel(
            "CUENTA REAL: las ordenes del bot y cada click en el ladder "
            "usan DINERO DE VERDAD."
        )
        self.aviso.setObjectName("avisoLive")
        self.aviso.setWordWrap(True)
        cw.addWidget(self.aviso)

        self.lbl_confirm = QLabel("Para confirmar que entendes, escribi  REAL")
        self.lbl_confirm.setObjectName("etiqueta")
        self.ed_confirm = QLineEdit()
        self.ed_confirm.setPlaceholderText("REAL")
        cw.addWidget(self.lbl_confirm)
        cw.addWidget(self.ed_confirm)

        # --- botones ---
        pie = QHBoxLayout()
        pie.addStretch()
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("cancelar")
        self.btn_cancelar.setCursor(Qt.PointingHandCursor)
        self.btn_cancelar.clicked.connect(self.reject)
        self.btn_conectar = QPushButton("Conectar")
        self.btn_conectar.setObjectName("conectar")
        self.btn_conectar.setCursor(Qt.PointingHandCursor)
        self.btn_conectar.setDefault(True)
        self.btn_conectar.clicked.connect(self.accept)
        pie.addWidget(self.btn_cancelar)
        pie.addWidget(self.btn_conectar)
        cw.addSpacing(2)
        cw.addLayout(pie)

        col.addWidget(cuerpo)

        # --- cableado: cada eleccion rearma la siguiente ---
        self.combo_broker.currentTextChanged.connect(self._rearmar_modos)
        self.combo_datos.currentTextChanged.connect(self._actualizar)
        self._rearmar_brokers()

    # ---------- piezas ----------
    def _cabecera(self) -> QFrame:
        cab = QFrame()
        cab.setObjectName("cabecera")
        cab.setFixedHeight(46)
        h = QHBoxLayout(cab)
        h.setContentsMargins(16, 0, 8, 0)
        h.setSpacing(8)
        t = QLabel("Autotrading App")
        t.setObjectName("titulo")
        h.addWidget(t)
        # Version del codigo que esta corriendo (rama + identificador del commit).
        # Sirve para saber, mirando una captura o un registro de OTRA PC, si tenia
        # las ultimas correcciones o una version vieja. Lleva la "v." adelante para
        # que se entienda que es eso y no un dato de la cuenta.
        version = self._version_corta()
        if version:
            v = QLabel(f"v. {version}")
            v.setObjectName("version")
            v.setToolTip(
                "Version del codigo que estas corriendo.\n"
                "Si algo falla, este dato dice si la PC tiene las ultimas "
                "correcciones o quedo con una version vieja."
            )
            h.addWidget(v)
        h.addStretch()
        x = QToolButton()
        x.setObjectName("cerrar")
        x.setText("✕")
        x.setFixedSize(28, 28)
        x.setCursor(Qt.PointingHandCursor)
        x.clicked.connect(self.reject)
        h.addWidget(x)
        self._cab = cab
        return cab

    @staticmethod
    def _version_corta() -> str:
        """El identificador del commit. version_app() devuelve 'rama commit'
        (ej. 'main 52d238c'); en la cabecera alcanza con el commit."""
        try:
            from ..registro import version_app
            partes = str(version_app() or "").split()
        except Exception:  # noqa: BLE001
            return ""
        return partes[-1][:12] if partes else ""

    @staticmethod
    def _etiqueta(texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setObjectName("etiqueta")
        return lbl

    def _tarjeta(self, texto: str, detalle: str, live: bool) -> QPushButton:
        b = QPushButton(f"{texto}\n{detalle}")
        b.setObjectName("tarjetaLive" if live else "tarjeta")
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(48)
        f = QFont()
        f.setPixelSize(13)
        b.setFont(f)
        return b

    # ---------- armado en cascada ----------
    def _rearmar_brokers(self) -> None:
        vistos: list[str] = []
        for p in self._perfiles:
            if p.broker_nombre not in vistos:
                vistos.append(p.broker_nombre)
        self.combo_broker.blockSignals(True)
        self.combo_broker.clear()
        self.combo_broker.addItems(vistos)
        self.combo_broker.blockSignals(False)
        self._rearmar_modos()

    def _perfiles_del_broker(self) -> list[Perfil]:
        b = self.combo_broker.currentText()
        return [p for p in self._perfiles if p.broker_nombre == b]

    def _rearmar_modos(self) -> None:
        """Las cuentas disponibles para el broker elegido (PAPER / LIVE / SANDBOX)."""
        for b in self._botones_modo:
            self._grupo_modo.removeButton(b)
            self._fila_modo.removeWidget(b)
            b.deleteLater()
        self._botones_modo = []

        modos: list[tuple[str, bool]] = []
        for p in self._perfiles_del_broker():
            if (p.modo, p.es_live) not in modos:
                modos.append((p.modo, p.es_live))

        for modo, live in modos:
            detalle = "Dinero real" if live else "Simulado · sin dinero real"
            b = self._tarjeta(modo, detalle, live)
            b.clicked.connect(self._rearmar_datos)
            self._grupo_modo.addButton(b)
            self._fila_modo.addWidget(b)
            self._botones_modo.append(b)
        if self._botones_modo:
            # por defecto, la primera que NO sea de dinero real
            elegida = next((b for b, (_, live) in zip(self._botones_modo, modos)
                            if not live), self._botones_modo[0])
            elegida.setChecked(True)
        self._rearmar_datos()

    def _modo_elegido(self) -> str:
        for b in self._botones_modo:
            if b.isChecked():
                return b.text().split("\n")[0]
        return ""

    def _perfiles_del_modo(self) -> list[Perfil]:
        modo = self._modo_elegido()
        return [p for p in self._perfiles_del_broker() if p.modo == modo]

    def _rearmar_datos(self) -> None:
        opciones: list[str] = []
        for p in self._perfiles_del_modo():
            if p.datos not in opciones:
                opciones.append(p.datos)
        self.combo_datos.blockSignals(True)
        self.combo_datos.clear()
        for o in opciones:
            self.combo_datos.addItem(
                "Sin precios (solo ordenes)" if o == SIN_PRECIOS else o, o
            )
        self.combo_datos.blockSignals(False)
        self._actualizar()

    # ---------- perfil resultante ----------
    def perfil_elegido(self) -> Perfil:
        datos = self.combo_datos.currentData()
        for p in self._perfiles_del_modo():
            if p.datos == datos:
                return p
        candidatos = self._perfiles_del_modo() or self._perfiles_del_broker()
        return candidatos[0] if candidatos else self._perfiles[0]

    def _actualizar(self) -> None:
        p = self.perfil_elegido()
        es_live = p.es_live
        datos = p.datos

        if datos == SIN_PRECIOS:
            resumen = (f"Ordenes por <b>{p.broker_nombre}</b> ({p.modo}). "
                       f"<span style='color:#ffb3ba'>Sin precios: el ladder y los "
                       f"filtros del bot no van a tener datos.</span>")
        elif datos != p.broker_nombre:
            resumen = (f"Ordenes por <b>{p.broker_nombre}</b> ({p.modo})  ·  "
                       f"precios de <b>{datos}</b>")
        else:
            resumen = f"Ordenes y precios por <b>{p.broker_nombre}</b> ({p.modo})"
        self.lbl_resumen.setText(resumen)

        self.aviso.setVisible(es_live)
        self.lbl_confirm.setVisible(es_live)
        self.ed_confirm.setVisible(es_live)
        if not es_live:
            self.ed_confirm.clear()
        self.btn_conectar.setObjectName("conectarLive" if es_live else "conectar")
        self.btn_conectar.setText("Conectar en REAL" if es_live else "Conectar")
        # re-aplicar el estilo para que tome el objectName nuevo
        self.btn_conectar.setStyleSheet("")
        self.setStyleSheet(_QSS)
        self.adjustSize()

    # ---------- mover la ventana (no tiene marco) ----------
    def mousePressEvent(self, e) -> None:  # noqa: D102
        if e.button() == Qt.LeftButton and self._cab.geometry().contains(e.pos()):
            self._arrastre = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:  # noqa: D102
        if self._arrastre is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._arrastre)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:  # noqa: D102
        self._arrastre = None
        super().mouseReleaseEvent(e)

    # ---------- salvaguarda de LIVE (igual que antes) ----------
    def accept(self) -> None:  # noqa: D102
        if self.perfil_elegido().es_live and self.ed_confirm.text().strip().upper() != "REAL":
            QMessageBox.warning(
                self,
                "Confirmacion requerida",
                "Para operar con DINERO REAL tenes que escribir la palabra REAL "
                "en el campo de confirmacion.",
            )
            return
        super().accept()
