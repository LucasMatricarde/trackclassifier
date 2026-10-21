"""Card do modo 'criar estrutura para mim' na aba Configuracao."""

from PySide6.QtWidgets import QFrame, QVBoxLayout

from ..tokens import SPACE_4, SPACE_5


class RootModeCard(QFrame):
    """Card com checkbox + ajuda + campo raiz, borda accent.base."""

    def __init__(self, checkbox, ajuda, campo_raiz, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setProperty("accent", True)

        self._checkbox = checkbox
        self._ajuda = ajuda
        self._campo_raiz = campo_raiz

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_5, SPACE_5, SPACE_5)
        layout.setSpacing(SPACE_4)
        layout.addWidget(checkbox)
        layout.addWidget(ajuda)
        layout.addWidget(campo_raiz)

    def set_visible_all(self, visible: bool) -> None:
        """Mostra ou esconde explicitamente todos os filhos."""
        self._checkbox.setVisible(visible)
        self._ajuda.setVisible(visible)
        self._campo_raiz.setVisible(visible)
        self.setVisible(visible)
