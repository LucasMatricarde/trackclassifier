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
from ..typography import texto_de_label
from ..viewmodel import TrackRow, format_duration
from .delegates import TRACK_ROLE


class Column(IntEnum):
    """Colunas da rodada 3a do pack, na ordem em que aparecem.

    Tres mudancas em relacao a v0.1, todas do mockup:

    - CAPA virou coluna. Antes era desenhada dentro do TitleDelegate, o
      que fazia o titulo comecar em x variavel quando a capa faltava.
    - TITULO absorveu ARTISTA: titulo em peso medio e artista em
      text.secondary na mesma linha, como no mockup. Ordenar por artista
      continua existindo em _sort_key, mas deixou de ter cabecalho.
    - CONFIANCA saiu. Decisao de produto, nao de layout: na Biblioteca a
      track ja esta classificada, e a confianca do modelo sobre uma
      decisao humana ja tomada nao muda nenhuma acao. Onde ela e
      acionavel -- explicando a posicao na fila de active learning -- e na
      Revisao. O dado continua no TrackRow.
    """

    CAPA = 0
    TITULO = 1
    WAVEFORM = 2
    GENERO = 3
    BPM = 4
    KEY = 5
    CLASSIFICACAO = 6
    DURACAO = 7

    @property
    def header(self) -> str:
        # Caixa alta pelo token, nao por .upper() solto: se `font.case.label`
        # deixar de ser uppercase no JSON, o cabecalho acompanha junto com o
        # resto do app.
        return texto_de_label(_HEADERS[self])

    @property
    def width(self) -> int:
        return _WIDTHS[self]


_HEADERS: dict[Column, str] = {
    Column.CAPA: "Capa",
    Column.TITULO: "Titulo · artista",
    Column.WAVEFORM: "Onda",
    Column.GENERO: "Genero",
    Column.BPM: "BPM",
    Column.KEY: "Key",
    Column.CLASSIFICACAO: "Classe",
    Column.DURACAO: "Dur",
}

#: Larguras do LEIA-ME do pack. TITULO e a unica que estica -- as outras
#: sao fixas para as colunas da direita nao dancarem ao redimensionar.
_WIDTHS: dict[Column, int] = {
    Column.CAPA: 38,
    Column.TITULO: 220,
    Column.WAVEFORM: 480,
    Column.GENERO: 96,
    Column.BPM: 52,
    Column.KEY: 56,
    Column.CLASSIFICACAO: 72,
    Column.DURACAO: 52,
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
            if coluna in (Column.BPM, Column.DURACAO):
                return _RIGHT
            if coluna in (Column.CLASSIFICACAO, Column.KEY, Column.CAPA):
                return _CENTER
            return _LEFT

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        linha = self._rows[index.row()]
        coluna = Column(index.column())

        if coluna is Column.TITULO:
            # O artista e desenhado pelo TitleDelegate ao lado do titulo,
            # nao concatenado aqui: os dois tem peso e cor diferentes, e
            # uma string so nao carrega isso. O DisplayRole existe para a
            # busca e para o elide de fallback.
            return linha.display_title
        if coluna is Column.GENERO:
            return linha.genre or SEM_DADO
        if coluna is Column.BPM:
            return f"{linha.bpm:.0f}" if linha.bpm else SEM_DADO
        if coluna is Column.KEY:
            return format_key(linha.key, self._notation)
        if coluna is Column.DURACAO:
            return format_duration(linha.duration_s)
        if coluna is Column.CLASSIFICACAO:
            # Texto so para quem le por acessibilidade e para a busca: o
            # ClassificationDelegate pinta os segmentos por conta propria e
            # _pinta_fundo zera opcao.text antes de desenhar o fundo, entao
            # nada aparece duas vezes. Aqui dentro do ramo do DisplayRole,
            # e nao num AccessibleTextRole novo -- data() e caminho quente.
            return linha.label
        # Capa e onda sao pintadas pelos delegates.
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
        if Column(column) in (Column.WAVEFORM, Column.CAPA):
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
    if column is Column.DURACAO:
        return lambda linha: linha.duration_s
    if column is Column.CLASSIFICACAO:
        rotulo = lambda linha: linha.label or linha.predicted  # noqa: E731
        return lambda linha: (rotulo(linha) is None, rotulo(linha) or "")
    return lambda linha: linha.display_title.lower()
