"""Fio divisorio vertical de 1px, vestido pela regra QWidget#VDivider do QSS.

Existe como widget proprio, e nao como borda lateral de quem esta ao lado,
porque o mockup o usa em contextos diferentes (barra de transporte, painel
de classificacao) e a borda lateral acoplaria o divisor ao layout de um dos
vizinhos -- apagar o vizinho apagaria a divisoria junto.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


class VDivider(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("VDivider")
        # Sem WA_StyledBackground o Qt ignora o `background` que o QSS da a
        # uma subclasse nula de QWidget -- o mesmo motivo que o PlayerBar
        # documenta no proprio construtor.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(1)
