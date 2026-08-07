"""Modelo da tabela. Guarda a lista, nao a apresentacao.

Titulo, artista e genero entraram na fase 2 (TrackRow ja os carrega desde a
fase anterior). Key entrou na fase 4, com notacao alternavel entre Camelot e
classica -- o modelo guarda a preferencia e reformata sob pedido, sem reler
nem reconverter nada.
"""

from enum import IntEnum
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt

from ...keys import KeyNotation, format_key
from ..viewmodel import TrackRow, format_duration
from .delegates import TRACK_ROLE


class Column(IntEnum):
    WAVEFORM = 0
    TITULO = 1
    ARTISTA = 2
    GENERO = 3
    BPM = 4
    KEY = 5
    CLASSIFICACAO = 6
    CONFIANCA = 7
    DURACAO = 8

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
    Column.KEY: "Key",
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
    Column.KEY: 70,
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
        #: Notacao corrente da coluna Key. O modelo formata; a Key guardada
        #: em TrackRow continua canonica, entao trocar de notacao e so
        #: repintar -- nada e relido nem reconvertido.
        self._notation = KeyNotation.CAMELOT

    # QModelIndex() como default e o contrato do Qt para estas duas
    # sobrescritas (rowCount/columnCount de um item raiz); nao ha singleton
    # de modulo para isso na API do PySide6.
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(Column)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        # O Qt pede varios roles por celula em cada paint (decoracao, fonte,
        # tooltip, check state...), e so tres deles tem resposta aqui. Num
        # scroll da biblioteca real (354 linhas) data() e chamado ~88 mil
        # vezes -- construir `Column(index.column())` e indexar `self._rows`
        # ANTES de saber se o role interessa custava 9% do tempo do paint
        # (medido via cProfile) em trabalho descartado no proximo `if`.
        if not index.isValid():
            return None

        if role == TRACK_ROLE:
            return self._rows[index.row()]

        if role == Qt.ItemDataRole.TextAlignmentRole:
            coluna = Column(index.column())
            if coluna in (Column.BPM, Column.CONFIANCA, Column.DURACAO):
                return _RIGHT
            if coluna in (Column.CLASSIFICACAO, Column.KEY):
                return _CENTER
            return _LEFT

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        linha = self._rows[index.row()]
        coluna = Column(index.column())

        if coluna is Column.TITULO:
            return linha.display_title
        if coluna is Column.ARTISTA:
            return linha.artist or SEM_DADO
        if coluna is Column.GENERO:
            return linha.genre or SEM_DADO
        if coluna is Column.BPM:
            return f"{linha.bpm:.0f}" if linha.bpm else SEM_DADO
        if coluna is Column.KEY:
            return format_key(linha.key, self._notation)
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

    def set_notation(self, notation: KeyNotation) -> None:
        if notation is self._notation:
            return
        self._notation = notation
        # A coluna inteira muda de texto sem que nenhuma linha mude de dado:
        # dataChanged so na coluna Key evita o reset de modelo, que perderia
        # a selecao (o mesmo problema que a fase 3 corrigiu no computo de
        # peaks).
        if self._rows:
            self.dataChanged.emit(
                self.index(0, Column.KEY),
                self.index(len(self._rows) - 1, Column.KEY),
                [Qt.ItemDataRole.DisplayRole],
            )


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
    if column is Column.KEY:
        # Pela POSICAO NA RODA, nao pela string: "10A" < "2A" no alfabeto, o
        # que embaralharia justamente a leitura harmonica que a coluna serve.
        return lambda linha: (
            linha.key is None,
            linha.key.camelot_number if linha.key else 0,
            linha.key.mode.value if linha.key else "",
        )
    if column is Column.CONFIANCA:
        return lambda linha: (linha.confidence is None, linha.confidence or 0.0)
    if column is Column.DURACAO:
        return lambda linha: linha.duration_s
    if column is Column.CLASSIFICACAO:
        rotulo = lambda linha: linha.label or linha.predicted  # noqa: E731
        return lambda linha: (rotulo(linha) is None, rotulo(linha) or "")
    return lambda linha: linha.display_title.lower()
