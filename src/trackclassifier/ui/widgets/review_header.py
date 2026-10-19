"""Track identity, metadata and model suggestion for Review."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..tokens import (
    COLOR_ACCENT_BASE,
    COLOR_CLASSIFICATION_NEUTRO_BASE,
    COLOR_STATE_WARNING,
    SIZE_ART_REVIEW,
    SPACE_4,
    SPACE_5,
    SPACE_6,
)
from ..typography import repolir
from ..viewmodel import TrackRow, format_duration
from .guess_bar import LIMIAR_ATENCAO
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

        # Tres colunas de estatistica separadas por divisoria (ReviewStat no
        # QSS), como no mockup: a previsao e um bloco cheio na cor da classe,
        # a confianca mede em ambar (a cor de "quao certo o modelo esta" nao
        # e navegacao, entao nao usa o acento) e o progresso usa o acento.
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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_5, SPACE_6, SPACE_5)
        layout.setSpacing(SPACE_6)
        layout.addWidget(self.cover)
        layout.addLayout(identity, 1)
        layout.addWidget(self._stat(prediction_box))
        layout.addWidget(self._stat(confidence_box))
        layout.addWidget(self._stat(progress_box))

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
    def _stat(conteudo: QVBoxLayout) -> QWidget:
        """Uma coluna de estatistica com a divisoria a esquerda do mockup.

        Sem WA_StyledBackground o Qt ignora o border-left que o QSS da a uma
        subclasse nula de QWidget -- o mesmo motivo documentado em PlayerBar.
        """
        coluna = QWidget()
        coluna.setObjectName("ReviewStat")
        coluna.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        caixa = QVBoxLayout(coluna)
        caixa.setContentsMargins(SPACE_6, 0, 0, 0)
        caixa.setSpacing(0)
        caixa.addLayout(conteudo)
        return coluna

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
