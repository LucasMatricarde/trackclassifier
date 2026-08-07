"""Aba Revisao: uma track por vez, decidida pelo teclado.

O teclado em si (QShortcut, contexto WindowShortcut) vive em MainWindow --
ver o comentario la para o motivo. Este widget so expoe os metodos que os
atalhos chamam (decide_atual/pular/voltar), sem tratar QKeyEvent.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..keys import KeyNotation
from .tokens import FONT_SIZE_LARGE, SIZE_ART_PLAYER, SPACE_1, SPACE_5, SPACE_6
from .typography import estiliza_label
from .viewmodel import ReviewState, TrackRow, format_duration
from .widgets.decision_bar import DecisionBar
from .widgets.empty_state import Acao, EmptyState
from .widgets.guess_bar import GuessBar
from .widgets.key_chip import KeyChip
from .widgets.metric_block import MetricBlock
from .widgets.player_bar import PlayerBar
from .widgets.upcoming_list import UpcomingList
from .widgets.waveform_view import WaveformView

VAZIO_TITULO = "Fila vazia"
VAZIO_SUBTITULO = "Nenhuma track nova na inbox."
VAZIO = f"{VAZIO_TITULO}. {VAZIO_SUBTITULO}"
BULK_MIN_CONFIDENCE = 0.75


class ReviewTab(QWidget):
    decide_requested = Signal(str, str)
    undo_requested = Signal()
    bulk_approve_requested = Signal(float)
    #: (sha1, caminho do arquivo de audio) -- gatilho do computo preguicoso
    #: dos buckets da track atual.
    peaks_requested = Signal(str, str)
    scan_requested = Signal()

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
        #: sha1 ja solicitados nesta sessao -- evita reenfileirar compute_peaks
        #: a cada refresh enquanto o computo de uma track continuar falhando
        #: (disco cheio, arquivo removido). Sem isto, uma falha persistente
        #: vira um loop sem fim: refresh -> pede de novo -> computa de novo
        #: -> refresh de novo, travando a thread do servico.
        self._pedidos_de_peaks: set[str] = set()

        self._titulo = QLabel(VAZIO)
        self._titulo.setObjectName("TrackTitle")
        self._titulo.setStyleSheet(f"font-size: {FONT_SIZE_LARGE};")
        self._subtitulo = QLabel("")
        self._subtitulo.setObjectName("TrackArtist")

        self._capa = QLabel()
        self._capa.setFixedSize(SIZE_ART_PLAYER, SIZE_ART_PLAYER)
        self._capa.setScaledContents(True)

        self._key_chip = KeyChip()

        # Um bloco por numero, com o micro-label em cima: quatro valores
        # numa string so ("138 BPM  6:12  restam 47") obrigam a ler a
        # frase inteira para achar um deles.
        self._bpm = MetricBlock("BPM")
        self._duracao = MetricBlock("Duracao")
        self._restam = MetricBlock("Restam")
        self._chave = MetricBlock("Key")

        self._palpite = GuessBar()
        self._proximas = UpcomingList()
        self._rotulo_proximas = QLabel()
        self._rotulo_proximas.setObjectName("MicroLabel")
        estiliza_label(self._rotulo_proximas, "Proximas")

        self._waveform = WaveformView()
        self._waveform.seek_requested.connect(self._player.seek_fraction)
        self._player.position_changed.connect(self._atualiza_progresso)

        self._decisao = DecisionBar()
        self._decisao.set_bulk_label(BULK_MIN_CONFIDENCE)
        self._decisao.decidido.connect(self.decide_atual)
        self._decisao.bloco_pedido.connect(self._pedir_bloco)

        textos = QVBoxLayout()
        textos.setSpacing(SPACE_1)
        textos.addWidget(self._titulo)
        textos.addWidget(self._subtitulo)

        numeros = QHBoxLayout()
        numeros.setSpacing(20)
        numeros.addWidget(self._chave)
        numeros.addWidget(self._bpm)
        numeros.addWidget(self._duracao)
        numeros.addWidget(self._restam)

        topo = QHBoxLayout()
        topo.setSpacing(SPACE_5)
        topo.addWidget(self._capa)
        topo.addLayout(textos, 1)
        topo.addWidget(self._key_chip)
        topo.addLayout(numeros)

        self._player_bar = PlayerBar(self._player)

        # Tudo que so faz sentido com uma track vira um widget so: com a fila
        # vazia ele some inteiro e o EmptyState ocupa o lugar. Antes o
        # stretch=1 da onda esticava um bloco vazio pela altura da janela.
        self._bloco = QWidget()
        conteudo = QVBoxLayout(self._bloco)
        conteudo.setContentsMargins(0, 0, 0, 0)
        conteudo.setSpacing(SPACE_5)
        conteudo.addLayout(topo)
        conteudo.addWidget(self._waveform, 1)
        conteudo.addWidget(self._player_bar)
        conteudo.addWidget(self._palpite)
        conteudo.addWidget(self._rotulo_proximas)
        conteudo.addWidget(self._proximas)

        self._vazio = EmptyState(VAZIO_TITULO, VAZIO_SUBTITULO, (Acao("Escanear"),))
        self._vazio.acao_clicada.connect(lambda _rotulo: self.scan_requested.emit())

        corpo = QVBoxLayout()
        corpo.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        corpo.setSpacing(SPACE_5)
        corpo.addWidget(self._vazio, 1)
        corpo.addWidget(self._bloco, 1)

        layout = QVBoxLayout(self)
        # O rodape encosta nas bordas: e uma faixa de chrome da janela, nao
        # conteudo. Por isso a margem fica no corpo, e nao no layout externo.
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(corpo, 1)
        layout.addWidget(self._decisao)

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

        # Um estado novo do servico sempre substitui qualquer posicao local
        # de skip/back: o snapshot antigo pode ja estar obsoleto (outra
        # decisao, undo, treino ou scan aconteceu em algum lugar).
        if state.current is not None:
            self._janela = [state.current, *state.upcoming]
        else:
            self._janela = []
        self._posicao = 0

        proximas = state.upcoming if state.current is not None else ()
        self._proximas.set_rows(tuple(proximas))
        self._rotulo_proximas.setVisible(bool(proximas))
        self._atualiza_exibicao()

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

        if atual is None:
            self._titulo.setText(VAZIO)
            self._subtitulo.setText("")
            self._subtitulo.setVisible(False)
            self._capa.setVisible(False)
            for bloco in (self._chave, self._bpm, self._duracao, self._restam):
                bloco.set_value(None)
            self._palpite.set_guess(None, None, low_confidence=False)
            self._waveform.set_row(None)
            self._carregada = None
            self._key_chip.set_key(None)
            return

        remaining = self._state.remaining if self._state is not None else 0
        self._titulo.setText(atual.display_title)
        # Junta so o que existe: com um dos dois ausente, um " · " solto no
        # meio parece dado faltando por bug em vez de tag ausente. Sem
        # nenhum dos dois a linha some -- um QLabel vazio continuaria
        # ocupando altura e empurrando o titulo para cima do centro.
        legenda = " · ".join(parte for parte in (atual.artist, atual.genre) if parte)
        self._subtitulo.setText(legenda)
        self._subtitulo.setVisible(bool(legenda))
        self._mostra_capa(atual)
        self._key_chip.set_key(atual.key)
        # O chip de Camelot ja mostra a key; o bloco metrico dela existiria
        # so para repetir. Fica escondido -- e por isso set_value aceita
        # None em vez de a Revisao montar tres blocos e um chip solto.
        self._chave.set_value(None)
        self._bpm.set_value(f"{atual.bpm:.0f}" if atual.bpm else None)
        self._duracao.set_value(format_duration(atual.duration_s))
        self._restam.set_value(str(remaining))
        self._palpite.set_guess(
            atual.predicted,
            atual.confidence,
            low_confidence=self._state.low_confidence if self._state else False,
        )
        self._waveform.set_row(atual)

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
        #
        # Carrega parada no trecho mais energetico: o usuario da play.
        # Tocar sozinho a cada avanco transforma a revisao em corrida.
        self._player.load(Path(atual.path_hint), int(atual.duration_s * 1000))
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
        duracao = self._player.duration_ms
        if duracao > 0:
            self._waveform.set_progress(posicao_ms / duracao)

    def recebe_peaks(self, sha1: str, caminho: str) -> None:
        """Chamado pelo worker quando peaks_ready dispara -- sem refresh completo."""
        self._pedidos_de_peaks.discard(sha1)
        self._waveform.set_peaks_path(sha1, caminho)

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
