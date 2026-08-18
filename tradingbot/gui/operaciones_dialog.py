"""
Ventanita para pedir un reporte de la cuenta.

Tres reportes distintos, porque contestan tres preguntas distintas:

  EJECUCIONES  - lo que de verdad se opero, pedazo por pedazo.
  ORDENES      - lo que PEDISTE, se haya hecho o no: que se cancelo, que se
                 rechazo y (en Tasty) por que.
  TRADES       - la entrada apareada con su salida y el resultado de cada
                 operacion cerrada. Es la unica que dice como te fue.

Arranca en el ultimo mes, que es lo que se pide casi siempre.
"""
from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from ..core.historial import ESTADOS

EJECUCIONES, ORDENES, TRADES = "ejecuciones", "ordenes", "trades"


class DialogoOperaciones(QDialog):
    def __init__(self, parent=None, broker: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Reportes de la cuenta")
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(
            f"Todo lo que {broker or 'el broker'} tiene de la cuenta, en un archivo\n"
            "que abre Excel. Incluye lo que hayas operado a mano o desde otra PC."
        ))

        g_tipo = QGroupBox("Que reporte")
        v = QVBoxLayout(g_tipo)
        self.rb_ejec = QRadioButton("Ejecuciones — lo que de verdad se opero")
        self.rb_ejec.setToolTip(
            "Cada pedazo que se lleno, con su precio. Una orden puede llenarse en\n"
            "varios pedazos y a precios distintos: aca estan todos.")
        self.rb_ord = QRadioButton("Ordenes — lo que se pidio, se haya hecho o no")
        self.rb_ord.setToolTip(
            "Incluye las canceladas y las rechazadas. Tastytrade ademas manda el\n"
            "MOTIVO del rechazo escrito; Alpaca no lo informa.\n\n"
            "Tradier no ofrece este reporte: su API solo guarda las ordenes del dia.")
        self.rb_trades = QRadioButton("Trades cerrados — entrada + salida + resultado")
        self.rb_trades.setToolTip(
            "Aparea cada entrada con su salida por orden de llegada (FIFO, el mismo\n"
            "criterio que usan los brokers) y calcula el resultado de cada operacion\n"
            "cerrada. Sale de las ejecuciones: no cuesta ninguna llamada extra.")
        self.rb_trades.setChecked(True)
        for b in (self.rb_trades, self.rb_ejec, self.rb_ord):
            v.addWidget(b)
        lay.addWidget(g_tipo)

        self.g_estados = QGroupBox("Que ordenes (destildá para dejarlas afuera)")
        grilla = QGridLayout(self.g_estados)
        self.tildes = {}
        for i, estado in enumerate(ESTADOS):
            c = QCheckBox(estado)
            c.setChecked(True)
            self.tildes[estado] = c
            grilla.addWidget(c, i // 2, i % 2)
        lay.addWidget(self.g_estados)
        for b in (self.rb_trades, self.rb_ejec, self.rb_ord):
            b.toggled.connect(self._refrescar)

        hoy = QDate.currentDate()
        form = QFormLayout()
        self.ed_desde = QDateEdit(hoy.addDays(-30))
        self.ed_hasta = QDateEdit(hoy)
        for e in (self.ed_desde, self.ed_hasta):
            e.setCalendarPopup(True)
            e.setDisplayFormat("dd/MM/yyyy")
            e.setMaximumDate(hoy)
        form.addRow("Desde:", self.ed_desde)
        form.addRow("Hasta:", self.ed_hasta)
        lay.addLayout(form)

        atajos = QHBoxLayout()
        for texto, dias in (("Hoy", 0), ("7 dias", 7), ("30 dias", 30), ("90 dias", 90)):
            b = QPushButton(texto)
            b.clicked.connect(lambda _=False, d=dias: self._poner(d))
            atajos.addWidget(b)
        lay.addLayout(atajos)

        self.lbl_aviso = QLabel("")
        self.lbl_aviso.setStyleSheet("color: palette(mid);")
        lay.addWidget(self.lbl_aviso)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Ok).setText("Bajar")
        botones.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)
        self._refrescar()

    def _refrescar(self) -> None:
        """Los estados solo tienen sentido en el reporte de ordenes."""
        self.g_estados.setEnabled(self.rb_ord.isChecked())

    def _poner(self, dias: int) -> None:
        hoy = QDate.currentDate()
        self.ed_desde.setDate(hoy.addDays(-dias))
        self.ed_hasta.setDate(hoy)

    def accept(self) -> None:
        # con las fechas al reves el broker devuelve vacio y parece que no operaste
        if self.ed_desde.date() > self.ed_hasta.date():
            self.lbl_aviso.setText("La fecha 'desde' quedo despues de la de 'hasta'.")
            return
        if self.rb_ord.isChecked() and not self.estados():
            self.lbl_aviso.setText("Dejá tildado al menos un estado de orden.")
            return
        super().accept()

    def tipo(self) -> str:
        if self.rb_ejec.isChecked():
            return EJECUCIONES
        if self.rb_ord.isChecked():
            return ORDENES
        return TRADES

    def estados(self) -> list[str]:
        """Los estados tildados. Si estan todos, se devuelve vacio = sin filtro."""
        elegidos = [e for e, c in self.tildes.items() if c.isChecked()]
        return [] if len(elegidos) == len(self.tildes) else elegidos

    def fechas(self) -> tuple[str, str]:
        """Las dos fechas como YYYY-MM-DD, que es lo que piden las APIs."""
        return (self.ed_desde.date().toString("yyyy-MM-dd"),
                self.ed_hasta.date().toString("yyyy-MM-dd"))
