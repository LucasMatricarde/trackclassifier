"""Identidade da track em revisao e as estatisticas do modelo.

No mockup a identidade (capa, titulo, chips) flutua sobre o fundo da
janela e so os dois blocos de estatistica ganham caixa: Previsao + Confianca
num card com o GuessBar, e Progresso da revisao em outro. A capa e CoverArt
porque QLabel nao recorta pixmap -- ver cover_art.py.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..tokens import (
    COLOR_ACCENT_BASE,
    RADIUS_CONTROL,
    SIZE_ART_REVIEW,
    SPACE_4,
    SPACE_5,
    SPACE_6,
    SPACE_7,
)
from ..viewmodel import TrackRow, format_duration
from .cover_art import CoverArt
from .guess_bar import GuessBar
from .key_chip import KeyChip
from .meter import Meter


class ReviewHeader(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReviewHeader")
        self.cover = CoverArt(SIZE_ART_REVIEW, RADIUS_CONTROL)
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

        # A previsao e a confianca vivem no GuessBar (escala ordinal + medidor
        # + aviso de baixa confianca). O mockup agrupa-os num card so: e a
        # leitura "o que o modelo acha, e o quanto ele tem certeza". O progresso
        # fica num card separado, com a cor de acento.
        self.guess = GuessBar()
        self.progress = QLabel("0 / 0")
        self.progress.setObjectName("DashboardValue")
        self.progress_pct = QLabel("")
        self.progress_pct.setObjectName("DashboardMuted")
        self.progress_bar = Meter(COLOR_ACCENT_BASE, 8)

        progress_box = QVBoxLayout()
        progress_box.setSpacing(SPACE_4)
        progress_box.addWidget(self._caption("Progresso da revisao"))
        numeros = QHBoxLayout()
        numeros.addWidget(self.progress)
        numeros.addStretch(1)
        numeros.addWidget(self.progress_pct)
        progress_box.addLayout(numeros)
        progress_box.addWidget(self.progress_bar)
        progress_box.addStretch(1)

        card_modelo, caixa_modelo = self._card()
        caixa_modelo.addWidget(self.guess)
        card_progresso, caixa_progresso = self._card()
        caixa_progresso.addLayout(progress_box)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_5, SPACE_6, SPACE_5)
        layout.setSpacing(SPACE_6)
        layout.addWidget(self.cover)
        layout.addLayout(identity, 1)
        layout.addWidget(card_modelo)
        layout.addWidget(card_progresso)

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

    @staticmethod
    def _card() -> tuple[QWidget, QHBoxLayout]:
        """Um dos dois cards de estatistica do mockup.

        Sem WA_StyledBackground o Qt ignora background/border do QSS numa
        subclasse nula de QWidget -- o card ficaria invisivel. Mesmo motivo
        documentado na PlayerBar.
        """
        card = QWidget()
        card.setObjectName("ReviewStatCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        caixa = QHBoxLayout(card)
        caixa.setContentsMargins(SPACE_6, SPACE_5, SPACE_6, SPACE_5)
        caixa.setSpacing(SPACE_7)
        return card, caixa

    def set_track(
        self, row: TrackRow, *, remaining: int, position: int, low_confidence: bool
    ) -> None:
        self.cover.set_cover(row.cover_path)
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
        # GuessBar desenha a escala ordinal, a classe, o medidor de confianca
        # e o aviso de poucos exemplos -- tudo em uma passada, sem duplicar a
        # logica de cor/visibilidade aqui.
        self.guess.set_guess(
            row.predicted,
            row.confidence,
            low_confidence=low_confidence,
        )
        self.progress.setText(f"{position} / {remaining}" if remaining else "0 / 0")
        fracao = position / remaining if remaining else 0.0
        self.progress_bar.set_fraction(fracao)
        self.progress_pct.setText(f"{fracao:.0%}" if remaining else "")
