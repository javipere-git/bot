"""
Ventanita para elegir de que fechas bajar el historial de operaciones.

Arranca con el ultimo mes, que es lo que se pide casi siempre. Los botones de
abajo son atajos para no andar tocando el calendario.
"""
from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class DialogoOperaciones(QDialog):
    def __init__(self, parent=None, broker: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Bajar operaciones")
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(
            f"Historial de EJECUCIONES de {broker or 'la cuenta'}: lo que de verdad\n"
            "se opero, no lo que se pidio. Se guarda en un archivo que abre Excel."
        ))

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

    def _poner(self, dias: int) -> None:
        hoy = QDate.currentDate()
        self.ed_desde.setDate(hoy.addDays(-dias))
        self.ed_hasta.setDate(hoy)

    def accept(self) -> None:
        # con las fechas al reves el broker devuelve vacio y parece que no hay nada
        if self.ed_desde.date() > self.ed_hasta.date():
            self.lbl_aviso.setText("La fecha 'desde' quedo despues de la de 'hasta'.")
            return
        super().accept()

    def fechas(self) -> tuple[str, str]:
        """Las dos fechas como YYYY-MM-DD, que es lo que piden las APIs."""
        return (self.ed_desde.date().toString("yyyy-MM-dd"),
                self.ed_hasta.date().toString("yyyy-MM-dd"))
