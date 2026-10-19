"""Review classification targets; keeps the existing signal contract."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..tokens import SPACE_2, SPACE_4, SPACE_5, SPACE_6
from ..typography import estiliza_label
from ..viewmodel import LABELS_EM_ORDEM
from .class_action_card import ClassActionCard
from .vdivider import VDivider

#: A coluna da direita repete o que a HintBar anuncia no rodape, mas junto
#: de onde a decisao acontece e com o desenho de tecla do mockup. Manter as
#: duas em sincronia e de proposito: uma legenda que promete tecla
#: inexistente e pior que legenda nenhuma (ver o teste da HintBar).
_ATALHOS: tuple[tuple[str, str], ...] = (
    ("1", "Classificar como -1"),
    ("2", "Classificar como neutra"),
    ("3", "Classificar como +1"),
    ("S", "Pular"),
    ("D", "Remover"),
    ("Space", "Tocar / pausar"),
    ("<- ->", "Anterior / proxima"),
    ("ctrl+Z", "Desfazer"),
)


class DecisionBar(QWidget):
    decidido = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DecisionBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._alvos: dict[str, ClassActionCard] = {}

        title = QLabel("Classificar esta musica")
        title.setObjectName("DashboardSectionTitle")
        hint = QLabel("Escolha a classificacao baseada na energia e no seu criterio.")
        hint.setObjectName("DashboardMuted")
        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE_5)
        for digit, label in enumerate(LABELS_EM_ORDEM, 1):
            card = ClassActionCard(label, str(digit))
            card.clicked.connect(lambda _checked=False, value=label: self.decidido.emit(value))
            self._alvos[label] = card
            buttons.addWidget(card, 1)

        esquerda = QVBoxLayout()
        esquerda.setSpacing(SPACE_4)
        esquerda.addWidget(title)
        esquerda.addWidget(hint)
        esquerda.addSpacing(SPACE_2)
        esquerda.addLayout(buttons)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_5, SPACE_6, SPACE_5)
        layout.setSpacing(SPACE_6)
        layout.addLayout(esquerda, 1)
        layout.addWidget(VDivider())
        layout.addLayout(self._coluna_de_atalhos())

    @staticmethod
    def _coluna_de_atalhos() -> QVBoxLayout:
        titulo = QLabel()
        titulo.setObjectName("MicroLabel")
        estiliza_label(titulo, "Atalhos do teclado")

        coluna = QVBoxLayout()
        coluna.setSpacing(SPACE_4)
        coluna.addWidget(titulo)
        for tecla, descricao in _ATALHOS:
            linha = QHBoxLayout()
            linha.setSpacing(SPACE_4)
            kbd = QLabel(tecla)
            kbd.setObjectName("Kbd")
            texto = QLabel(descricao)
            texto.setObjectName("DashboardMuted")
            linha.addWidget(kbd)
            linha.addWidget(texto)
            linha.addStretch(1)
            coluna.addLayout(linha)
        coluna.addStretch(1)
        return coluna

    def set_enabled_targets(self, enabled: bool) -> None:
        for card in self._alvos.values():
            card.setEnabled(enabled)
