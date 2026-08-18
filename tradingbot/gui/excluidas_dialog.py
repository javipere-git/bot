"""
Ventanita para editar los simbolos excluidos.

Varias cajas separadas, y esa separacion es todo el punto:

  - LAS TUYAS van en varias listas con NOMBRE editable (impuestos, sin liquidez,
    siempre pierdo...). Sin el motivo escrito, en un mes la lista es una bolsa de
    simbolos sueltos que despues no sabes si podes sacar. Ademas, cuando el bot
    saltea uno, el registro dice de que lista salio.
  - LA DEL BROKER va aparte porque se renueva sola y son cientos: si estuviera
    mezclada, actualizarla te haria volver a cargar las tuyas cada vez.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
        self.resize(680, 620)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(
            "El bot NO va a operar estos simbolos, aunque esten en la watchlist.\n"
            "Se pueden separar por comas, espacios o saltos de linea."
        ))

        mias, broker = excluidas.leer(ruta)

        g_mias = QGroupBox("Mias — cada lista con su motivo (el nombre se puede cambiar)")
        grilla = QGridLayout(g_mias)
        self.filas = []
        for i, (nombre, simbolos) in enumerate(mias):
            ed_nombre = QLineEdit(nombre)
            ed_nombre.setPlaceholderText("Nombre de la lista")
            ed_nombre.setToolTip(
                "El motivo por el que excluis estos. Cuando el bot saltee uno,\n"
                "el registro va a decir de que lista salio.")
            ed_simbolos = QPlainTextEdit(" ".join(simbolos))
            ed_simbolos.setPlaceholderText("Ej.:  ABCD  EFGH  IJKL")
            ed_simbolos.setMinimumHeight(70)
            grilla.addWidget(ed_nombre, (i // 2) * 2, i % 2)
            grilla.addWidget(ed_simbolos, (i // 2) * 2 + 1, i % 2)
            self.filas.append((ed_nombre, ed_simbolos))
        lay.addWidget(g_mias, 2)

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

    def listas(self) -> tuple[list[tuple[str, list[str]]], list[str]]:
        """Devuelve (mias, del_broker). `mias` son pares (nombre, simbolos)."""
        mias = [(ed_n.text(), excluidas._limpiar(ed_s.toPlainText()))
                for ed_n, ed_s in self.filas]
        return (mias, excluidas._limpiar(self.ed_broker.toPlainText()))
