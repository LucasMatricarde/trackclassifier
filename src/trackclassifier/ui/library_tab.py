"""Aba Biblioteca: tabela do acervo ja rotulado, com filtro e busca."""

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
from .widgets.delegates import ClassificationDelegate, WaveformDelegate
from .widgets.track_model import Column, TrackTableModel

_TECLAS = {Qt.Key.Key_1: "-1", Qt.Key.Key_2: "neutra", Qt.Key.Key_3: "+1"}


class LibraryTab(QWidget):
    decide_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todas: tuple = ()

        self._busca = QLineEdit()
        self._busca.setPlaceholderText("Buscar por nome de arquivo")
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
        cabecalho.setSectionResizeMode(Column.ARQUIVO, QHeaderView.ResizeMode.Stretch)
        cabecalho.setHighlightSections(False)
        for coluna in Column:
            if coluna is not Column.ARQUIVO:
                tabela.setColumnWidth(coluna, coluna.width)

        # setSortingEnabled(True) dispara uma ordenacao imediata pela coluna 0,
        # que aqui e a da onda. Fixar o indicador em Arquivo evita a ordem
        # aleatoria na primeira abertura.
        cabecalho.setSortIndicator(Column.ARQUIVO, Qt.SortOrder.AscendingOrder)

        self._waveform_delegate = WaveformDelegate(tabela)
        tabela.setItemDelegateForColumn(Column.WAVEFORM, self._waveform_delegate)
        tabela.setItemDelegateForColumn(Column.CLASSIFICACAO, ClassificationDelegate(tabela))
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
            and (not termo or termo in linha.filename.lower())
        ]
        self._model.set_rows(linhas)

    def keyPressEvent(self, event) -> None:
        chave = event.key()
        if chave not in _TECLAS:
            super().keyPressEvent(event)
            return
        linha = self._model.row_at(self._table.currentIndex().row())
        if linha is not None:
            self.decide_requested.emit(linha.sha1, _TECLAS[chave])
