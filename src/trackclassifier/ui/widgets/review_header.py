"""Track identity, metadata and model suggestion for Review."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..tokens import COLOR_ACCENT_BASE, SIZE_ART_REVIEW, SPACE_4, SPACE_5, SPACE_6
from ..typography import repolir
from ..viewmodel import TrackRow, format_duration
from .key_chip import KeyChip
from .meter import Meter

_CLASS = {"-1": "low", "neutra": "neutral", "+1": "high"}


class ReviewHeader(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReviewHeader")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.cover = QLabel()
        self.cover.setFixedSize(SIZE_ART_REVIEW, SIZE_ART_REVIEW)
        self.cover.setScaledContents(True)
        self.title = QLabel("")
        self.title.setObjectName("ReviewTrackTitle")
        self.artist = QLabel("")
        self.artist.setObjectName("ReviewArtist")
        self.genre = self._chip()
        self.bpm = self._chip()
        self.key = KeyChip()
        self.duration = self._chip()
        self.format = self._chip()
        chips = QHBoxLayout()
        chips.setSpacing(SPACE_4)
        for item in (self.genre, self.bpm, self.key, self.duration, self.format):
            chips.addWidget(item)
        chips.addStretch(1)
        identity = QVBoxLayout()
        identity.setSpacing(SPACE_4)
        identity.addWidget(self.title)
        identity.addWidget(self.artist)
        identity.addLayout(chips)
        identity.addStretch(1)

        self.prediction = self._chip()
        self.confidence = QLabel("—")
        self.confidence.setObjectName("DashboardValue")
        self.confidence_bar = Meter(COLOR_ACCENT_BASE, 5)
        self.progress = QLabel("0 / 0")
        self.progress.setObjectName("DashboardValue")
        self.progress_bar = Meter(COLOR_ACCENT_BASE, 5)
        prediction_box = QVBoxLayout()
        prediction_box.addWidget(self._caption("Previsao do modelo"))
        prediction_box.addWidget(self.prediction)
        prediction_box.addWidget(self._caption("Confianca"))
        prediction_box.addWidget(self.confidence)
        prediction_box.addWidget(self.confidence_bar)
        prediction_box.addStretch(1)
        progress_box = QVBoxLayout()
        progress_box.addWidget(self._caption("Posicao na fila"))
        progress_box.addWidget(self.progress)
        progress_box.addWidget(self.progress_bar)
        progress_box.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_5, SPACE_6, SPACE_5)
        layout.setSpacing(SPACE_6)
        layout.addWidget(self.cover)
        layout.addLayout(identity, 1)
        layout.addLayout(prediction_box)
        layout.addLayout(progress_box)

    @staticmethod
    def _chip() -> QLabel:
        chip = QLabel()
        chip.setObjectName("DashboardChip")
        return chip

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("DashboardCaption")
        return label

    def set_track(
        self, row: TrackRow, *, remaining: int, position: int, low_confidence: bool
    ) -> None:
        image = QPixmap(row.cover_path) if row.cover_path else QPixmap()
        self.cover.setVisible(not image.isNull())
        if not image.isNull():
            self.cover.setPixmap(image)
        self.title.setText(row.display_title)
        subtitle = " · ".join(part for part in (row.artist, row.genre) if part)
        self.artist.setText(subtitle)
        self.artist.setVisible(bool(subtitle))
        self.genre.setText(row.genre or "")
        self.genre.setVisible(bool(row.genre))
        self.bpm.setText(f"{row.bpm:.0f} BPM" if row.bpm else "")
        self.bpm.setVisible(bool(row.bpm))
        self.key.set_key(row.key)
        self.duration.setText(format_duration(row.duration_s))
        self.format.setText(row.filename.rsplit(".", 1)[-1].upper() if "." in row.filename else "")
        self.format.setVisible("." in row.filename)
        self.prediction.setText(row.predicted or "Sem previsao")
        self.prediction.setProperty("class", _CLASS.get(row.predicted, ""))
        repolir(self.prediction)
        self.confidence.setText(f"{row.confidence:.2f}" if row.confidence is not None else "—")
        self.confidence_bar.set_fraction(row.confidence or 0.0)
        self.confidence_bar.setVisible(row.confidence is not None)
        self.progress.setText(f"{position} / {remaining}" if remaining else "0 / 0")
        self.progress_bar.set_fraction(position / remaining if remaining else 0.0)
        self.prediction.setToolTip("Modelo com poucos exemplos" if low_confidence else "")
