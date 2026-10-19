"""Barra de transporte da aba Revisao.

Fica na Revisao e nao no rodape da janela de proposito: so ela tem track
corrente. O Space e desabilitado fora dela (ver window._atualiza_atalhos_de_revisao)
e a Biblioteca nao toca nada -- um rodape global prometeria playback la.

Nao ha logica de reproducao aqui. Tudo e ligacao de sinal ao BasePlayer que
a aba ja recebe; em especial o rotulo do botao vem de playing_changed e nao
de um flag proprio, senao o atalho de teclado (que chama player.toggle()
sem passar por este widget) dessincronizaria o botao na primeira vez.

O grupo Acoes (Pular / Remover / Aprovar em bloco) mora aqui e nao na
DecisionBar porque sao acoes SOBRE A TRACK, nao classificacoes: o mockup os
poe na mesma faixa do transporte, e a barra de decisao fica so com os tres
rotulos. Quem decide o que cada um faz e a ReviewTab -- este widget so
emite o pedido.
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..icons import icon
from ..tokens import (
    COLOR_TEXT_PRIMARY,
    SIZE_CONTROL_TRANSPORT,
    SIZE_CONTROL_TRANSPORT_PLAY,
    SIZE_CONTROL_VOLUME_RAIL,
    SIZE_ICON_BASE,
    SIZE_ICON_LARGE,
    SPACE_3,
    SPACE_5,
)
from ..typography import estiliza_label
from ..viewmodel import format_duration
from .vdivider import VDivider
from .volume_rail import VolumeRail

_VOLUME_INICIAL = 80



def _com_kbd(botao: QPushButton, tecla: str) -> QHBoxLayout:
    """Botao de acao com a tecla de atalho desenhada ao lado, como no mockup.

    O kbd fica FORA do botao, nao dentro: um filho posicionado a mao dentro
    do QPushButton nao acompanha redimensionamento, e incluir a tecla no
    texto ("Pular  S") faria o leitor de tela anunciar "Pular S" como se
    fosse uma palavra so.
    """
    grupo = QHBoxLayout()
    grupo.setSpacing(SPACE_3)
    kbd = QLabel(tecla)
    kbd.setObjectName("Kbd")
    grupo.addWidget(botao)
    grupo.addWidget(kbd)
    return grupo


class PlayerBar(QWidget):
    previous_requested = Signal()
    next_requested = Signal()
    #: Pular e Remover nao sabem para qual track vao: quem sabe e a aba,
    #: dona da janela local de navegacao.
    skip_requested = Signal()
    remove_requested = Signal()
    bulk_requested = Signal()

    def __init__(self, player, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # objectName e o que liga a regra QWidget#PlayerBar do app.qss --
        # ela existia desde a fase 1 sem nenhum widget para vestir.
        self.setObjectName("PlayerBar")
        # Sem WA_StyledBackground o Qt IGNORA o `background` que o QSS da a
        # uma subclasse de QWidget que nao reimplementa paintEvent -- a
        # regra QWidget#PlayerBar existia e nao pintava nada, e a barra
        # ficava com o fundo da janela em vez do painel do mockup.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._player = player
        self._posicao_ms = 0
        self._duracao_ms = 0

        self.setFixedHeight(SIZE_CONTROL_TRANSPORT)

        # Icones SVG tintados por token, criados aqui (nao no modulo) porque
        # icon() rasteriza com QSvgRenderer, que precisa de QApplication ativo.
        icone_play = icon("play", COLOR_TEXT_PRIMARY, SIZE_ICON_LARGE)
        icone_pause = icon("pause", COLOR_TEXT_PRIMARY, SIZE_ICON_LARGE)
        icone_prev = icon("prev", COLOR_TEXT_PRIMARY, SIZE_ICON_BASE)
        icone_next = icon("next", COLOR_TEXT_PRIMARY, SIZE_ICON_BASE)

        self._botao = QPushButton()
        self._botao.setObjectName("TransportPlay")
        self._botao.setFixedSize(SIZE_CONTROL_TRANSPORT_PLAY, SIZE_CONTROL_TRANSPORT_PLAY)
        self._botao.setIcon(icone_play)
        self._botao.setIconSize(QSize(SIZE_ICON_LARGE, SIZE_ICON_LARGE))
        self._botao.clicked.connect(self._player.toggle)

        self._previous = QPushButton()
        self._previous.setObjectName("TransportNav")
        self._previous.setAccessibleName("Musica anterior")
        self._previous.setIcon(icone_prev)
        self._previous.setIconSize(QSize(SIZE_ICON_BASE, SIZE_ICON_BASE))
        self._previous.clicked.connect(self.previous_requested)
        self._next = QPushButton()
        self._next.setObjectName("TransportNav")
        self._next.setAccessibleName("Proxima musica")
        self._next.setIcon(icone_next)
        self._next.setIconSize(QSize(SIZE_ICON_BASE, SIZE_ICON_BASE))
        self._next.clicked.connect(self.next_requested)

        self._tempo = QLabel("")
        self._tempo.setObjectName("Numeric")

        self._rotulo_volume = QLabel()
        self._rotulo_volume.setObjectName("MicroLabel")
        estiliza_label(self._rotulo_volume, "Volume")

        self.volume = VolumeRail(_VOLUME_INICIAL, SIZE_CONTROL_VOLUME_RAIL)
        self.volume.valor_mudou.connect(self._muda_volume)

        rotulo_acoes = QLabel()
        rotulo_acoes.setObjectName("MicroLabel")
        estiliza_label(rotulo_acoes, "Acoes")

        self.botao_pular = QPushButton("Pular")
        self.botao_pular.setAccessibleName("Pular esta track (S)")
        self.botao_pular.clicked.connect(self.skip_requested)
        self.botao_remover = QPushButton("Remover")
        self.botao_remover.setAccessibleName("Remover esta track para a lixeira (D)")
        self.botao_remover.clicked.connect(self.remove_requested)
        icone_check = icon("check", COLOR_TEXT_PRIMARY, SIZE_ICON_BASE)

        self.botao_bloco = QPushButton()
        self.botao_bloco.setObjectName("BulkAction")
        self.botao_bloco.setIcon(icone_check)
        self.botao_bloco.setIconSize(QSize(SIZE_ICON_BASE, SIZE_ICON_BASE))
        self.botao_bloco.clicked.connect(self.bulk_requested)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_3, SPACE_5, SPACE_3)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self._botao)
        layout.addWidget(self._previous)
        layout.addWidget(self._next)
        layout.addWidget(VDivider())
        layout.addWidget(self._rotulo_volume)
        layout.addWidget(self.volume)
        layout.addWidget(self._tempo)
        layout.addStretch(1)
        layout.addWidget(rotulo_acoes)
        layout.addLayout(_com_kbd(self.botao_pular, "S"))
        layout.addLayout(_com_kbd(self.botao_remover, "D"))
        layout.addWidget(self.botao_bloco)

        self._icone_play = icone_play
        self._icone_pause = icone_pause

        self._player.position_changed.connect(self._muda_posicao)
        self._player.duration_changed.connect(self._muda_duracao)
        self._player.playing_changed.connect(self._muda_estado)

        self._muda_volume(_VOLUME_INICIAL)
        self._atualiza_tempo()

    # ---- acoes ----------------------------------------------------------

    def set_bulk_label(self, limiar: float) -> None:
        self.botao_bloco.setText(f"Aprovar em bloco (confianca ≥ {limiar})")

    def set_actions_enabled(self, enabled: bool) -> None:
        """Sem track na fila nao ha o que pular, remover ou aprovar."""
        for botao in (self.botao_pular, self.botao_remover, self.botao_bloco):
            botao.setEnabled(enabled)

    # ---- reacoes aos sinais do player ----------------------------------

    def _muda_posicao(self, ms: int) -> None:
        self._posicao_ms = ms
        self._atualiza_tempo()

    def _muda_duracao(self, ms: int) -> None:
        self._duracao_ms = ms
        self._atualiza_tempo()

    def _muda_estado(self, tocando: bool) -> None:
        self._botao.setIcon(self._icone_pause if tocando else self._icone_play)

    def _muda_volume(self, valor: int) -> None:
        self._player.set_volume(valor / 100)

    def _atualiza_tempo(self) -> None:
        self._tempo.setText(
            f"{format_duration(self._posicao_ms / 1000)} / "
            f"{format_duration(self._duracao_ms / 1000)}"
        )

    # ---- superficie de teste -------------------------------------------

    def texto_do_tempo(self) -> str:
        return self._tempo.text()

    def icon_do_botao(self) -> QIcon:
        return self._botao.icon()

    def altura_do_botao(self) -> int:
        return self._botao.height()

    def acionar_play(self) -> None:
        self._botao.click()
