"""Rodape da Revisao: os tres alvos de decisao e a legenda de atalhos.

O digito vive DENTRO do alvo, e nao numa legenda separada. Isso faz do
botao e da tecla a mesma afordancia visual, em vez de duas coisas que o
usuario precisa correlacionar. Classificar centenas de tracks com o mouse
e inviavel -- o alvo desenhado e o que ensina a tecla, nao um substituto
dela.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..tokens import (
    COLOR_BORDER_STRONG,
    COLOR_SURFACE_1,
    COLOR_TEXT_PRIMARY,
    FONT_SIZE_LARGE,
    RADIUS_SM,
    SPACE_3,
    SPACE_5,
    SPACE_6,
    SPACE_8,
    classification_colors,
)
from ..typography import estiliza_label
from ..viewmodel import LABELS_EM_ORDEM

_CLASSE = {"+1": "animada", "neutra": "neutro", "-1": "lento"}

_ALTURA_ALVO = 40
#: Os atalhos, na ordem em que a barra os lista. Vem daqui e nao de uma
#: string solta para o rodape nao divergir do que MainWindow registra.
_ATALHOS = (("espaco", "tocar"), ("← →", "navegar"), ("Z", "desfazer"))


class DecisionBar(QWidget):
    #: Rotulo do dominio ("-1" | "neutra" | "+1").
    decidido = Signal(str)
    bloco_pedido = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(64)
        self.setStyleSheet(f"background: {COLOR_SURFACE_1};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_6, 0, SPACE_6, 0)
        layout.setSpacing(SPACE_5)

        self._alvos: dict[str, QPushButton] = {}
        for indice, rotulo in enumerate(LABELS_EM_ORDEM):
            alvo = self._alvo(str(indice + 1), rotulo)
            self._alvos[rotulo] = alvo
            layout.addWidget(alvo)

        # Respiro grande entre os alvos e a legenda: sao duas coisas
        # diferentes (o que se pode fazer agora vs. o que mais existe), e
        # com o espaco padrao o "espaco" cola no alvo "3 +1" e le como um
        # quarto botao.
        layout.addSpacing(SPACE_8)
        for tecla, acao in _ATALHOS:
            layout.addWidget(self._atalho(tecla, acao))
        layout.addStretch(1)

        self.botao_bloco = QPushButton()
        self.botao_bloco.setProperty("variant", "ghost")
        self.botao_bloco.clicked.connect(self.bloco_pedido)
        layout.addWidget(self.botao_bloco)

    def _alvo(self, digito: str, rotulo: str) -> QPushButton:
        _, cor = classification_colors(_CLASSE[rotulo])
        alvo = QPushButton(f"{digito}  {rotulo}")
        alvo.setFixedHeight(_ALTURA_ALVO)
        alvo.setStyleSheet(
            f"border: 1px solid {COLOR_BORDER_STRONG};"
            f"border-radius: {RADIUS_SM}px;"
            f"padding: 0 {SPACE_5}px;"
            f"color: {cor}; font-size: {FONT_SIZE_LARGE};"
        )
        alvo.clicked.connect(lambda _=False, r=rotulo: self.decidido.emit(r))
        return alvo

    def _atalho(self, tecla: str, acao: str) -> QWidget:
        caixa = QWidget()
        layout = QVBoxLayout(caixa)
        # Margem horizontal propria: sem ela as tres legendas encostam umas
        # nas outras e leem como uma frase so.
        layout.setContentsMargins(SPACE_3, 0, SPACE_3, 0)
        layout.setSpacing(0)

        rotulo_tecla = QLabel(tecla)
        rotulo_tecla.setObjectName("Numeric")
        rotulo_tecla.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
        rotulo_tecla.setAlignment(Qt.AlignmentFlag.AlignCenter)

        rotulo_acao = QLabel()
        rotulo_acao.setObjectName("MicroLabel")
        estiliza_label(rotulo_acao, acao)
        rotulo_acao.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(rotulo_tecla)
        layout.addSpacing(SPACE_3)
        layout.addWidget(rotulo_acao)
        return caixa

    def set_bulk_label(self, limiar: float) -> None:
        estiliza_label(self.botao_bloco, f"Aprovar em bloco (confianca >= {limiar})")

    def set_enabled_targets(self, habilitados: bool) -> None:
        """Fila vazia desabilita os tres alvos -- nao ha o que classificar.

        Modelo nao treinado NAO desabilita: classificar e justamente o que
        treina, e travar os alvos ali criaria um impasse.
        """
        for alvo in self._alvos.values():
            alvo.setEnabled(habilitados)
