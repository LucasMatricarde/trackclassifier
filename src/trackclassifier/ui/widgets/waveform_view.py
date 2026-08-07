"""Onda grande da aba Revisao, com playhead e seek por clique."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

from ..colors import para_qcolor, tinta
from ..tokens import (
    COLOR_SURFACE_0,
    COLOR_SURFACE_WAVEFORM,
    COLOR_TEXT_PRIMARY,
    COLOR_WAVEBAND_GRID,
    COLOR_WAVEBAND_PLAYHEAD,
    RADIUS_XS,
    SIZE_WAVE_BAR,
    SIZE_WAVE_PLAYER,
)
from ..typography import texto_de_label
from ..viewmodel import TrackRow, format_duration
from .waveform_render import load_peaks, render_bands, render_curve

#: Barras entre linhas da grade de compasso. 32 barras de 2px = 64px.
_BARRAS_POR_COMPASSO = 32

#: Marca do pico: branco a 35%. Mais apagada que o playhead (branco cheio)
#: de proposito -- o playhead e onde a musica esta agora, o pico e uma
#: referencia. Trocar a hierarquia faria a marca competir com o cursor.
_PICO = tinta(COLOR_WAVEBAND_PLAYHEAD, 0.35)

#: Scrim atras dos rotulos sobre a onda. Sem ele o texto some em cima de
#: uma banda clara, que e justamente onde o pico costuma estar.
_SCRIM = tinta(COLOR_SURFACE_0, 0.82)
_SCRIM_H = 5
_SCRIM_V = 3


class WaveformView(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(SIZE_WAVE_PLAYER)
        # Nome fixo aqui (nao em set_row): o nome e invariante, so a
        # descricao muda a cada track. Setar de novo em set_row so
        # duplicaria trabalho -- e um WaveformView que nunca recebeu
        # set_row ainda merece ter nome para o leitor de tela.
        self.setAccessibleName("Onda")
        self._row: TrackRow | None = None
        self._progress = 0.0
        self._pixmap = None
        #: Caminho de peaks aprendido DEPOIS do ultimo set_row, sem passar
        #: por um refresh completo -- ver worker.ServiceWorker.peaks_ready.
        #: Prevalece sobre row.peaks_path em _monta_pixmap.
        self._peaks_override: str | None = None

    def set_row(self, row: TrackRow | None) -> None:
        self._row = row
        # A onda inteira e pixel: sem isto um leitor de tela anuncia
        # "WaveformView" e nada mais. O nome fixo mora no __init__.
        self.setAccessibleDescription(row.display_title if row else "sem track")
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

        self._pinta_grade(pintor)
        self._pinta_pico(pintor)

        x = int(self._progress * self.width())
        pintor.setPen(QColor(COLOR_WAVEBAND_PLAYHEAD))
        pintor.drawLine(x, 0, x, self.height())
        self._pinta_tempo(pintor, x)

    def _pinta_grade(self, pintor: QPainter) -> None:
        """Grade de compasso a cada 32 barras.

        E o unico consumidor de `waveband.grid` -- ate aqui o token existia
        sem uso. A cada 32 barras de 2px da 64px, que numa track de 4/4 a
        128 BPM cai perto de um compasso na largura tipica da janela. Nao e
        exato (a onda nao conhece o BPM), e nao precisa ser: serve de regua
        de leitura, nao de metronomo.
        """
        passo = SIZE_WAVE_BAR * _BARRAS_POR_COMPASSO
        if passo <= 0 or self.width() <= 0:
            return
        pintor.save()
        pintor.setPen(para_qcolor(COLOR_WAVEBAND_GRID))
        for x in range(passo, self.width(), passo):
            pintor.drawLine(x, 0, x, self.height())
        pintor.restore()

    def _pinta_pico(self, pintor: QPainter) -> None:
        """Marca do peak_offset_s, com o rotulo sobre scrim.

        O dado esta no QueueItem desde sempre e ate aqui so posicionava o
        player. Animada vs. lento se decide no drop, nao na intro: sem a
        marca, o usuario arrasta o playhead procurando o ponto toda vez.
        """
        assert self._row is not None
        duracao = self._row.duration_s
        if duracao <= 0 or self.width() <= 0:
            return
        # Cache antigo pode trazer peak_offset_s maior que a duracao (ou
        # negativo). Clampar aqui e o que mantem a marca dentro da onda em
        # vez de desenhar fora do widget, em silencio.
        fracao = min(1.0, max(0.0, self._row.peak_offset_s / duracao))
        x = int(fracao * self.width())

        pintor.save()
        pintor.setPen(para_qcolor(_PICO))
        pintor.drawLine(x, 0, x, self.height())

        # O rotulo usa a fracao CLAMPADA, e nao o offset cru: um cache
        # antigo com 9000s numa track de 5min desenharia a marca no fim
        # (certo) com o texto "150:00" ao lado (errado) -- dado
        # inconsistente vazando para a tela em vez de ser contido aqui.
        texto = texto_de_label(f"pico {format_duration(fracao * duracao)}")
        metricas = QFontMetrics(pintor.font())
        caixa = metricas.boundingRect(texto).adjusted(-_SCRIM_H, -_SCRIM_V, _SCRIM_H, _SCRIM_V)
        # A esquerda da marca quando nao cabe a direita: perto do fim da
        # track o rotulo sairia da tela.
        esquerda = x + _SCRIM_H
        if esquerda + caixa.width() > self.width():
            esquerda = x - _SCRIM_H - caixa.width()
        caixa.moveTo(esquerda, self.height() - caixa.height() - _SCRIM_V)

        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(para_qcolor(_SCRIM))
        pintor.drawRoundedRect(caixa, float(RADIUS_XS), float(RADIUS_XS))
        pintor.setPen(QColor(COLOR_TEXT_PRIMARY))
        pintor.drawText(caixa, Qt.AlignmentFlag.AlignCenter, texto)
        pintor.restore()

    def _pinta_tempo(self, pintor: QPainter, x: int) -> None:
        """Tempo corrente ao lado do playhead, no topo."""
        assert self._row is not None
        texto = format_duration(self._progress * self._row.duration_s)
        metricas = QFontMetrics(pintor.font())
        largura = metricas.horizontalAdvance(texto)
        esquerda = x + _SCRIM_H
        if esquerda + largura > self.width():
            esquerda = x - _SCRIM_H - largura
        pintor.save()
        pintor.setPen(QColor(COLOR_WAVEBAND_PLAYHEAD))
        pintor.drawText(esquerda, metricas.ascent() + _SCRIM_V, texto)
        pintor.restore()

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
