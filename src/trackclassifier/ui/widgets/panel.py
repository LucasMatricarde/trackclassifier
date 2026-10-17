"""Shared dashboard surface; the generated QSS owns its appearance."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..tokens import SPACE_5, SPACE_6


class Panel(QWidget):
    def __init__(self, parent: QWidget | None = None, *, tone: str = "base") -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setProperty("tone", tone)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.content = QVBoxLayout(self)
        self.content.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        self.content.setSpacing(SPACE_5)
