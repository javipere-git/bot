"""
Widgets reutilizables de la interfaz.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    """Seccion con un titulo clickeable que muestra/oculta su contenido
    (estilo ThinkorSwim: flechita abajo = abierto, derecha = cerrado)."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        self._btn = QToolButton()
        self._btn.setText(title)
        self._btn.setCheckable(True)
        self._btn.setChecked(True)
        self._btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn.setArrowType(Qt.DownArrow)
        self._btn.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self._btn.clicked.connect(self._toggle)

        self._content = QWidget()
        self._content_lay = QVBoxLayout(self._content)
        self._content_lay.setContentsMargins(0, 0, 0, 0)

        lay.addWidget(self._btn)
        lay.addWidget(self._content)

    def add_widget(self, w: QWidget) -> None:
        self._content_lay.addWidget(w)

    def set_title(self, text: str) -> None:
        self._btn.setText(text)

    def _toggle(self, checked: bool) -> None:
        self._content.setVisible(checked)
        self._btn.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        # colapsado: se achica a la altura del titulo; abierto: libre
        self.setMaximumHeight(16777215 if checked else self._btn.sizeHint().height() + 4)
