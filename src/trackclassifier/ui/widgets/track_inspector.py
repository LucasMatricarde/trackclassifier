"""Selected library track details, using only fields already in TrackRow."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ..tokens import SPACE_4, SPACE_5, SPACE_6
from ..viewmodel import TrackRow, format_duration


class TrackInspector(QWidget):
    play_requested = Signal()
    classify_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TrackInspector")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(260)
        self.cover = QLabel()
        self.cover.setFixedSize(96, 96)
        self.cover.setScaledContents(True)
        self.title = QLabel("Selecione uma musica")
        self.title.setObjectName("DashboardSectionTitle")
        self.title.setWordWrap(True)
        self.artist = QLabel("")
        self.artist.setObjectName("DashboardMuted")
        self.artist.setWordWrap(True)
        self.details = QLabel("")
        self.details.setObjectName("DashboardCaption")
        self.details.setWordWrap(True)
        play = QPushButton("▶  Reproduzir")
        play.clicked.connect(self.play_requested)
        actions = QVBoxLayout()
        actions.setSpacing(SPACE_4)
        for digit, label in enumerate(("-1", "neutra", "+1"), 1):
            button = QPushButton(f"{digit}  Classificar como {label}")
            button.clicked.connect(
                lambda _checked=False, value=label: self.classify_requested.emit(value)
            )
            actions.addWidget(button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.artist)
        layout.addWidget(self.details)
        layout.addWidget(play)
        layout.addWidget(QLabel("Acoes rapidas"))
        layout.addLayout(actions)
        layout.addStretch(1)
        self.set_track(None)

    def set_track(self, row: TrackRow | None) -> None:
        self.setEnabled(row is not None)
        if row is None:
            self.cover.clear()
            self.title.setText("Selecione uma musica")
            self.artist.setText("")
            self.details.setText("")
            return
        image = QPixmap(row.cover_path) if row.cover_path else QPixmap()
        self.cover.setPixmap(image)
        self.title.setText(row.display_title)
        self.artist.setText(row.artist or "")
        self.details.setText(
            f"Genero: {row.genre or '—'}\nBPM: {row.bpm:.0f}\n"
            f"Duracao: {format_duration(row.duration_s)}\nClasse: {row.label or '—'}"
        )
