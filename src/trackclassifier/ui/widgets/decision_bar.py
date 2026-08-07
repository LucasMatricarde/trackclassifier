"""Rodape da Revisao: os tres alvos de decisao.

O digito vive DENTRO do alvo, e nao numa legenda separada. Isso faz do
botao e da tecla a mesma afordancia visual, em vez de duas coisas que o
usuario precisa correlacionar. Classificar centenas de tracks com o mouse
e inviavel -- o alvo desenhado e o que ensina a tecla, nao um substituto
dela.

A legenda de atalhos (espaco/setas/Z) saiu daqui: virou HintBar, na janela,
chrome comum a Revisao e Biblioteca -- ver ui/widgets/hint_bar.py e
MainWindow._muda_hint_bar. Antes desta barra existir, a DecisionBar era o
UNICO lugar do app com legenda nenhuma, e por isso carregava a dela junto
com os alvos.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ..tokens import (
    COLOR_BORDER_STRONG,
    COLOR_SURFACE_1,
    FONT_SIZE_LARGE,
    RADIUS_SM,
    SPACE_5,
    SPACE_6,
    classification_colors,
)
from ..typography import estiliza_label
from ..viewmodel import LABELS_EM_ORDEM

_CLASSE = {"+1": "animada", "neutra": "neutro", "-1": "lento"}

_ALTURA_ALVO = 40


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

    def set_bulk_label(self, limiar: float) -> None:
        estiliza_label(self.botao_bloco, f"Aprovar em bloco (confianca >= {limiar})")

    def set_enabled_targets(self, habilitados: bool) -> None:
        """Fila vazia desabilita os tres alvos -- nao ha o que classificar.

        Modelo nao treinado NAO desabilita: classificar e justamente o que
        treina, e travar os alvos ali criaria um impasse.
        """
        for alvo in self._alvos.values():
            alvo.setEnabled(habilitados)
