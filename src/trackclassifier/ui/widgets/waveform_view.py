"""Onda grande da aba Revisao, com playhead e seek por clique."""

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ..tokens import COLOR_SURFACE_WAVEFORM, COLOR_WAVEBAND_PLAYHEAD, SIZE_WAVE_PLAYER
from ..viewmodel import TrackRow
from .waveform_render import load_peaks, render_bands, render_curve


class WaveformView(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(SIZE_WAVE_PLAYER)
        self._row: TrackRow | None = None
        self._progress = 0.0
        self._pixmap = None
        #: Caminho de peaks aprendido DEPOIS do ultimo set_row, sem passar
        #: por um refresh completo -- ver worker.ServiceWorker.peaks_ready.
        #: Prevalece sobre row.peaks_path em _monta_pixmap.
        self._peaks_override: str | None = None

    def set_row(self, row: TrackRow | None) -> None:
        self._row = row
        self._pixmap = None
        self._progress = 0.0
        self._peaks_override = None
        self.update()

    def set_peaks_path(self, sha1: str, path: str) -> None:
        """Chamado quando um computo de peaks termina em segundo plano.

        Ignora resultados tardios de uma track que o usuario ja navegou para
        longe -- sem isto, um computo lento terminando depois de varios
        pular()/voltar() reapareceria pintando a onda errada.
        """
        if self._row is None or self._row.sha1 != sha1:
            return
        self._peaks_override = path
        self._pixmap = None
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
        if self._row is None:
            pintor.fillRect(self.rect(), QColor(COLOR_SURFACE_WAVEFORM))
            return

        if self._pixmap is None:
            self._pixmap = self._monta_pixmap()
        if self._pixmap is None:
            pintor.fillRect(self.rect(), QColor(COLOR_SURFACE_WAVEFORM))
            return
        pintor.drawPixmap(0, 0, self._pixmap)

        x = int(self._progress * self.width())
        pintor.setPen(QColor(COLOR_WAVEBAND_PLAYHEAD))
        pintor.drawLine(x, 0, x, self.height())

    def _monta_pixmap(self):
        """RGB quando ha buckets, mono quando nao ha, nada quando nao ha dado.

        A ordem importa: os buckets sao o dado melhor, mas so existem depois
        do computo preguicoso rodar naquela track. Ate la, energy_curve ja
        veio do scan e da uma onda util.
        """
        assert self._row is not None
        picos = load_peaks(self._peaks_override or self._row.peaks_path)
        if picos is not None:
            return render_bands(picos, self.size())
        if self._row.energy_curve:
            return render_curve(self._row.energy_curve, self.size())
        return None

    def mousePressEvent(self, event) -> None:
        if self.width() > 0:
            self.seek_requested.emit(event.position().x() / self.width())
        super().mousePressEvent(event)
