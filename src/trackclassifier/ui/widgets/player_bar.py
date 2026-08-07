"""Barra de transporte da aba Revisao.

Fica na Revisao e nao no rodape da janela de proposito: so ela tem track
corrente. O Space e desabilitado fora dela (ver window._atualiza_atalhos_de_revisao)
e a Biblioteca nao toca nada -- um rodape global prometeria playback la.

Nao ha logica de reproducao aqui. Tudo e ligacao de sinal ao BasePlayer que
a aba ja recebe; em especial o rotulo do botao vem de playing_changed e nao
de um flag proprio, senao o atalho de teclado (que chama player.toggle()
sem passar por este widget) dessincronizaria o botao na primeira vez.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..tokens import (
    FONT_FAMILY_SANS,
    FONT_SIZE_CAPTION,
    SIZE_CONTROL_BASE,
    SIZE_CONTROL_PRIMARY,
    SPACE_3,
    SPACE_5,
)
from ..typography import estiliza_label
from ..viewmodel import format_duration
from .volume_rail import VolumeRail

_PLAY = "▶"
_PAUSE = "❚❚"
_VOLUME_INICIAL = 80


class PlayerBar(QWidget):
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

        # Altura da BARRA, nao do botao: o botao usa o token de controle
        # base. Ate a v0.1 os dois usavam SIZE_CONTROL_PRIMARY, e o botao
        # de 36px numa barra de 36px encostava nas duas bordas.
        self.setFixedHeight(SIZE_CONTROL_PRIMARY)

        self._botao = QPushButton(_PLAY)
        self._botao.setFixedSize(SIZE_CONTROL_BASE, SIZE_CONTROL_BASE)
        # Familia sans e padding zerado so aqui: o QSS veste todo
        # QPushButton com a mono de 10px, e nem JetBrains Mono nem seus
        # fallbacks tem ▶ (U+25B6) ou ❚ (U+275A) -- o Qt caia num glifo de
        # substituicao de poucos pixels no canto do botao. O padding do QSS
        # (6px 12px) ainda por cima empurrava o desenho para fora de um
        # botao de 28x28.
        self._botao.setStyleSheet(
            f"font-family: {FONT_FAMILY_SANS}; font-size: {FONT_SIZE_CAPTION};"
            "padding: 0px;"
        )
        self._botao.clicked.connect(self._player.toggle)

        self._tempo = QLabel("")
        self._tempo.setObjectName("Numeric")

        self._rotulo_volume = QLabel()
        self._rotulo_volume.setObjectName("MicroLabel")
        estiliza_label(self._rotulo_volume, "Volume")

        self.volume = VolumeRail(_VOLUME_INICIAL)
        self.volume.valor_mudou.connect(self._muda_volume)

        layout = QHBoxLayout(self)
        # Margem vertical menor que a horizontal: a barra tem 36px de altura
        # fixa e o botao ocupa 28 deles.
        layout.setContentsMargins(SPACE_5, SPACE_3, SPACE_5, SPACE_3)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self._botao)
        layout.addWidget(self._tempo)
        layout.addStretch(1)
        layout.addWidget(self._rotulo_volume)
        layout.addWidget(self.volume)

        self._player.position_changed.connect(self._muda_posicao)
        self._player.duration_changed.connect(self._muda_duracao)
        self._player.playing_changed.connect(self._muda_estado)

        self._muda_volume(_VOLUME_INICIAL)
        self._atualiza_tempo()

    # ---- reacoes aos sinais do player ----------------------------------

    def _muda_posicao(self, ms: int) -> None:
        self._posicao_ms = ms
        self._atualiza_tempo()

    def _muda_duracao(self, ms: int) -> None:
        self._duracao_ms = ms
        self._atualiza_tempo()

    def _muda_estado(self, tocando: bool) -> None:
        self._botao.setText(_PAUSE if tocando else _PLAY)

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

    def texto_do_botao(self) -> str:
        return self._botao.text()

    def altura_do_botao(self) -> int:
        return self._botao.height()

    def acionar_play(self) -> None:
        self._botao.click()
