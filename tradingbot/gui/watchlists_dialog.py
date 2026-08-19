"""
Ventanita para precargar las watchlists de los botones WL.

Cada una tiene su NOMBRE editable. En la pantalla principal los botones dicen
"WL 1", "WL 2"... por una cuestion de lugar, pero el nombre aparece en la ayuda
al pasar el mouse por encima, y en el registro cuando la cargas.

El boton "Tomar la de la pantalla" es el atajo que hace util todo esto: armas la
watchlist como sea (a mano, con un archivo, con el boton de ETB que trae miles
de simbolos) y la guardas en un WL sin copiar y pegar nada.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ..core import watchlists


class DialogoWatchlists(QDialog):
    def __init__(self, parent=None, ruta: str | None = None,
                 en_pantalla: str = "") -> None:
        super().__init__(parent)
        self.ruta = ruta                    # None = el archivo de siempre
        self._en_pantalla = en_pantalla     # lo que hay ahora en la watchlist
        self.setWindowTitle("Watchlists guardadas")
        self.resize(560, 620)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(
            "Cada boton WL de la pantalla carga una de estas listas.\n"
            "Se pueden separar por comas, espacios o saltos de linea."
        ))

        self.filas = []
        self.btn_tomar = []
        for i, (nombre, simbolos) in enumerate(watchlists.leer(ruta)):
            fila = QHBoxLayout()
            fila.addWidget(QLabel(f"<b>WL {i + 1}</b>"))
            ed_nombre = QLineEdit(nombre)
            ed_nombre.setPlaceholderText(f"Nombre (ej.: acciones caras)")
            ed_nombre.setToolTip(
                "Con que nombre la vas a reconocer. Aparece en la ayuda del boton\n"
                "y en el registro cuando la cargas.")
            fila.addWidget(ed_nombre, 1)
            btn = QPushButton("Tomar la de la pantalla")
            btn.setToolTip(
                "Copia aca los simbolos que tenes AHORA en la watchlist.\n"
                "Sirve para guardar de una la lista que trajo el boton de ETB.")
            btn.clicked.connect(lambda _=False, n=i: self._tomar(n))
            # sin nada en la pantalla no hay nada que copiar: mejor apagado que
            # dejarte vaciar una lista de un click sin querer
            btn.setEnabled(bool(_limpio(en_pantalla)))
            fila.addWidget(btn)
            self.btn_tomar.append(btn)
            lay.addLayout(fila)

            ed_simbolos = QPlainTextEdit(" ".join(simbolos))
            ed_simbolos.setPlaceholderText("Ej.:  AAPL  MSFT  SPY")
            ed_simbolos.setMinimumHeight(90)
            lay.addWidget(ed_simbolos, 1)
            self.filas.append((ed_nombre, ed_simbolos))

        self.lbl_estado = QLabel("")
        self.lbl_estado.setStyleSheet("color: palette(mid);")
        lay.addWidget(self.lbl_estado)

        botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Save).setText("Guardar")
        botones.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)

    def _tomar(self, i: int) -> None:
        simbolos = _limpio(self._en_pantalla)
        self.filas[i][1].setPlainText(" ".join(simbolos))
        self.lbl_estado.setText(
            f"WL {i + 1}: copiados {len(simbolos):,} simbolo(s) de la pantalla. "
            f"Acordate de guardar.")

    def listas(self) -> list[tuple[str, list[str]]]:
        return [(ed_n.text(), watchlists._limpiar(ed_s.toPlainText()))
                for ed_n, ed_s in self.filas]


def _limpio(texto: str) -> list[str]:
    return watchlists._limpiar(texto)
