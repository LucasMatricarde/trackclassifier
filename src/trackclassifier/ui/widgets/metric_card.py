"""A labelled numeric metric on the shared dashboard surface."""

from PySide6.QtWidgets import QLabel

from .panel import Panel


class MetricCard(Panel):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        label = QLabel(title)
        label.setObjectName("DashboardCaption")
        self.value = QLabel("—")
        self.value.setObjectName("DashboardValue")
        self.content.addWidget(label)
        self.content.addWidget(self.value)
