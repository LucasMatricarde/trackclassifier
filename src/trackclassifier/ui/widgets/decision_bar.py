"""Review classification targets; keeps the existing signal contract."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..tokens import SPACE_5, SPACE_6
from ..viewmodel import LABELS_EM_ORDEM
from .class_action_card import ClassActionCard


class DecisionBar(QWidget):
    decidido = Signal(str)
    bloco_pedido = Signal()

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

        self.botao_bloco = QPushButton()
        self.botao_bloco.setObjectName("BulkAction")
        self.botao_bloco.clicked.connect(self.bloco_pedido)
        top = QHBoxLayout()
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.botao_bloco)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_5, SPACE_6, SPACE_5)
        layout.setSpacing(SPACE_5)
        layout.addLayout(top)
        layout.addWidget(hint)
        layout.addLayout(buttons)

    def set_bulk_label(self, limiar: float) -> None:
        self.botao_bloco.setText(f"Aprovar em bloco (confianca ≥ {limiar})")

    def set_enabled_targets(self, enabled: bool) -> None:
        for card in self._alvos.values():
            card.setEnabled(enabled)
