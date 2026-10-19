"""Aba Revisao: uma track por vez, decidida pelo teclado.

O teclado em si (QShortcut, contexto WindowShortcut) vive em MainWindow --
ver o comentario la para o motivo. Este widget so expoe os metodos que os
atalhos chamam (decide_atual/pular/voltar), sem tratar QKeyEvent.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..keys import KeyNotation
from .tokens import (
    SPACE_2,
    SPACE_4,
    SPACE_5,
    SPACE_6,
)
from .viewmodel import ReviewState, TrackRow
from .widgets.decision_bar import DecisionBar
from .widgets.empty_state import Acao, EmptyState
from .widgets.player_bar import PlayerBar
from .widgets.review_header import ReviewHeader
from .widgets.upcoming_list import UpcomingList
from .widgets.waveform_overview import WaveformOverview
from .widgets.waveform_view import WaveformView

VAZIO_TITULO = "Fila vazia"
VAZIO_SUBTITULO = "Nenhuma track nova na inbox."
VAZIO = f"{VAZIO_TITULO}. {VAZIO_SUBTITULO}"
BULK_MIN_CONFIDENCE = 0.75


class ReviewTab(QWidget):
    decide_requested = Signal(str, str)
    undo_requested = Signal()
    bulk_approve_requested = Signal(float)
    #: (sha1) -- a track exibida vai para a lixeira do SO. Quem executa e o
    #: worker, na thread do servico, como decide/undo.
    remove_requested = Signal(str)
    #: (sha1, caminho do arquivo de audio) -- gatilho do computo preguicoso
    #: dos buckets da track atual.
    peaks_requested = Signal(str, str)
    scan_requested = Signal()
    #: (nome do perfil) -- troca de perfil na aba Revisao. window.py liga ao
    #: worker.switch_profile.
    profile_switch_requested = Signal(str)

    def __init__(self, player, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._player = player
        self._state: ReviewState | None = None

        # Janela local de navegacao para pular/voltar sem round-trip ao
        # worker. O servico nao tem conceito de posicao numa fila -- so
        # entrega "a atual" e "as proximas ate 3" a cada refresh. Skip/back
        # navegam dentro desse snapshot cacheado ([current] + upcoming, no
        # maximo 4 tracks); nunca chamam o worker e nunca sobrevivem a um
        # set_state novo, porque o snapshot antigo pode estar obsoleto (ex.:
        # a aba Biblioteca decidiu uma dessas tracks por fora).
        self._janela: list[TrackRow] = []
        self._posicao = 0
        #: sha1 da track que o player ja tem carregada. Ver _atualiza_exibicao.
        self._carregada: str | None = None
        #: Caminho (str) que esta chamada passou a player.load() por ultimo,
        #: para _quando_player_carrega distinguir "fui eu quem carregou" de
        #: "a Biblioteca deu play por cima". Ver o comentario no connect logo
        #: abaixo para o porque disso ser necessario.
        self._carregada_path: str | None = None
        #: sha1 ja solicitados nesta sessao -- evita reenfileirar compute_peaks
        #: a cada refresh enquanto o computo de uma track continuar falhando
        #: (disco cheio, arquivo removido). Sem isto, uma falha persistente
        #: vira um loop sem fim: refresh -> pede de novo -> computa de novo
        #: -> refresh de novo, travando a thread do servico.
        self._pedidos_de_peaks: set[str] = set()

        self._header = ReviewHeader()
        self._titulo = self._header.title
        self._subtitulo = self._header.artist
        self._capa = self._header.cover
        self._key_chip = self._header.key

        # Combobox de perfil no topo da aba Revisao: troca a inbox visivel sem
        # sair da aba. O servico ja carregou todas as pastas de todos os
        # perfis de uma vez (scan global); este combobox so filtra queue()
        # para o perfil ativo -- set_active_profile no worker.
        self._perfil_combo = QComboBox()
        self._perfil_combo.setMinimumWidth(160)
        self._perfil_combo.currentTextChanged.connect(self._on_profile_changed)

        self._proximas = UpcomingList()

        self._waveform = WaveformView()
        self._waveform.seek_requested.connect(self._player.seek_fraction)
        self._overview = WaveformOverview()
        self._overview.seek_requested.connect(self._player.seek_fraction)
        self._player.position_changed.connect(self._atualiza_progresso)
        # O player e UM SO pro app inteiro, compartilhado com a Biblioteca
        # (ver docstring de widgets/player.py e window.MainWindow.__init__).
        # Sem este sinal, um duplo-clique na Biblioteca troca o que o player
        # toca e a Revisao nunca fica sabendo: o guard de _atualiza_exibicao
        # (`atual.sha1 == self._carregada`) ficaria preso no sha1 antigo pra
        # sempre, e _atualiza_progresso continuaria pintando o playhead da
        # onda com a posicao/duracao de uma track que ja nao e mais a que
        # esta tocando. source_changed dispara pra QUALQUER load(), inclusive
        # o proprio -- _quando_player_carrega usa _carregada_path (guardado
        # ANTES de chamar load, mais abaixo) pra saber se foi esta aba que
        # pediu, e so solta a posse quando nao foi.
        self._player.source_changed.connect(self._quando_player_carrega)

        self._decisao = DecisionBar()
        self._decisao.decidido.connect(self.decide_atual)

        self._player_bar = PlayerBar(self._player)
        self._player_bar.set_bulk_label(BULK_MIN_CONFIDENCE)
        self._player_bar.previous_requested.connect(self.voltar)
        self._player_bar.next_requested.connect(self.pular)
        # Pular por botao e o mesmo pular da seta direita: navegacao local,
        # sem round-trip ao worker (ver pular()).
        self._player_bar.skip_requested.connect(self.pular)
        self._player_bar.remove_requested.connect(self.remover_atual)
        self._player_bar.bulk_requested.connect(self._pedir_bloco)

        # Onda detalhada e mini-onda moram num painel so (QWidget#WavePanel),
        # como no mockup -- soltas no layout, liam-se como duas faixas sem
        # relacao entre si. O stretch fica no painel inteiro, nao mais na
        # onda grande: sem track ele some junto com o resto do bloco.
        self._painel_onda = QWidget()
        self._painel_onda.setObjectName("WavePanel")
        self._painel_onda.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        onda = QVBoxLayout(self._painel_onda)
        onda.setContentsMargins(SPACE_5, SPACE_5, SPACE_5, SPACE_5)
        onda.setSpacing(SPACE_4)
        onda.addWidget(self._waveform, 1)
        onda.addWidget(self._overview)

        # Tudo que so faz sentido com uma track vira um widget so: com a fila
        # vazia ele some inteiro e o EmptyState ocupa o lugar. Antes o
        # stretch=1 da onda esticava um bloco vazio pela altura da janela.
        self._bloco = QWidget()
        conteudo = QVBoxLayout(self._bloco)
        conteudo.setContentsMargins(0, 0, 0, 0)
        conteudo.setSpacing(SPACE_5)
        conteudo.addWidget(self._header)
        conteudo.addWidget(self._painel_onda, 1)
        conteudo.addWidget(self._player_bar)
        conteudo.addWidget(self._decisao)
        conteudo.addWidget(self._proximas)

        self._vazio = EmptyState(VAZIO_TITULO, VAZIO_SUBTITULO, (Acao("Escanear"),))
        self._vazio.acao_clicada.connect(lambda _rotulo: self.scan_requested.emit())

        corpo = QVBoxLayout()
        corpo.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        corpo.setSpacing(SPACE_5)
        # Perfil: barra fina acima do header, como se fosse parte do chrome da
        # aba -- troca de perfil e mais visivel do que uma opcao escondida.
        perfil_barra = QHBoxLayout()
        perfil_barra.setContentsMargins(0, 0, 0, 0)
        perfil_barra.setSpacing(SPACE_2)
        perfil_barra.addWidget(QLabel("Perfil:"))
        perfil_barra.addWidget(self._perfil_combo)
        perfil_barra.addStretch(1)
        corpo.addLayout(perfil_barra)
        corpo.addWidget(self._vazio, 1)
        corpo.addWidget(self._bloco, 1)

        layout = QVBoxLayout(self)
        # O rodape encosta nas bordas: e uma faixa de chrome da janela, nao
        # conteudo. Por isso a margem fica no corpo, e nao no layout externo.
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(corpo, 1)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def current_sha1(self) -> str | None:
        # A decisao sempre age sobre o que esta exibido localmente, que pode
        # divergir de state.current depois de um skip -- nunca sobre o
        # snapshot original do servico.
        exibida = self._exibida()
        return exibida.sha1 if exibida is not None else None

    def empty_text(self) -> str:
        return VAZIO

    def _exibida(self) -> TrackRow | None:
        """Track na posicao local atual dentro da janela [current, *upcoming]."""
        if 0 <= self._posicao < len(self._janela):
            return self._janela[self._posicao]
        return None

    def set_state(self, state: ReviewState) -> None:
        self._state = state
        self._atualiza_combobox(state)

        # Um estado novo do servico sempre substitui qualquer posicao local
        # de skip/back: o snapshot antigo pode ja estar obsoleto (outra
        # decisao, undo, treino ou scan aconteceu em algum lugar).
        if state.current is not None:
            self._janela = [state.current, *state.upcoming]
        else:
            self._janela = []
        self._posicao = 0

        # A fila em baixo e alimentada em _atualiza_exibicao, nao aqui: ela
        # destaca a track exibida, e pular/voltar mudam a exibida sem passar
        # por set_state -- o destaque tem que acompanhar as duas entradas.
        self._atualiza_exibicao()

    def _atualiza_combobox(self, state: ReviewState) -> None:
        """Popula o seletor de perfil a partir do estado vindo do servico.

        blockSignals para nao disparar _on_profile_changed durante a
        repaginacao -- set_state e chamado justamente por causa de uma troca
        ja feita, e loopar o sinal causaria double refresh.
        """
        self._perfil_combo.blockSignals(True)
        self._perfil_combo.clear()
        self._perfil_combo.addItems(list(state.profiles))
        if state.active_profile in state.profiles:
            self._perfil_combo.setCurrentText(state.active_profile)
        self._perfil_combo.blockSignals(False)

    def _on_profile_changed(self, nome: str) -> None:
        # Sai imediatamente se o nome nao e um perfil real (pode acontecer
        # na repaginacao). Quem muda o estado de fato e set_state, que
        # volta a chamar _atualiza_combobox.
        if not nome or nome not in (self._state.profiles if self._state else ()):
            return
        self.profile_switch_requested.emit(nome)

    def _atualiza_exibicao(self) -> None:
        """Repinta titulo/numeros/palpite/onda a partir de _exibida().

        Chamado tanto por set_state (dado novo do servico) quanto por
        skip/back (navegacao puramente local, sem novo dado) -- e por isso
        que fica separado do resto de set_state.
        """
        atual = self._exibida()

        self._vazio.setVisible(atual is None)
        self._bloco.setVisible(atual is not None)

        self._decisao.set_enabled_targets(atual is not None)
        self._player_bar.set_actions_enabled(atual is not None)

        remaining = self._state.remaining if self._state is not None else 0
        # A fila mostra so as proximas (nao a atual) -- a track em revisao
        # ja esta no header/waveform; a posicao dela na fila e o card de
        # Progresso. set_rows recebe o slice apos a posicao local.
        proximas = (
            tuple(self._janela[self._posicao + 1:]) if atual is not None else ()
        )
        self._proximas.set_rows(proximas)

        if atual is None:
            self._titulo.setText(VAZIO)
            self._subtitulo.setText("")
            self._subtitulo.setVisible(False)
            self._capa.setVisible(False)
            self._waveform.set_row(None)
            self._overview.set_row(None)
            self._carregada = None
            self._carregada_path = None
            self._key_chip.set_key(None)
            return

        self._header.set_track(
            atual,
            remaining=remaining,
            position=self._posicao + 1,
            low_confidence=self._state.low_confidence if self._state else False,
        )
        self._waveform.set_row(atual)
        self._overview.set_row(atual)

        if atual.peaks_path is None and atual.sha1 not in self._pedidos_de_peaks:
            # A track exibida e a prioridade real: e onde o DJ decide, e onde
            # a onda grande ocupa a tela inteira. Pede uma vez por sha1 -- ver
            # o comentario em _pedidos_de_peaks para o motivo da dedup.
            self._pedidos_de_peaks.add(atual.sha1)
            self.peaks_requested.emit(atual.sha1, atual.path_hint)

        if atual.sha1 == self._carregada:
            # Todo decide/undo/train/scan termina em states_changed, e na
            # maioria deles a track exibida continua a mesma. Recarregar aqui
            # zeraria a posicao no meio da escuta -- um scan em andamento
            # emitiria progresso o tempo todo e a track nunca sairia do zero.
            return

        self._carregada = atual.sha1
        # path_hint e str por design (viewmodel nao carrega Path); a conversao
        # mora aqui, na fronteira com o player, para BasePlayer.load(path: Path)
        # nao mentir na anotacao.
        caminho = Path(atual.path_hint)
        # Guardado ANTES de chamar load(): source_changed dispara SINCRONO
        # (mesma thread, conexao direta) de dentro da propria chamada abaixo,
        # entao _quando_player_carrega precisa ja enxergar o caminho que EU
        # pedi para nao se confundir e soltar a propria posse que acabou de
        # tomar.
        self._carregada_path = str(caminho)
        #
        # Carrega parada no trecho mais energetico: o usuario da play.
        # Tocar sozinho a cada avanco transforma a revisao em corrida.
        self._player.load(caminho, int(atual.duration_s * 1000))
        self._player.seek(int(atual.peak_offset_s * 1000))

    def _mostra_capa(self, linha: TrackRow) -> None:
        """Carrega a capa do disco, uma vez por track.

        Sem cache proprio: aqui e uma imagem so, recarregada apenas quando a
        track muda -- diferente da tabela, que pinta dezenas por segundo
        durante o scroll e por isso precisa do PixmapCache.
        """
        if linha.cover_path is None:
            self._capa.clear()
            # setVisible(False) e nao so clear(): o QLabel tem tamanho fixo
            # de 44x44, entao limpar o pixmap deixa o buraco reservado.
            self._capa.setVisible(False)
            return

        pixmap = QPixmap(linha.cover_path)
        if pixmap.isNull():
            # Arquivo corrompido ou formato que o Qt nao abre.
            self._capa.clear()
            self._capa.setVisible(False)
            return
        self._capa.setPixmap(pixmap)
        self._capa.setVisible(True)

    def _atualiza_progresso(self, posicao_ms: int) -> None:
        """Move o playhead da onda -- sem isto ele fica sempre em x=0."""
        if self._carregada is None:
            # O player pode estar tocando a track de OUTRA aba agora (ver
            # _quando_player_carrega) -- pintar o playhead com a posicao dela
            # sobre a onda de uma track diferente e o desencontro que a
            # revisao final pegou.
            return
        duracao = self._player.duration_ms
        if duracao > 0:
            self._waveform.set_progress(posicao_ms / duracao)
            self._overview.set_progress(posicao_ms / duracao)

    def _quando_player_carrega(self, caminho: str) -> None:
        """O player (compartilhado com a Biblioteca) acabou de carregar algo.

        Se o caminho bate com o que ESTA CHAMADA pediu por ultimo, foi a
        propria Revisao que disparou -- nada a fazer. Caso contrario, a
        Biblioteca deu play por cima: a track exibida aqui continua sendo a
        que o servico mandou, mas o player agora toca outra coisa, entao esta
        aba perde a posse (ver _carregada em _atualiza_exibicao e o guard em
        _atualiza_progresso) ate o proximo estado do servico mandar recarregar.
        """
        if caminho != self._carregada_path:
            self._carregada = None

    def recebe_peaks(self, sha1: str, caminho: str) -> None:
        """Chamado pelo worker quando peaks_ready dispara -- sem refresh completo."""
        self._pedidos_de_peaks.discard(sha1)
        self._waveform.set_peaks_path(sha1, caminho)
        self._overview.set_peaks_path(sha1, caminho)

    def set_notation(self, notation: KeyNotation) -> None:
        """Recebe a preferencia global vinda do alternador da Biblioteca."""
        self._key_chip.set_notation(notation)

    def _pedir_bloco(self) -> None:
        if self._state is None or self._state.remaining == 0:
            return
        resposta = QMessageBox.question(
            self,
            "Aprovar em bloco",
            f"Mover todas as tracks com confianca >= {BULK_MIN_CONFIDENCE}?",
        )
        if resposta == QMessageBox.StandardButton.Yes:
            self.bulk_approve_requested.emit(BULK_MIN_CONFIDENCE)

    def decide_atual(self, rotulo: str) -> None:
        """Chamado pelo atalho de teclado 1/2/3 em MainWindow."""
        sha1 = self.current_sha1
        if sha1 is not None:
            self.decide_requested.emit(sha1, rotulo)

    def remover_atual(self) -> None:
        """Chamado pelo botao Remover e pelo atalho D em MainWindow.

        Sem dialogo de confirmacao, ao contrario do Aprovar em bloco: o
        arquivo vai para a lixeira do SO, que e recuperavel pelo Finder --
        a confirmacao do bloco existe porque ele afeta muitas tracks de uma
        vez, nao porque o destino e irreversivel.
        """
        sha1 = self.current_sha1
        if sha1 is not None:
            self.remove_requested.emit(sha1)

    def pular(self) -> None:
        """Avanca dentro da janela local. Chamado pelo atalho de seta direita."""
        # Navegacao local, sem round-trip ao worker: so avanca dentro do
        # snapshot ja cacheado. Passar do fim (no maximo 4 tracks) so trava
        # ali ate o proximo set_state trazer dado novo -- sem crash, sem
        # wraparound.
        if self._janela:
            self._posicao = min(self._posicao + 1, len(self._janela) - 1)
            self._atualiza_exibicao()

    def voltar(self) -> None:
        """Recua dentro da janela local. Chamado pelo atalho de seta esquerda."""
        if self._janela:
            self._posicao = max(self._posicao - 1, 0)
            self._atualiza_exibicao()

    # ---- superficie de teste --------------------------------------------

    def bloco_visivel(self) -> bool:
        return not self._bloco.isHidden()

    def capa_visivel(self) -> bool:
        return not self._capa.isHidden()

    def acionar_empty_state(self) -> None:
        self._vazio.acionar("Escanear")
