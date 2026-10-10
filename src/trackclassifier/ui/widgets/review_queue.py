"""Non-interactive preview of the upcoming review tracks."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..tokens import SPACE_4, SPACE_5, SPACE_6
from ..viewmodel import TrackRow
from .track_model import TrackTableModel


class ReviewQueueStrip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReviewQueue")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(SPACE_6, SPACE_5, SPACE_6, SPACE_5)
        self._layout.setSpacing(SPACE_5)
        self._count = 0
        self._model = TrackTableModel()

    def set_rows(self, rows: tuple[TrackRow, ...]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._count = len(rows)
        self._model.set_rows(list(rows))
        self.setVisible(bool(rows))
        self.setAccessibleDescription(f"{len(rows)} proximas tracks")
        label = QLabel("Fila de revisao")
        label.setObjectName("DashboardSectionTitle")
        self._layout.addWidget(label)
        for row in rows:
            card = QWidget()
            card.setObjectName("QueueItem")
            line = QHBoxLayout(card)
            line.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
            line.setSpacing(SPACE_4)
            cover = QLabel()
            cover.setFixedSize(36, 36)
            cover.setScaledContents(True)
            if row.cover_path:
                image = QPixmap(row.cover_path)
                if not image.isNull():
                    cover.setPixmap(image)
            line.addWidget(cover)
            names = QVBoxLayout()
            title = QLabel(row.display_title)
            title.setObjectName("DashboardCaption")
            title.setToolTip(row.display_title)
            artist = QLabel(row.artist or "")
            artist.setObjectName("DashboardMuted")
            names.addWidget(title)
            names.addWidget(artist)
            line.addLayout(names)
            self._layout.addWidget(card, 1)

    def total(self) -> int:
        return self._count

    def model(self) -> TrackTableModel:
        return self._model
