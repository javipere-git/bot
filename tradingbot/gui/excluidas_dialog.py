"""
Ventanita para editar los simbolos excluidos.

Dos cuadros separados, y esa separacion es todo el punto: las que excluis VOS y
las que el BROKER tiene bloqueadas se renuevan por su cuenta. Si estuvieran
juntas, actualizar la lista del broker (que cambia sola y son cientos) te haria
volver a cargar las tuyas cada vez.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ..core import excluidas


class DialogoExcluidas(QDialog):
    def __init__(self, parent=None, ruta: str | None = None) -> None:
        super().__init__(parent)
        self.ruta = ruta            # None = el archivo de siempre (config/excluidas.txt)
        self.setWindowTitle("Simbolos excluidos")
        self.resize(560, 460)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(
            "El bot NO va a operar estos simbolos, aunque esten en la watchlist.\n"
            "Se pueden separar por comas, espacios o saltos de linea."
        ))

        mias, broker = excluidas.leer(ruta)

        lay.addWidget(QLabel("<b>Mias</b> — las que excluis vos, por el motivo que sea"))
        self.ed_mias = QPlainTextEdit(" ".join(mias))
        self.ed_mias.setPlaceholderText("Ej.:  ABCD  EFGH  IJKL")
        lay.addWidget(self.ed_mias, 1)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("<b>Del broker</b> — bloqueadas para abrir posicion"))
        self.btn_traer = QPushButton("Traer del broker")
        self.btn_traer.setToolTip(
            "Le pregunta al broker donde OPERAS cuales tiene bloqueadas para abrir\n"
            "y reemplaza SOLO esta lista (las tuyas no se tocan)."
        )
        fila.addStretch(1)
        fila.addWidget(self.btn_traer)
        lay.addLayout(fila)

        self.ed_broker = QPlainTextEdit(" ".join(broker))
        self.ed_broker.setPlaceholderText(
            "Se completa sola con 'Traer del broker', o pegalas a mano")
        lay.addWidget(self.ed_broker, 1)

        self.lbl_estado = QLabel("")
        lay.addWidget(self.lbl_estado)

        botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        # Qt los pone en ingles: aca se escriben a mano, como el resto de la app
        botones.button(QDialogButtonBox.Save).setText("Guardar")
        botones.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)

    def poner_del_broker(self, simbolos) -> None:
        """La ventana principal la llama con la lista que trajo del broker."""
        self.ed_broker.setPlainText(" ".join(sorted(set(simbolos))))
        self.lbl_estado.setText(f"Traidos {len(set(simbolos))} simbolos del broker.")

    def listas(self) -> tuple[list[str], list[str]]:
        return (excluidas._limpiar(self.ed_mias.toPlainText()),
                excluidas._limpiar(self.ed_broker.toPlainText()))
