"""Aba Biblioteca: tabela do acervo ja rotulado, com filtro e busca.

O atalho de teclado 1/2/3 (QShortcut, contexto WindowShortcut) vive em
MainWindow -- ver o comentario la. QAbstractItemView (base de QTableView)
consome digitos para a busca incremental embutida antes que um keyPressEvent
daqui pudesse ve-los, entao nem valeria a pena tratar aqui.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .tokens import SIZE_ROW_COMFORTABLE
from .viewmodel import LibraryState
from .widgets.delegates import (
    ClassificationDelegate,
    KeyDelegate,
    TitleDelegate,
    WaveformDelegate,
)
from .widgets.track_model import Column, TrackTableModel


class LibraryTab(QWidget):
    decide_requested = Signal(str, str)
    #: Repassado do WaveformDelegate: (sha1, caminho do arquivo de audio).
    peaks_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todas: tuple = ()

        self._busca = QLineEdit()
        self._busca.setPlaceholderText("Buscar por titulo, artista ou arquivo")
        self._busca.textChanged.connect(self._reaplica_filtros)

        self._filtro = QComboBox()
        self._filtro.addItems(["Todos", "+1", "neutra", "-1"])
        self._filtro.currentTextChanged.connect(self._reaplica_filtros)

        self._model = TrackTableModel()
        self._table = self._monta_tabela()

        barra = QHBoxLayout()
        barra.addWidget(self._busca, 1)
        barra.addWidget(self._filtro)

        layout = QVBoxLayout(self)
        layout.addLayout(barra)
        layout.addWidget(self._table, 1)

    def _monta_tabela(self) -> QTableView:
        tabela = QTableView()
        tabela.setModel(self._model)
        tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabela.setShowGrid(False)
        tabela.setSortingEnabled(True)
        tabela.setWordWrap(False)
        tabela.verticalHeader().setVisible(False)

        # Altura fixa: e o que permite ao QTableView calcular o offset do
        # scroll sem medir cada linha. Altura variavel faz o scroll tremer.
        tabela.verticalHeader().setDefaultSectionSize(SIZE_ROW_COMFORTABLE)
        tabela.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        tabela.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        cabecalho = tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        cabecalho.setSectionResizeMode(Column.TITULO, QHeaderView.ResizeMode.Stretch)
        cabecalho.setHighlightSections(False)
        for coluna in Column:
            if coluna is not Column.TITULO:
                tabela.setColumnWidth(coluna, coluna.width)

        # setSortingEnabled(True) dispara uma ordenacao imediata pela coluna 0,
        # que aqui e a da onda. Fixar o indicador em Titulo evita a ordem
        # aleatoria na primeira abertura.
        cabecalho.setSortIndicator(Column.TITULO, Qt.SortOrder.AscendingOrder)

        self._waveform_delegate = WaveformDelegate(tabela)
        self._waveform_delegate.peaks_requested.connect(self.peaks_requested)
        tabela.setItemDelegateForColumn(Column.WAVEFORM, self._waveform_delegate)
        tabela.setItemDelegateForColumn(Column.CLASSIFICACAO, ClassificationDelegate(tabela))
        tabela.setItemDelegateForColumn(Column.KEY, KeyDelegate(tabela))
        self._title_delegate = TitleDelegate(tabela)
        tabela.setItemDelegateForColumn(Column.TITULO, self._title_delegate)
        return tabela

    def set_state(self, state: LibraryState) -> None:
        self._todas = state.rows
        self._reaplica_filtros()

    def _reaplica_filtros(self) -> None:
        termo = self._busca.text().strip().lower()
        rotulo = self._filtro.currentText()
        linhas = [
            linha
            for linha in self._todas
            if (rotulo == "Todos" or linha.label == rotulo)
            and (not termo or _casa(linha, termo))
        ]
        self._model.set_rows(linhas)

        # set_rows reseta o modelo, e o QTableView nao reordena sozinho depois
        # de um reset -- mesmo com setSortingEnabled(True), que so liga o
        # cabecalho ao model.sort() quando o INDICADOR muda. Sem isto o
        # indicador continua apontando para a coluna escolhida enquanto as
        # linhas voltam para a ordem de insercao: o usuario ordena por BPM,
        # digita uma letra na busca e a tabela embaralha sem aviso.
        cabecalho = self._table.horizontalHeader()
        self._model.sort(cabecalho.sortIndicatorSection(), cabecalho.sortIndicatorOrder())

    def decide_selecionada(self, rotulo: str) -> None:
        """Chamado pelo atalho de teclado 1/2/3 em MainWindow."""
        linha = self._model.row_at(self._table.currentIndex().row())
        if linha is not None:
            self.decide_requested.emit(linha.sha1, rotulo)

    def peaks_prontos(self, sha1: str, caminho: str) -> None:
        """Chamado pelo worker quando peaks_ready dispara -- sem refresh completo.

        viewport().update() repinta as linhas visiveis sem resetar o modelo:
        diferente de set_state->set_rows (beginResetModel/endResetModel), que
        perderia a selecao e o scroll a cada computo em segundo plano.
        """
        self._waveform_delegate.registrar_peaks(sha1, caminho)
        self._table.viewport().update()


def _casa(linha, termo: str) -> bool:
    """Busca em titulo, artista e nome de arquivo.

    O nome do arquivo continua no conjunto mesmo agora que ha tags: numa
    biblioteca de promos, boa parte das tracks nao tem metadado nenhum, e
    tirar o nome do arquivo deixaria justamente essas impossiveis de achar.
    """
    campos = (linha.title, linha.artist, linha.filename)
    return any(campo and termo in campo.lower() for campo in campos)
