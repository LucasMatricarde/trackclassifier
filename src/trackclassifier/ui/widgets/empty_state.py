"""Bloco centralizado para tela sem conteudo.

Existe porque as tres abas abrem vazias -- e uma frase no canto superior
esquerdo dentro de um vazio de altura inteira e o que o app mostrava antes.
A acao opcional e o ponto: "Fila vazia. Use Escanear" manda o usuario
procurar um botao; um botao Escanear aqui dispara o scan.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ..tokens import SPACE_5


class EmptyState(QWidget):
    action_clicked = Signal()

    def __init__(
        self,
        titulo: str,
        subtitulo: str = "",
        acao: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._titulo = QLabel(titulo)
        self._titulo.setObjectName("TrackTitle")
        self._titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._subtitulo = QLabel(subtitulo)
        self._subtitulo.setObjectName("Hint")
        self._subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitulo.setVisible(bool(subtitulo))

        self._botao: QPushButton | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACE_5)
        layout.addStretch(1)
        layout.addWidget(self._titulo)
        layout.addWidget(self._subtitulo)

        if acao:
            self._botao = QPushButton(acao)
            self._botao.setProperty("variant", "primary")
            self._botao.clicked.connect(self.action_clicked)
            # Num QVBoxLayout o botao esticaria a largura inteira e leria
            # como faixa de fundo, nao como botao.
            layout.addWidget(self._botao, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)

    def set_texto(self, titulo: str, subtitulo: str = "") -> None:
        self._titulo.setText(titulo)
        self._subtitulo.setText(subtitulo)
        self._subtitulo.setVisible(bool(subtitulo))

    def tem_botao(self) -> bool:
        return self._botao is not None

    def subtitulo_visivel(self) -> bool:
        return not self._subtitulo.isHidden()

    def acionar(self) -> None:
        """Aciona o botao. Existe para o teste percorrer o mesmo caminho do
        clique real."""
        if self._botao is not None:
            self._botao.click()
