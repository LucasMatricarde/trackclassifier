"""Small waveform navigator below the detailed Review waveform."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ..colors import para_qcolor, tinta
from ..tokens import (
    COLOR_ACCENT_BASE,
    COLOR_SURFACE_WAVEFORM,
    COLOR_TEXT_SECONDARY,
    SIZE_WAVE_OVERVIEW,
    SPACE_3,
    SPACE_7,
)
from ..viewmodel import TrackRow
from .waveform_render import load_peaks, render_bands, render_curve


class _MiniOnda(QWidget):
    """A mini-onda em si: pintura e clique direto, sem os botoes de passo.

    Widget proprio e nao um paintEvent da Overview porque os botoes < > do
    mockup flanqueiam a onda -- misturar os dois num unico paint obrigaria
    o clique a descontar a largura dos botoes a mao.
    """

    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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

    def fracao_da_janela(self) -> float:
        """Fracao da track que o retangulo de selecao cobre.

        E o passo dos botoes < >: andar exatamente uma janela por clique,
        para o playhead nunca saltar um trecho nem repetir metade. O 1/6 e
        o mesmo fator do paintEvent abaixo -- sem largura real ainda
        (widget nao mostrado), o fallback mantem o passo coerente com o
        desenho que aparecera.
        """
        if self.width() <= 0:
            return 1 / 6
        return max(24, self.width() // 6) / self.width()

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


class WaveformOverview(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(SIZE_WAVE_OVERVIEW)
        #: Copia da fracao da mini-onda, para _passo poder calcular o destino
        #: mesmo quando a faixa ainda nao recebeu nenhuma posicao do player.
        self._progress = 0.0

        self._mini = _MiniOnda()
        self._mini.seek_requested.connect(self.seek_requested)

        self._voltar = self._botao_passo("‹", "Voltar uma janela", -1)
        self._avancar = self._botao_passo("›", "Avancar uma janela", 1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_3)
        layout.addWidget(self._voltar)
        layout.addWidget(self._mini, 1)
        layout.addWidget(self._avancar)

    def _botao_passo(self, glifo: str, nome: str, direcao: int) -> QPushButton:
        botao = QPushButton(glifo)
        botao.setObjectName("OverviewStep")
        botao.setAccessibleName(nome)
        botao.setFixedSize(SPACE_7, SPACE_7)
        botao.clicked.connect(lambda: self._passo(direcao))
        return botao

    def _passo(self, direcao: int) -> None:
        destino = min(1.0, max(0.0, self._progress + direcao * self._mini.fracao_da_janela()))
        self.seek_requested.emit(destino)

    def set_row(self, row: TrackRow | None) -> None:
        self._progress = 0.0
        self._mini.set_row(row)

    def set_peaks_path(self, sha1: str, path: str) -> None:
        self._mini.set_peaks_path(sha1, path)

    def set_progress(self, fraction: float) -> None:
        self._progress = max(0.0, min(1.0, fraction))
        self._mini.set_progress(fraction)
