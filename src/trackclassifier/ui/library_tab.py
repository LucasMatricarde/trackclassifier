"""Aba Biblioteca: tabela do acervo ja rotulado, com filtro e busca.

O atalho de teclado 1/2/3 (QShortcut, contexto WindowShortcut) vive em
MainWindow -- ver o comentario la. QAbstractItemView (base de QTableView)
consome digitos para a busca incremental embutida antes que um keyPressEvent
daqui pudesse ve-los, entao nem valeria a pena tratar aqui.
"""

from PySide6.QtCore import Qt, QTimer, Signal
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

from ..keys import KeyNotation
from .tokens import SIZE_ROW_COMFORTABLE, SPACE_4, SPACE_5, SPACE_6
from .typography import aplica_tracking
from .viewmodel import LibraryState
from .widgets.delegates import (
    ClassificationDelegate,
    CoverDelegate,
    KeyDelegate,
    TitleDelegate,
    WaveformDelegate,
)
from .widgets.empty_state import EmptyState
from .widgets.track_model import Column, TrackTableModel

#: Texto do alternador. Nao vem de KeyNotation.value porque aquilo e chave
#: interna ("camelot"/"classic"), nao rotulo de tela.
_CAMELOT = "Camelot"
_CLASSICA = "Classica"

#: Quantos computos de buckets podem estar em voo ao mesmo tempo. Cada um
#: custa ~0,4 s na thread do servico, e ela e a MESMA que atende
#: decide/undo/train/refresh, servindo os slots em ordem de chegada. O teto e
#: o que garante que uma decisao pelo teclado nunca espere mais que ~1 s
#: atras da fila de ondas.
MAX_PEAKS_EM_VOO = 3

#: Quanto tempo a rolagem precisa ficar parada antes de pedir computo. Rolar
#: rapido por cima de 300 linhas nao pede nada -- so o que o usuario parou
#: para olhar. O timer e reiniciado a cada rolagem, entao o pedido sai uma vez
#: por parada, nao uma vez por quadro.
ATRASO_PEAKS_MS = 250


class LibraryTab(QWidget):
    decide_requested = Signal(str, str)
    #: (sha1, caminho do arquivo de audio) -- computo preguicoso dos buckets.
    #: Emitido por _pede_peaks_visiveis, nunca de dentro de um paint().
    peaks_requested = Signal(str, str)
    #: KeyNotation escolhido. object porque Signal nao aceita Enum arbitrario
    #: como tipo declarado.
    notation_changed = Signal(object)
    scan_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todas: tuple = ()

        #: sha1 cujo computo ja foi pedido e ainda nao voltou. Limitado a
        #: MAX_PEAKS_EM_VOO -- ver o comentario da constante.
        self._peaks_em_voo: set[str] = set()
        #: sha1 cujo computo FALHOU. Nao se pede de novo: uma track cujo
        #: arquivo sumiu ou nao decodifica falharia toda vez que voltasse ao
        #: viewport, e cada tentativa custa o acesso ao arquivo na thread do
        #: servico. Um refresh completo limpa o conjunto (ver set_state): o
        #: proximo scan pode ter resolvido a causa.
        self._peaks_sem_sucesso: set[str] = set()
        self._timer_peaks = QTimer(self)
        self._timer_peaks.setSingleShot(True)
        self._timer_peaks.setInterval(ATRASO_PEAKS_MS)
        self._timer_peaks.timeout.connect(self._pede_peaks_visiveis)

        self._busca = QLineEdit()
        self._busca.setPlaceholderText("Buscar por titulo, artista ou arquivo")
        self._busca.textChanged.connect(self._reaplica_filtros)

        self._filtro = QComboBox()
        self._filtro.addItems(["Todos", "+1", "neutra", "-1"])
        self._filtro.currentTextChanged.connect(self._reaplica_filtros)

        self._notacao = QComboBox()
        self._notacao.addItems([_CAMELOT, _CLASSICA])
        self._notacao.currentTextChanged.connect(self._muda_notacao)

        self._model = TrackTableModel()
        self._table = self._monta_tabela()

        barra = QHBoxLayout()
        barra.setSpacing(SPACE_4)
        barra.addWidget(self._busca, 1)
        barra.addWidget(self._filtro)
        barra.addWidget(self._notacao)

        self._vazio = EmptyState(
            "Nenhuma track analisada",
            "Escaneie a inbox para popular a biblioteca.",
            "Escanear",
        )
        self._vazio.action_clicked.connect(self.scan_requested)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addLayout(barra)
        layout.addWidget(self._vazio, 1)
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
        # O tracking do micro-label nao vem do QSS (que nao tem
        # letter-spacing) -- ver o docstring de ui/typography.py.
        aplica_tracking(cabecalho)
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

        # A rolagem e o unico gatilho continuo: cada valor novo reinicia o
        # timer, entao um arrasto longo nao pede nada ate parar. Via metodo, e
        # nao `connect(self._timer_peaks.start)`: valueChanged carrega um int,
        # e o overload QTimer.start(msec) o aceitaria -- a posicao da barra
        # viraria o intervalo do timer.
        tabela.verticalScrollBar().valueChanged.connect(self._quando_rola)

        self._waveform_delegate = WaveformDelegate(tabela)
        tabela.setItemDelegateForColumn(Column.WAVEFORM, self._waveform_delegate)
        tabela.setItemDelegateForColumn(Column.CLASSIFICACAO, ClassificationDelegate(tabela))
        tabela.setItemDelegateForColumn(Column.KEY, KeyDelegate(tabela))
        tabela.setItemDelegateForColumn(Column.TITULO, TitleDelegate(tabela))
        # Guardado: e o unico delegate com cache de disco que a aba precisa
        # invalidar quando o servico troca o conjunto de tracks.
        self._cover_delegate = CoverDelegate(tabela)
        tabela.setItemDelegateForColumn(Column.CAPA, self._cover_delegate)
        return tabela

    def set_state(self, state: LibraryState) -> None:
        self._todas = state.rows
        # Estado novo do servico: uma track que falhou o computo antes pode ter
        # sido corrigida pelo scan que acabou de rodar. O que esta EM VOO nao
        # se toca -- o pedido continua na fila do worker e a resposta ainda vai
        # chegar; limpar aqui deixaria o teto contando errado para sempre.
        self._peaks_sem_sucesso.clear()
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

        # O empty state so aparece quando a biblioteca inteira esta vazia --
        # busca sem resultado e outro estado, e trocar a tabela por um botao
        # "Escanear" ali esconderia o campo de busca que o usuario acabou de
        # digitar.
        vazia = not self._todas
        self._vazio.setVisible(vazia)
        self._table.setVisible(not vazia)

        # Filtrar troca o conjunto de linhas visiveis sem mexer na barra de
        # rolagem, entao valueChanged nao dispara: sem isto, filtrar para um
        # punhado de tracks sem buckets nunca pediria o computo delas.
        self._agenda_peaks()

    def decide_selecionada(self, rotulo: str) -> None:
        """Chamado pelo atalho de teclado 1/2/3 em MainWindow."""
        linha = self._model.row_at(self._table.currentIndex().row())
        if linha is not None:
            self.decide_requested.emit(linha.sha1, rotulo)

    def _muda_notacao(self, texto: str) -> None:
        notacao = KeyNotation.CLASSIC if texto == _CLASSICA else KeyNotation.CAMELOT
        self._model.set_notation(notacao)
        self.notation_changed.emit(notacao)

    def peaks_prontos(self, sha1: str, caminho: str) -> None:
        """Chamado pelo worker quando peaks_ready dispara -- sem refresh completo.

        viewport().update() repinta as linhas visiveis sem resetar o modelo:
        diferente de set_state->set_rows (beginResetModel/endResetModel), que
        perderia a selecao e o scroll a cada computo em segundo plano.
        """
        self._peaks_em_voo.discard(sha1)
        self._waveform_delegate.registrar_peaks(sha1, caminho)
        self._table.viewport().update()
        # Abriu vaga sob o teto: puxa o proximo do viewport sem esperar uma
        # rolagem nova. E o que faz uma tela parada terminar de colorir.
        self._agenda_peaks()

    def peaks_falharam(self, sha1: str) -> None:
        """Chamado pelo worker quando peaks_failed dispara.

        Sem este caminho o teto vazaria: um computo que falha nunca emitiria
        peaks_ready, a sha1 ficaria em _peaks_em_voo para sempre e depois de
        MAX_PEAKS_EM_VOO falhas a aba pararia de pedir qualquer onda.
        """
        self._peaks_em_voo.discard(sha1)
        self._peaks_sem_sucesso.add(sha1)
        self._agenda_peaks()

    # ---- computo preguicoso dos buckets ---------------------------------

    def _quando_rola(self, _valor: int) -> None:
        self._agenda_peaks()

    def _agenda_peaks(self) -> None:
        """(Re)inicia a espera. Chamado de todo lugar que muda o que esta na tela."""
        self._timer_peaks.start()

    def showEvent(self, event) -> None:
        # A aba so tem viewport com altura util depois de aparecer, e trocar
        # para ela nao mexe na barra de rolagem -- sem este gancho, abrir a
        # Biblioteca e nao rolar nunca pediria buckets nenhum.
        super().showEvent(event)
        self._agenda_peaks()

    def resizeEvent(self, event) -> None:
        # Esticar a janela revela linhas novas pelo mesmo caminho silencioso.
        super().resizeEvent(event)
        self._agenda_peaks()

    def _pede_peaks_visiveis(self) -> None:
        """Pede o computo das linhas que estao na tela AGORA, respeitando o teto.

        E o coracao da contencao: a aba pergunta ao QTableView quais linhas o
        viewport cobre neste instante, em vez de acumular o que foi pintado em
        algum momento. Rolar 300 linhas de uma vez nao deixa rastro -- so a
        parada final vira pedido.
        """
        if not self._table.isVisible():
            return

        altura = self._table.viewport().height()
        primeira = self._table.rowAt(0)
        if primeira < 0:
            return
        ultima = self._table.rowAt(altura - 1)
        if ultima < 0:
            # rowAt devolve -1 quando o ponto cai depois da ultima linha, que e
            # o caso normal de uma tabela mais curta que o viewport.
            ultima = self._model.rowCount() - 1

        for indice in range(primeira, ultima + 1):
            if len(self._peaks_em_voo) >= MAX_PEAKS_EM_VOO:
                return
            linha = self._model.row_at(indice)
            if linha is None:
                continue
            if linha.peaks_path is not None or self._waveform_delegate.tem_peaks(linha.sha1):
                continue
            if linha.sha1 in self._peaks_em_voo or linha.sha1 in self._peaks_sem_sucesso:
                continue
            self._peaks_em_voo.add(linha.sha1)
            self.peaks_requested.emit(linha.sha1, linha.path_hint)


def _casa(linha, termo: str) -> bool:
    """Busca em titulo, artista e nome de arquivo.

    O nome do arquivo continua no conjunto mesmo agora que ha tags: numa
    biblioteca de promos, boa parte das tracks nao tem metadado nenhum, e
    tirar o nome do arquivo deixaria justamente essas impossiveis de achar.
    """
    campos = (linha.title, linha.artist, linha.filename)
    return any(campo and termo in campo.lower() for campo in campos)
