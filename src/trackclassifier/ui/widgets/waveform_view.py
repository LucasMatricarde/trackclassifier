"""Onda grande da aba Revisao, com playhead e seek por clique."""

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ..tokens import COLOR_SURFACE_WAVEFORM, COLOR_WAVEBAND_PLAYHEAD, SIZE_WAVE_PLAYER
from ..viewmodel import TrackRow
from .waveform_render import render_curve


class WaveformView(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(SIZE_WAVE_PLAYER)
        self._row: TrackRow | None = None
        self._progress = 0.0
        self._pixmap = None

    def set_row(self, row: TrackRow | None) -> None:
        self._row = row
        self._pixmap = None
        self._progress = 0.0
        self.update()

    def set_progress(self, fraction: float) -> None:
        self._progress = min(1.0, max(0.0, fraction))
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(600, SIZE_WAVE_PLAYER)

    def resizeEvent(self, event) -> None:
        # Invalida o render: o pixmap e do tamanho antigo.
        self._pixmap = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        pintor = QPainter(self)
        if self._row is None or not self._row.energy_curve:
            pintor.fillRect(self.rect(), QColor(COLOR_SURFACE_WAVEFORM))
            return

        if self._pixmap is None:
            self._pixmap = render_curve(self._row.energy_curve, self.size())
        pintor.drawPixmap(0, 0, self._pixmap)

        x = int(self._progress * self.width())
        pintor.setPen(QColor(COLOR_WAVEBAND_PLAYHEAD))
        pintor.drawLine(x, 0, x, self.height())

    def mousePressEvent(self, event) -> None:
        if self.width() > 0:
            self.seek_requested.emit(event.position().x() / self.width())
        super().mousePressEvent(event)
