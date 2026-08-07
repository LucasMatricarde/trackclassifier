"""Micro-label acima, numero em mono abaixo. Quatro no topo da Revisao.

Difere do par rotulo/valor da aba Modelo, que e rotulo-a-esquerda e
valor-a-direita numa lista. Aqui os quatro numeros ficam lado a lado e o
rotulo precisa estar EM CIMA de cada um -- alinhados a direita, para os
digitos formarem uma coluna que o olho compara sem reler o rotulo.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..tokens import FONT_SIZE_LARGE, SPACE_2
from ..typography import estiliza_label


class MetricBlock(QWidget):
    def __init__(self, rotulo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._rotulo = QLabel()
        self._rotulo.setObjectName("MicroLabel")
        estiliza_label(self._rotulo, rotulo)
        self._rotulo.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._valor = QLabel("")
        self._valor.setObjectName("Numeric")
        self._valor.setStyleSheet(f"font-size: {FONT_SIZE_LARGE};")
        self._valor.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_2)
        layout.addWidget(self._rotulo)
        layout.addWidget(self._valor)

    def set_value(self, valor: str | None) -> None:
        """None esconde o bloco inteiro, rotulo junto.

        Um micro-label sozinho sobre espaco vazio parece dado que falhou
        ao carregar; o bloco ausente parece o que e -- uma metrica que
        aquela track nao tem.
        """
        self.setVisible(valor is not None)
        self._valor.setText(valor or "")
