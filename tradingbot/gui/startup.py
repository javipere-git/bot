"""
Dialogo de inicio: elegir con que broker + cuenta operar al abrir la app.

Lista un boton por cada perfil disponible (segun lo cargado en credentials.ini):
Tradier PAPER, Tradier LIVE (si esta habilitado), Alpaca PAPER, etc. PAPER es
siempre lo por defecto. Elegir un perfil LIVE (dinero real) exige ademas escribir
la palabra REAL (primera de las dos confirmaciones; la segunda es al Iniciar).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
)

from .perfiles import Perfil


class StartupDialog(QDialog):
    def __init__(self, perfiles: list[Perfil], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Elegi broker y cuenta")
        self.setMinimumSize(460, 300)
        self._perfiles = perfiles

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Con que broker y cuenta queres operar?"))

        self._grupo = QButtonGroup(self)
        self._radios: list[QRadioButton] = []
        for i, p in enumerate(perfiles):
            marca = "  [DINERO REAL]" if p.es_live else ""
            rb = QRadioButton(f"{p.broker_nombre}  -  {p.cuenta_texto}{marca}")
            if i == 0:
                rb.setChecked(True)
            self._grupo.addButton(rb, i)
            self._radios.append(rb)
            lay.addWidget(rb)
            rb.toggled.connect(self._actualizar_confirmacion)

        self._aviso = QLabel(
            "LIVE opera con TU CUENTA REAL: las ordenes del bot y cada click en el "
            "ladder usan dinero de verdad."
        )
        self._aviso.setWordWrap(True)
        self._aviso.setStyleSheet("color: #b00020;")
        lay.addWidget(self._aviso)

        self.lbl_confirm = QLabel("Para confirmar que entendes, escribi:  REAL")
        self.ed_confirm = QLineEdit()
        lay.addWidget(self.lbl_confirm)
        lay.addWidget(self.ed_confirm)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)

        self._actualizar_confirmacion()

    def _perfil_elegido_idx(self) -> int:
        return self._grupo.checkedId()

    def perfil_elegido(self) -> Perfil:
        return self._perfiles[self._perfil_elegido_idx()]

    def _actualizar_confirmacion(self) -> None:
        es_live = self.perfil_elegido().es_live
        self._aviso.setVisible(es_live)
        self.lbl_confirm.setVisible(es_live)
        self.ed_confirm.setVisible(es_live)
        if not es_live:
            self.ed_confirm.clear()

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
