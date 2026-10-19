"""Non-interactive preview of the upcoming review tracks."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..tokens import SIZE_ART_QUEUE, SPACE_4, SPACE_5, SPACE_6
from ..viewmodel import TrackRow
from .track_model import TrackTableModel


class ReviewQueueStrip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReviewQueue")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(SPACE_6, SPACE_5, SPACE_6, SPACE_5)
        self._layout.setSpacing(SPACE_5)
        self._count = 0
        self._model = TrackTableModel()

    def set_rows(self, rows: tuple[TrackRow, ...], *, remaining: int, atual: int = 0) -> None:
        """Remonta a faixa: bloco fixo a esquerda e um card por track.

        `rows` ja traz a track em revisao na primeira posicao (a janela
        local da ReviewTab), nao so as proximas: o mockup destaca a atual
        DENTRO da fila, com a borda de 2px da regra QueueItem[current=true].
        `atual` diz qual indice recebe o destaque -- ele acompanha a
        navegacao local de pular/voltar, entao nem sempre e 0.

        Recriar os cards a cada chamada e barato (a janela local tem no
        maximo 4) e dispensa o unpolish/polish que trocar a propriedade
        `current` num card vivo exigiria a cada skip.
        """
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._count = len(rows)
        self._model.set_rows(list(rows))
        self.setVisible(bool(rows))
        self.setAccessibleDescription(f"{remaining} musicas restantes")
        if not rows:
            return

        rotulo = QLabel("Fila de revisao")
        rotulo.setObjectName("DashboardSectionTitle")
        subtitulo = QLabel(f"{remaining} musicas restantes")
        subtitulo.setObjectName("DashboardMuted")
        bloco = QWidget()
        coluna = QVBoxLayout(bloco)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(SPACE_4)
        coluna.addWidget(rotulo)
        coluna.addWidget(subtitulo)
        coluna.addStretch(1)
        self._layout.addWidget(bloco)

        for indice, row in enumerate(rows):
            card = QWidget()
            card.setObjectName("QueueItem")
            # Sem WA_StyledBackground o Qt ignora background/border do QSS
            # numa subclasse nula de QWidget -- e o current=true vira so
            # propriedade sem desenho nenhum. Mesmo motivo documentado no
            # construtor da PlayerBar.
            card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            if indice == atual:
                card.setProperty("current", "true")
            line = QHBoxLayout(card)
            line.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
            line.setSpacing(SPACE_4)
            cover = QLabel()
            # O mockup pede ~49x53; o token guarda um numero so (52) e as
            # capas reais sao quadradas -- a diferenca de 3px nao justifica
            # um segundo token.
            cover.setFixedSize(SIZE_ART_QUEUE, SIZE_ART_QUEUE)
            cover.setScaledContents(True)
            if row.cover_path:
                image = QPixmap(row.cover_path)
                if not image.isNull():
                    cover.setPixmap(image)
            line.addWidget(cover)
            names = QVBoxLayout()
            title = QLabel(row.display_title)
            title.setObjectName("DashboardCaption")
            title.setToolTip(row.display_title)
            artist = QLabel(row.artist or "")
            artist.setObjectName("DashboardMuted")
            names.addWidget(title)
            names.addWidget(artist)
            line.addLayout(names)
            self._layout.addWidget(card, 1)

    def total(self) -> int:
        return self._count

    def model(self) -> TrackTableModel:
        return self._model
