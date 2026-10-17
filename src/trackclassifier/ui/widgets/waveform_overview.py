"""Small waveform navigator below the detailed Review waveform."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from ..colors import para_qcolor, tinta
from ..tokens import COLOR_ACCENT_BASE, COLOR_SURFACE_WAVEFORM, COLOR_TEXT_SECONDARY
from ..viewmodel import TrackRow
from .waveform_render import load_peaks, render_bands, render_curve


class WaveformOverview(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(42)
        self.setAccessibleName("Visao geral da onda")
        self._row: TrackRow | None = None
        self._peaks_path: str | None = None
        self._progress = 0.0
        self._image = None

    def set_row(self, row: TrackRow | None) -> None:
        self._row = row
        self._peaks_path = None
        self._progress = 0.0
        self._image = None
        self.update()

    def set_peaks_path(self, sha1: str, path: str) -> None:
        if self._row is not None and self._row.sha1 == sha1:
            self._peaks_path = path
            self._image = None
            self.update()

    def set_progress(self, fraction: float) -> None:
        self._progress = max(0.0, min(1.0, fraction))
        self.update()

    def resizeEvent(self, event) -> None:
        self._image = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), para_qcolor(COLOR_SURFACE_WAVEFORM))
        if self._row is None:
            return
        if self._image is None:
            peaks = load_peaks(self._peaks_path or self._row.peaks_path)
            if peaks is not None:
                self._image = render_bands(peaks, self.size())
            elif self._row.energy_curve:
                self._image = render_curve(self._row.energy_curve, self.size())
        if self._image is not None:
            painter.setOpacity(0.55)
            painter.drawPixmap(0, 0, self._image)
            painter.setOpacity(1.0)
        width = max(24, self.width() // 6)
        left = min(
            max(0, self.width() - width),
            max(0, int(self._progress * self.width()) - width // 2),
        )
        painter.fillRect(
            left, 1, width, self.height() - 2,
            para_qcolor(tinta(COLOR_ACCENT_BASE, 0.18)),
        )
        painter.setPen(para_qcolor(COLOR_TEXT_SECONDARY))
        painter.drawRect(left, 1, width, self.height() - 3)

    def mousePressEvent(self, event) -> None:
        if self.width() > 0:
            self.seek_requested.emit(event.position().x() / self.width())
        super().mousePressEvent(event)
