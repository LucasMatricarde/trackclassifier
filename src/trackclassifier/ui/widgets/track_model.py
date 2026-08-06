"""Modelo da tabela. Guarda a lista, nao a apresentacao.

Titulo, artista e genero entraram na fase 2 (TrackRow ja os carrega desde a
fase anterior). Key ainda nao tem coluna -- fica para quando houver dado
real por tras dela.
"""

from enum import IntEnum
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt

from ..viewmodel import TrackRow, format_duration
from .delegates import TRACK_ROLE


class Column(IntEnum):
    WAVEFORM = 0
    TITULO = 1
    ARTISTA = 2
    GENERO = 3
    BPM = 4
    CLASSIFICACAO = 5
    CONFIANCA = 6
    DURACAO = 7

    @property
    def header(self) -> str:
        return _HEADERS[self]

    @property
    def width(self) -> int:
        return _WIDTHS[self]


_HEADERS: dict[Column, str] = {
    Column.WAVEFORM: "Onda",
    Column.TITULO: "Titulo",
    Column.ARTISTA: "Artista",
    Column.GENERO: "Genero",
    Column.BPM: "BPM",
    Column.CLASSIFICACAO: "Classificacao",
    Column.CONFIANCA: "Confianca",
    Column.DURACAO: "Duracao",
}

_WIDTHS: dict[Column, int] = {
    Column.WAVEFORM: 150,
    Column.TITULO: 280,
    Column.ARTISTA: 180,
    Column.GENERO: 120,
    Column.BPM: 60,
    Column.CLASSIFICACAO: 110,
    Column.CONFIANCA: 90,
    Column.DURACAO: 70,
}

#: Mostrado onde nao ha dado. Mesmo travessao que BPM e confianca ja usam --
#: celula vazia parece bug de render, travessao parece ausencia.
SEM_DADO = "—"

_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
_CENTER = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
_LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


class TrackTableModel(QAbstractTableModel):
    def __init__(
        self, rows: list[TrackRow] | None = None, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._rows: list[TrackRow] = rows or []

    # QModelIndex() como default e o contrato do Qt para estas duas
    # sobrescritas (rowCount/columnCount de um item raiz); nao ha singleton
    # de modulo para isso na API do PySide6.
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(Column)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        linha = self._rows[index.row()]
        coluna = Column(index.column())

        if role == TRACK_ROLE:
            return linha

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if coluna in (Column.BPM, Column.CONFIANCA, Column.DURACAO):
                return _RIGHT
            if coluna is Column.CLASSIFICACAO:
                return _CENTER
            return _LEFT

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if coluna is Column.TITULO:
            return linha.display_title
        if coluna is Column.ARTISTA:
            return linha.artist or SEM_DADO
        if coluna is Column.GENERO:
            return linha.genre or SEM_DADO
        if coluna is Column.BPM:
            return f"{linha.bpm:.0f}" if linha.bpm else SEM_DADO
        if coluna is Column.CONFIANCA:
            return SEM_DADO if linha.confidence is None else f"{linha.confidence:.2f}"
        if coluna is Column.DURACAO:
            return format_duration(linha.duration_s)
        # Onda e classificacao sao pintadas pelos delegates.
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation is not Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return Column(section).header
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if Column(column) is Column.WAVEFORM:
            return  # nao ha ordem natural para uma imagem
        self.layoutAboutToBeChanged.emit()
        self._rows.sort(
            key=_sort_key(Column(column)), reverse=order is Qt.SortOrder.DescendingOrder
        )
        self.layoutChanged.emit()

    def row_at(self, row: int) -> TrackRow | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def set_rows(self, rows: list[TrackRow]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


def _sort_key(column: Column):
    """Chave de ordenacao por coluna. None sempre vai para o fim.

    A tupla `(e_none, valor)` e o que empurra os ausentes para o fim em ordem
    crescente: False < True. Numa biblioteca de promos, ordenar por artista
    com metade sem tag e o caso comum, nao a excecao.
    """
    if column is Column.TITULO:
        # display_title nunca e None -- cai para o nome do arquivo.
        return lambda linha: linha.display_title.lower()
    if column is Column.ARTISTA:
        return lambda linha: (linha.artist is None, (linha.artist or "").lower())
    if column is Column.GENERO:
        return lambda linha: (linha.genre is None, (linha.genre or "").lower())
    if column is Column.BPM:
        return lambda linha: (linha.bpm is None, linha.bpm or 0.0)
    if column is Column.CONFIANCA:
        return lambda linha: (linha.confidence is None, linha.confidence or 0.0)
    if column is Column.DURACAO:
        return lambda linha: linha.duration_s
    if column is Column.CLASSIFICACAO:
        rotulo = lambda linha: linha.label or linha.predicted  # noqa: E731
        return lambda linha: (rotulo(linha) is None, rotulo(linha) or "")
    return lambda linha: linha.display_title.lower()
