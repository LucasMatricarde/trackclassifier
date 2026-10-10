"""Large keyboard-labelled class decision target."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout

from ..tokens import SPACE_4, SPACE_5

_DETAIL = {
    "-1": ("low", "Energia baixa"),
    "neutra": ("neutral", "Energia equilibrada"),
    "+1": ("high", "Energia alta"),
}


class ClassActionCard(QPushButton):
    def __init__(self, label: str, digit: str, parent=None) -> None:
        super().__init__(parent)
        tone, detail = _DETAIL[label]
        self.setObjectName("ClassActionCard")
        self.setProperty("class", tone)
        self.setAccessibleName(f"{digit}  Classificar como {label}: {detail}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(76)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_4, SPACE_5, SPACE_4)
        layout.setSpacing(0)
        title = QLabel(label)
        title.setObjectName("ClassActionValue")
        title.setProperty("class", tone)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel(detail)
        subtitle.setObjectName("DashboardMuted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shortcut = QLabel(digit)
        shortcut.setObjectName("DashboardCaption")
        shortcut.setAlignment(Qt.AlignmentFlag.AlignRight)
        for child in (title, subtitle, shortcut):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            layout.addWidget(child)
