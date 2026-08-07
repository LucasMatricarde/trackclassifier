"""Aba Biblioteca: tabela do acervo ja rotulado, com filtro e busca.

O atalho de teclado 1/2/3 (QShortcut, contexto WindowShortcut) vive em
MainWindow -- ver o comentario la. QAbstractItemView (base de QTableView)
consome digitos para a busca incremental embutida antes que um keyPressEvent
daqui pudesse ve-los, entao nem valeria a pena tratar aqui.
"""

import html
from pathlib import Path

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
from .tokens import (
    COLOR_ACCENT_TEXT,
    COLOR_TEXT_PRIMARY,
    FONT_FAMILY_MONO,
    SIZE_ART_ROW_COMFORTABLE,
    SIZE_ART_ROW_COMPACT,
    SIZE_ROW_COMFORTABLE,
    SIZE_ROW_COMPACT,
    SPACE_4,
    SPACE_5,
    SPACE_6,
)
from .typography import aplica_tracking
from .viewmodel import LibraryState
from .widgets.delegates import (
    SIZE_WAVE_ROW_COMFORTABLE,
    SIZE_WAVE_ROW_COMPACT,
    ClassificationDelegate,
    CoverDelegate,
    KeyDelegate,
    TitleDelegate,
    WaveformDelegate,
)
from .widgets.empty_state import Acao, EmptyState
from .widgets.library_header import LibraryHeader
from .widgets.library_table import LibraryTable
from .widgets.segmented import Segmented
from .widgets.track_model import Column, TrackTableModel

#: Rotulos do segmento, na ordem em que aparecem -- indice 0 e o padrao
#: (densidade confortavel) com que a aba abre.
_ROTULOS_DENSIDADE = ("Confortavel", "Compacta")
#: Derivado do tuple acima, nao hardcoded -- Segmented so emite indice
#: numerico, e um "compacta = indice == 1" solto em _aplica_densidade
#: dependeria da ORDEM de _ROTULOS_DENSIDADE sem dizer isso em lugar nenhum:
#: reordenar o tuple (copy, locale) inverteria a densidade em silencio, sem
#: nenhum teste pegando (os testes so conferem indice/tamanho resultante).
_INDICE_COMPACTA = _ROTULOS_DENSIDADE.index("Compacta")

#: Rotulos das duas acoes da busca sem resultado. Constante porque o
#: EmptyState devolve o rotulo no sinal e a aba compara por igualdade --
#: duas strings soltas divergiriam na primeira renomeacao.
_LIMPAR_BUSCA = "Limpar busca"
_FILTRO_TODOS = "Filtro: todos"

#: Valor do combo que significa "sem filtro". Ja aparecia solto em
#: _reaplica_filtros; virou constante para as duas leituras nao divergirem.
_TODOS = "Todos"

#: QWIDGETSIZE_MAX nao e exposto por PySide6.QtWidgets nesta versao (Qt
#: define a constante em C++, mas o binding nao a republica em Python) --
#: 16777215 (2**24 - 1) e o valor real, o "sem teto" que devolve
#: setMaximumHeight ao comportamento padrao do layout.
_QWIDGETSIZE_MAX = 16777215

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

    def __init__(self, player, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._player = player
        self._player.position_changed.connect(self._atualiza_tocando)
        # Sem isto o triangulo de play, o playhead da onda e o DURACAO regressivo
        # ficavam presos no estado final para sempre: nada mais disparava
        # _atualiza_tocando depois que a track terminava sozinha (pause manual
        # ja passa por outro caminho, mas o fim natural so avisa por aqui).
        self._player.track_finished.connect(self._quando_track_termina)
        # O player e UM SO pro app inteiro, compartilhado com a Revisao (ver
        # docstring de widgets/player.py e window.MainWindow.__init__). Sem
        # este sinal, carregar uma track nova na Revisao (decide/undo/scan ou
        # navegar a fila) troca o que o player toca e a Biblioteca nunca fica
        # sabendo: a linha antiga ficaria com o triangulo de play, o playhead
        # e a contagem regressiva de DURACAO presos numa track que ja nao esta
        # mais tocando. source_changed dispara pra QUALQUER load(), inclusive
        # o proprio -- _quando_player_carrega usa _tocando_path (guardado
        # ANTES de chamar load, em toca_linha) pra saber se foi esta aba que
        # pediu.
        self._player.source_changed.connect(self._quando_player_carrega)
        #: sha1 tocando agora, ou None. O player e um so pro app inteiro
        #: (ver docstring do modulo de Task 7) -- dar play numa linha da
        #: Biblioteca troca o que a Revisao tinha carregado, por design.
        self._tocando: str | None = None
        #: Caminho (str) que toca_linha passou a player.load() por ultimo --
        #: ver o comentario do connect de source_changed acima.
        self._tocando_path: str | None = None
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

        # Segmento de duas posicoes, nao um botao unico: o mockup mostra as
        # duas densidades lado a lado com a corrente acesa, e o indice 0
        # (Confortavel) e o padrao com que a tabela ja abre.
        self._densidade = Segmented(_ROTULOS_DENSIDADE)
        self._densidade.mudou.connect(self._aplica_densidade)

        barra = QHBoxLayout()
        barra.setSpacing(SPACE_4)
        barra.addWidget(self._busca, 1)
        barra.addWidget(self._filtro)
        barra.addWidget(self._notacao)
        barra.addWidget(self._densidade)

        self._vazio = EmptyState(
            "Nenhuma track analisada",
            "Escaneie a inbox para popular a biblioteca.",
            (Acao("Escanear"),),
        )
        self._vazio.acao_clicada.connect(lambda _rotulo: self.scan_requested.emit())

        # Diferente da biblioteca vazia: aqui a busca continua na tela e o
        # usuario esta DENTRO da tabela. As duas acoes existem porque o
        # mockup 06 as pede -- e porque, com filtro ligado, apagar o termo
        # sozinho nao traz nada de volta.
        self._sem_resultado = EmptyState(
            "",
            "",
            (Acao(_LIMPAR_BUSCA, "base"), Acao(_FILTRO_TODOS, "base")),
        )
        self._sem_resultado.acao_clicada.connect(self._acao_sem_resultado)
        self._sem_resultado.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addLayout(barra)
        layout.addWidget(self._vazio, 1)
        layout.addWidget(self._table)
        layout.addWidget(self._sem_resultado, 1)

    def _aplica_densidade(self, indice: int) -> None:
        """Troca altura de linha, lado da capa e altura da onda de uma vez.

        Os tres andam juntos: encolher a linha sem encolher a capa faz a
        capa transbordar, e encolher a capa sem a onda deixa a linha com um
        vazio no meio. E a mesma anatomia em outra escala, nao outra.
        """
        compacta = indice == _INDICE_COMPACTA
        altura = SIZE_ROW_COMPACT if compacta else SIZE_ROW_COMFORTABLE
        self._table.verticalHeader().setDefaultSectionSize(altura)
        self._cover_delegate.set_lado(
            SIZE_ART_ROW_COMPACT if compacta else SIZE_ART_ROW_COMFORTABLE
        )
        self._waveform_delegate.set_altura(
            SIZE_WAVE_ROW_COMPACT if compacta else SIZE_WAVE_ROW_COMFORTABLE
        )
        # As duas trocas invalidam o cache de pixmap: a chave inclui as
        # dimensoes, entao o conteudo velho nunca seria servido -- mas
        # ficaria ocupando o LRU e expulsando o novo.
        self._cover_delegate.clear_cache()
        self._waveform_delegate.clear_cache()
        self._table.viewport().update()

    def _monta_tabela(self) -> QTableView:
        tabela = LibraryTable()
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

        cabecalho = LibraryHeader(tabela)
        tabela.setHorizontalHeader(cabecalho)
        # O tracking do micro-label nao vem do QSS (que nao tem
        # letter-spacing) -- ver o docstring de ui/typography.py.
        aplica_tracking(cabecalho)
        cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        cabecalho.setSectionResizeMode(Column.TITULO, QHeaderView.ResizeMode.Stretch)
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

        # Duplo-clique, e nao clique simples: clique simples ja seleciona, e
        # tocar a cada selecao transformaria navegar pela lista com as setas
        # numa sequencia de tracks comecando e parando.
        tabela.doubleClicked.connect(lambda index: self.toca_linha(index.row()))

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

        # Tres estados distintos, nao dois. Biblioteca vazia oferece
        # escanear; busca sem resultado NAO -- escanear nao traria de volta
        # o que o filtro escondeu. A diferenca visivel vai alem da copy: na
        # busca sem resultado a tabela CONTINUA na tela, encolhida ate o
        # cabecalho, porque o usuario ainda esta dentro dela e as colunas
        # sao a referencia de onde ele esta.
        vazia = not self._todas
        sem_resultado = bool(self._todas) and not linhas

        self._vazio.setVisible(vazia)
        self._sem_resultado.setVisible(sem_resultado)
        if sem_resultado:
            titulo, subtitulo = self._texto_sem_resultado()
            self._sem_resultado.set_texto(titulo, subtitulo)
        self._table.setVisible(not vazia)
        # QWIDGETSIZE_MAX e o "sem teto" do Qt; None nao existe nesta API.
        self._table.setMaximumHeight(
            self._table.horizontalHeader().height() if sem_resultado else _QWIDGETSIZE_MAX
        )

        # Filtrar troca o conjunto de linhas visiveis sem mexer na barra de
        # rolagem, entao valueChanged nao dispara: sem isto, filtrar para um
        # punhado de tracks sem buckets nunca pediria o computo delas.
        self._agenda_peaks()

    def _acao_sem_resultado(self, rotulo: str) -> None:
        if rotulo == _LIMPAR_BUSCA:
            # setText dispara textChanged, que ja chama _reaplica_filtros.
            self._busca.setText("")
        elif rotulo == _FILTRO_TODOS:
            self._filtro.setCurrentText(_TODOS)

    def _texto_sem_resultado(self) -> tuple[str, str]:
        """(titulo, subtitulo em rich text) da busca sem resultado.

        Separado de _reaplica_filtros para o teste ler a copy sem depender
        de o widget estar visivel. O destaque do termo e do filtro e rich
        text porque tres QLabel emendados nao alinham na mesma baseline nem
        quebram linha juntos.
        """
        termo = self._busca.text().strip()
        rotulo = self._filtro.currentText()
        mono = f"font-family:{FONT_FAMILY_MONO}"
        partes = []
        if termo:
            # O termo e texto digitado pelo usuario, nao uma string fixa
            # como rotulo (que vem do combo, de uma lista fechada e segura):
            # sem escapar, um termo tipo "<b>drum" vira negrito de verdade
            # e "Sk8 <tag>" perde tudo depois de "<tag>" porque o QLabel em
            # RichText interpreta como uma tag HTML real.
            termo_seguro = html.escape(termo)
            partes.append(
                f'Nada em <span style="{mono};color:{COLOR_TEXT_PRIMARY}">{termo_seguro}</span>'
            )
        if rotulo != _TODOS:
            ligacao = "com o filtro" if partes else "Nada com o filtro"
            partes.append(
                f'{ligacao} <span style="{mono};color:{COLOR_ACCENT_TEXT}">{rotulo}</span>'
            )
        titulo = " ".join(partes) if partes else "Nada encontrado"
        subtitulo = (
            f"{len(self._todas)} tracks na biblioteca. "
            "A busca cobre titulo, artista e nome do arquivo."
        )
        return titulo, subtitulo

    def decide_selecionada(self, rotulo: str) -> None:
        """Chamado pelo atalho de teclado 1/2/3 em MainWindow."""
        linha = self._model.row_at(self._table.currentIndex().row())
        if linha is not None:
            self.decide_requested.emit(linha.sha1, rotulo)

    def _muda_notacao(self, texto: str) -> None:
        notacao = KeyNotation.CLASSIC if texto == _CLASSICA else KeyNotation.CAMELOT
        self._model.set_notation(notacao)
        self.notation_changed.emit(notacao)

    # ---- reproducao -------------------------------------------------------

    def toca_linha(self, indice: int) -> None:
        linha = self._model.row_at(indice)
        if linha is None:
            return
        self._tocando = linha.sha1
        # Path aqui e nao no viewmodel: ui/viewmodel.py e a fronteira de
        # dados puros -- mesmo motivo de review_tab.py:261.
        caminho = Path(linha.path_hint)
        # Guardado ANTES de chamar load(): source_changed dispara SINCRONO de
        # dentro da propria chamada abaixo -- ver o comentario no connect em
        # __init__.
        self._tocando_path = str(caminho)
        self._player.load(caminho, int(linha.duration_s * 1000))
        self._player.play()
        self._propaga_tocando(0.0, linha.duration_s)

    def _atualiza_tocando(self, posicao_ms: int) -> None:
        linha = next((l for l in self._todas if l.sha1 == self._tocando), None)  # noqa: E741
        if linha is None:
            return
        duracao_ms = self._player.duration_ms
        fracao = posicao_ms / duracao_ms if duracao_ms > 0 else 0.0
        self._propaga_tocando(fracao, max(0.0, linha.duration_s - posicao_ms / 1000))

    def _quando_track_termina(self) -> None:
        """A track tocando chegou ao fim sozinha (sem pause manual)."""
        self._limpa_tocando()

    def _quando_player_carrega(self, caminho: str) -> None:
        """O player (compartilhado com a Revisao) acabou de carregar algo.

        Mesma logica de ReviewTab._quando_player_carrega: se o caminho bate
        com o que ESTA CHAMADA pediu por ultimo, foi a propria Biblioteca que
        disparou -- nada a fazer. Caso contrario, a Revisao carregou uma
        track nova (decide/undo/scan ou navegar a fila) e a linha que esta
        aba marcou como tocando nao e mais a que soa.
        """
        if caminho != self._tocando_path:
            self._limpa_tocando()

    def _limpa_tocando(self) -> None:
        self._tocando = None
        self._propaga_tocando(0.0, 0.0)

    def _propaga_tocando(self, fracao: float, restante_s: float) -> None:
        """Um lugar so avisa os tres. Cada delegate guardando o proprio
        sha1 por caminhos diferentes e como as quatro definicoes de
        'pendente' que row_states.py existe para evitar."""
        self._cover_delegate.set_tocando(self._tocando)
        self._waveform_delegate.set_tocando(self._tocando, fracao)
        self._model.set_tocando(self._tocando, restante_s)
        self._table.viewport().update()

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
