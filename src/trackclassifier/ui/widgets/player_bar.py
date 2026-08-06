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
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from ..tokens import SIZE_CONTROL_PRIMARY, SPACE_4, SPACE_5
from ..viewmodel import format_duration

_PLAY = "▶"
_PAUSE = "❚❚"
_VOLUME_INICIAL = 80


class PlayerBar(QWidget):
    def __init__(self, player, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # objectName e o que liga a regra QWidget#PlayerBar do app.qss --
        # ela existia desde a fase 1 sem nenhum widget para vestir.
        self.setObjectName("PlayerBar")
        self._player = player
        self._posicao_ms = 0
        self._duracao_ms = 0

        self._botao = QPushButton(_PLAY)
        self._botao.setFixedSize(SIZE_CONTROL_PRIMARY, SIZE_CONTROL_PRIMARY)
        self._botao.clicked.connect(self._player.toggle)

        self._tempo = QLabel("")
        self._tempo.setObjectName("Numeric")

        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setValue(_VOLUME_INICIAL)
        self._volume.setFixedWidth(100)
        self._volume.valueChanged.connect(self._muda_volume)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_4, SPACE_5, SPACE_4)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self._botao)
        layout.addWidget(self._tempo)
        layout.addStretch(1)
        layout.addWidget(QLabel("Volume"))
        layout.addWidget(self._volume)

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

    def acionar_play(self) -> None:
        self._botao.click()
