"""Modelo da tabela. Guarda a lista, nao a apresentacao.

Titulo, artista e genero entraram na fase 2 (TrackRow ja os carrega desde a
fase anterior). Key entrou na fase 4, com notacao alternavel entre Camelot e
classica -- o modelo guarda a preferencia e reformata sob pedido, sem reler
nem reconverter nada.
"""

from enum import IntEnum
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt
from PySide6.QtGui import QColor, QFont

from ...keys import KeyNotation, format_key
from ..tokens import (
    COLOR_TEXT_SECONDARY,
    COLOR_WAVEBAND_PLAYHEAD,
    FONT_FAMILY_MONO,
    FONT_FAMILY_SANS,
    FONT_SIZE_CAPTION,
)
from ..typography import fonte_de_token, texto_de_label
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

#: Larguras do mockup 3a. TITULO e a unica que estica -- as outras sao
#: fixas para as colunas da direita nao dancarem ao redimensionar. GENERO
#: e 106 (nao 96): com o rotulo mais longo do acervo real ("Progressive
#: House") a coluna de 96 elidia o que a linha de cima ja mostrava inteiro.
_WIDTHS: dict[Column, int] = {
    Column.CAPA: 38,
    Column.TITULO: 220,
    Column.WAVEFORM: 480,
    Column.GENERO: 106,
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

# Fonte e cor de celula sao construidas UMA VEZ aqui, nao dentro de data():
# a mesma razao do comentario em data() sobre Column(index.column()) --
# num scroll de 354 linhas o Qt chama data() ~88 mil vezes, e um QFont novo
# a cada chamada seria trabalho descartado repetido por nada.
_FONTE_MONO_CAPTION = fonte_de_token(FONT_FAMILY_MONO, FONT_SIZE_CAPTION)
_FONTE_SANS_CAPTION = fonte_de_token(FONT_FAMILY_SANS, FONT_SIZE_CAPTION)
_COR_SECUNDARIA = QColor(COLOR_TEXT_SECONDARY)

#: (alinhamento, fonte, cor) por coluna -- TextAlignmentRole, FontRole e
#: ForegroundRole leem do mesmo lookup em vez de tres blocos "if role == X:
#: coluna = Column(...); if coluna in (...)" cada um repetindo a mesma lista
#: de colunas. Fonte e cor so tem valor pra GENERO/BPM/DURACAO: sao as tres
#: colunas SEM delegate proprio (ver _monta_tabela) -- quem le estes dois
#: roles e o QStyledItemDelegate padrao do Qt; as outras cinco pintam a mao
#: e ignorariam os dois de qualquer forma. Chave e o int da coluna, nao o
#: Column: o proximo ajuste de estilo por coluna vira uma entrada aqui, nao
#: um quarto bloco de role igual aos outros tres.
_ESTILO_PADRAO: tuple[Qt.AlignmentFlag, QFont | None, QColor | None] = (_LEFT, None, None)
_ESTILO_POR_COLUNA: dict[int, tuple[Qt.AlignmentFlag, QFont | None, QColor | None]] = {
    int(Column.CAPA): (_CENTER, None, None),
    int(Column.GENERO): (_LEFT, _FONTE_SANS_CAPTION, _COR_SECUNDARIA),
    int(Column.BPM): (_RIGHT, _FONTE_MONO_CAPTION, None),
    int(Column.KEY): (_CENTER, None, None),
    int(Column.CLASSIFICACAO): (_CENTER, None, None),
    int(Column.DURACAO): (_RIGHT, _FONTE_MONO_CAPTION, _COR_SECUNDARIA),
}


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
        #: (sha1, segundos restantes) da track tocando. A coluna DURACAO nao
        #: tem delegate -- e pintada pelo Qt a partir do DisplayRole -- entao
        #: o "-3:21" e a cor saem daqui, e nao de codigo de pintura.
        self._tocando: str | None = None
        self._restante_s = 0.0

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
            return _ESTILO_POR_COLUNA.get(index.column(), _ESTILO_PADRAO)[0]

        if role == Qt.ItemDataRole.FontRole:
            return _ESTILO_POR_COLUNA.get(index.column(), _ESTILO_PADRAO)[1]

        if role == Qt.ItemDataRole.ForegroundRole:
            # Duracao da linha tocando sobe de text.secondary (o padrao da
            # coluna em _ESTILO_POR_COLUNA) para o branco cheio do playhead
            # -- "este numero esta andando". Checado ANTES da tabela padrao
            # por coluna porque e a UNICA celula cuja cor depende de estado
            # (qual sha1 esta tocando agora), nao so da coluna em si.
            if (
                Column(index.column()) is Column.DURACAO
                and self._rows[index.row()].sha1 == self._tocando
            ):
                return QColor(COLOR_WAVEBAND_PLAYHEAD)
            return _ESTILO_POR_COLUNA.get(index.column(), _ESTILO_PADRAO)[2]

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
            # Contagem regressiva com o sinal explicito: "3:21" e "-3:21"
            # na mesma coluna precisam se distinguir sem cor, para quem le
            # por leitor de tela.
            if linha.sha1 == self._tocando:
                return f"-{format_duration(self._restante_s)}"
            return format_duration(linha.duration_s)
        if coluna is Column.CLASSIFICACAO:
            # Texto so para quem le por acessibilidade e para a busca: o
            # ClassificationDelegate pinta os segmentos por conta propria e
            # _pinta_fundo zera opcao.text antes de desenhar o fundo, entao
            # nada aparece duas vezes. Aqui dentro do ramo do DisplayRole,
            # e nao num AccessibleTextRole novo -- data() e caminho quente.
            #
            # So o rotulo DECIDIDO de proposito, nao linha.label or
            # linha.predicted como o delegate pinta e o _sort_key ordena: uma
            # linha da fila de revisao (label=None, predicted com o palpite
            # do modelo) fica sem texto aqui, e isso e escopo, nao lacuna
            # esquecida -- misturar decisao humana com palpite do modelo no
            # mesmo campo de texto acessivel faria um leitor de tela dizer
            # "+1" tanto para uma decisao tomada quanto para um chute do
            # modelo, confundindo as duas coisas.
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
        if role == Qt.ItemDataRole.TextAlignmentRole:
            # QHeaderView centraliza por padrao. O mockup alinha os OITO
            # cabecalhos a esquerda, inclusive os das colunas cujas celulas
            # sao a direita (BPM, Dur) -- o cabecalho rotula a coluna, nao
            # espelha o alinhamento do dado dentro dela.
            return _LEFT
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

    def set_tocando(self, sha1: str | None, restante_s: float) -> None:
        """Emite dataChanged so na coluna DURACAO.

        Reset de modelo aqui perderia a selecao a cada segundo de
        reproducao -- o mesmo motivo de set_notation nao resetar.
        """
        anterior = self._tocando
        self._tocando = sha1
        self._restante_s = max(0.0, restante_s)
        if not self._rows:
            return
        if anterior == sha1 and sha1 is None:
            return
        self.dataChanged.emit(
            self.index(0, Column.DURACAO),
            self.index(len(self._rows) - 1, Column.DURACAO),
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole],
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
