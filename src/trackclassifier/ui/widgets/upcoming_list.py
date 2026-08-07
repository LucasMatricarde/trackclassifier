"""As proximas da fila, na anatomia da Biblioteca em densidade compacta.

Era um QLabel com os titulos concatenados por espacos. O problema nao era
estetico: sem capa, sem onda e sem key, o usuario nao tinha como saber o
que vinha a seguir sem decidir a atual primeiro. Reusar o componente da
tabela custa quase nada -- e o mesmo modelo e os mesmos delegates, so a
densidade muda.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QWidget

from ..tokens import SIZE_ART_ROW_COMPACT, SIZE_ROW_COMPACT
from ..viewmodel import TrackRow
from .delegates import (
    SIZE_WAVE_ROW_COMPACT,
    ClassificationDelegate,
    CoverDelegate,
    KeyDelegate,
    TitleDelegate,
    WaveformDelegate,
)
from .track_model import Column, TrackTableModel


class UpcomingList(QTableView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = TrackTableModel()
        self.setModel(self._model)

        # Sem interacao: e uma previa, nao uma lista de trabalho. A decisao
        # acontece na track atual; clicar aqui sugeriria que da para pular
        # para a terceira da fila, e a fila e ordenada por incerteza de
        # proposito.
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setVisible(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.verticalHeader().setDefaultSectionSize(SIZE_ROW_COMPACT)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        cabecalho = self.horizontalHeader()
        cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        cabecalho.setSectionResizeMode(Column.TITULO, QHeaderView.ResizeMode.Stretch)
        for coluna in Column:
            if coluna is not Column.TITULO:
                self.setColumnWidth(coluna, coluna.width)

        self.setItemDelegateForColumn(
            Column.CAPA, CoverDelegate(self, lado=SIZE_ART_ROW_COMPACT)
        )
        self.setItemDelegateForColumn(Column.TITULO, TitleDelegate(self))
        self.setItemDelegateForColumn(
            Column.WAVEFORM, WaveformDelegate(self, altura=SIZE_WAVE_ROW_COMPACT)
        )
        self.setItemDelegateForColumn(Column.KEY, KeyDelegate(self))
        self.setItemDelegateForColumn(Column.CLASSIFICACAO, ClassificationDelegate(self))

    def set_rows(self, rows: tuple[TrackRow, ...]) -> None:
        """Fila vazia esconde a lista inteira, em vez de deixar a moldura."""
        self._model.set_rows(list(rows))
        self.setVisible(bool(rows))
        # Altura exata das linhas que existem: um QTableView com altura fixa
        # deixaria faixa vazia quando a fila tem menos de tres.
        self.setFixedHeight(len(rows) * SIZE_ROW_COMPACT)

    def total(self) -> int:
        return self._model.rowCount()
