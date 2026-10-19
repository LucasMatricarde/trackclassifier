"""Identidade da track em revisao e as estatisticas do modelo.

No mockup a identidade (capa, titulo, chips) flutua sobre o fundo da
janela e so as estatisticas ganham caixa: Previsao + Confianca num card
so e Progresso da revisao em outro. A capa e CoverArt porque QLabel nao
recorta pixmap -- ver cover_art.py.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..tokens import (
    COLOR_ACCENT_BASE,
    COLOR_CLASSIFICATION_NEUTRO_BASE,
    COLOR_STATE_WARNING,
    RADIUS_CONTROL,
    SIZE_ART_REVIEW,
    SPACE_4,
    SPACE_5,
    SPACE_6,
    SPACE_7,
)
from ..typography import repolir
from ..viewmodel import TrackRow, format_duration
from .cover_art import CoverArt
from .guess_bar import LIMIAR_ATENCAO
from .key_chip import KeyChip
from .meter import Meter

_CLASS = {"-1": "low", "neutra": "neutral", "+1": "high"}


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

        # A previsao e um bloco cheio na cor da classe; a confianca mede em
        # ambar (a cor de "quao certo o modelo esta" nao e navegacao, entao
        # nao usa o acento) e o progresso usa o acento. O mockup agrupa
        # previsao e confianca no MESMO card: e a leitura "o que o modelo
        # acha, e o quanto ele tem certeza".
        self.prediction = QLabel("—")
        self.prediction.setObjectName("PredictionBadge")
        self.confidence = QLabel("—")
        self.confidence.setObjectName("DashboardValue")
        self.confidence_bar = Meter(COLOR_CLASSIFICATION_NEUTRO_BASE, 8)
        self.progress = QLabel("0 / 0")
        self.progress.setObjectName("DashboardValue")
        self.progress_pct = QLabel("")
        self.progress_pct.setObjectName("DashboardMuted")
        self.progress_bar = Meter(COLOR_ACCENT_BASE, 8)

        prediction_box = QVBoxLayout()
        prediction_box.setSpacing(SPACE_4)
        prediction_box.addWidget(self._caption("Previsao do modelo"))
        prediction_box.addWidget(self.prediction, 0, Qt.AlignmentFlag.AlignLeft)
        prediction_box.addStretch(1)
        confidence_box = QVBoxLayout()
        confidence_box.setSpacing(SPACE_4)
        confidence_box.addWidget(self._caption("Confianca"))
        confidence_box.addWidget(self.confidence)
        confidence_box.addWidget(self.confidence_bar)
        confidence_box.addStretch(1)
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
        caixa_modelo.addLayout(prediction_box)
        caixa_modelo.addLayout(confidence_box, 1)
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
        self.prediction.setText(row.predicted or "Sem previsao")
        self.prediction.setProperty("class", _CLASS.get(row.predicted, ""))
        repolir(self.prediction)
        self.confidence.setText(f"{row.confidence:.2f}" if row.confidence is not None else "—")
        confianca = row.confidence or 0.0
        self.confidence_bar.set_fraction(confianca)
        # Mesma regra da GuessBar: abaixo do limiar a cor e o que faz
        # "0.31" ser lido como problema sem decorar onde fica o corte.
        self.confidence_bar.set_color(
            COLOR_STATE_WARNING if confianca < LIMIAR_ATENCAO else COLOR_CLASSIFICATION_NEUTRO_BASE
        )
        self.confidence_bar.setVisible(row.confidence is not None)
        self.progress.setText(f"{position} / {remaining}" if remaining else "0 / 0")
        fracao = position / remaining if remaining else 0.0
        self.progress_bar.set_fraction(fracao)
        self.progress_pct.setText(f"{fracao:.0%}" if remaining else "")
        self.prediction.setToolTip("Modelo com poucos exemplos" if low_confidence else "")
