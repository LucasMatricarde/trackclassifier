"""Aba Revisao: uma track por vez, decidida pelo teclado."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .viewmodel import ReviewState, TrackRow, format_duration
from .widgets.waveform_view import WaveformView

VAZIO = "Fila vazia. Use Escanear para procurar tracks novas na inbox."
BULK_MIN_CONFIDENCE = 0.75

#: Tecla -> rotulo do dominio. As tres sao adjacentes de proposito: a mao
#: fica parada entre decisoes.
_TECLAS = {
    Qt.Key.Key_1: "-1",
    Qt.Key.Key_2: "neutra",
    Qt.Key.Key_3: "+1",
}


class ReviewTab(QWidget):
    decide_requested = Signal(str, str)
    undo_requested = Signal()
    skip_requested = Signal()
    back_requested = Signal()
    bulk_approve_requested = Signal(float)

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

        self._titulo = QLabel(VAZIO)
        self._titulo.setObjectName("TrackTitle")
        self._numeros = QLabel("")
        self._numeros.setObjectName("Numeric")
        self._palpite = QLabel("")
        self._aviso = QLabel("")
        self._aviso.setObjectName("SectionLabel")
        self._legenda = QLabel(
            "1 = -1   2 = neutra   3 = +1   espaco = tocar   -> pular   "
            "<- voltar   Cmd+Z = desfazer"
        )
        self._legenda.setObjectName("SectionLabel")
        self._proximas = QLabel("")
        self._proximas.setObjectName("SectionLabel")

        self._waveform = WaveformView()
        self._waveform.seek_requested.connect(self._player.seek_fraction)

        botao_bloco = QPushButton(f"Aprovar em bloco (confianca >= {BULK_MIN_CONFIDENCE})")
        botao_bloco.clicked.connect(self._pedir_bloco)

        topo = QHBoxLayout()
        topo.addWidget(self._titulo, 1)
        topo.addWidget(self._numeros)

        layout = QVBoxLayout(self)
        layout.addLayout(topo)
        layout.addWidget(self._waveform, 1)
        layout.addWidget(self._palpite)
        layout.addWidget(self._aviso)
        layout.addWidget(self._legenda)
        layout.addWidget(self._proximas)
        layout.addWidget(botao_bloco)

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

        self._proximas.setText(
            "Proximas: " + "   ".join(linha.filename for linha in state.upcoming)
            if state.current is not None
            else ""
        )
        self._aviso.setText(
            "Modelo com poucos exemplos: confianca reduzida pela metade."
            if state.low_confidence
            else ""
        )
        self._atualiza_exibicao()

    def _atualiza_exibicao(self) -> None:
        """Repinta titulo/numeros/palpite/onda a partir de _exibida().

        Chamado tanto por set_state (dado novo do servico) quanto por
        skip/back (navegacao puramente local, sem novo dado) -- e por isso
        que fica separado do resto de set_state.
        """
        atual = self._exibida()

        if atual is None:
            self._titulo.setText(VAZIO)
            self._numeros.setText("")
            self._palpite.setText("")
            self._waveform.set_row(None)
            return

        remaining = self._state.remaining if self._state is not None else 0
        self._titulo.setText(atual.filename)
        self._numeros.setText(
            f"{atual.bpm:.0f} BPM   {format_duration(atual.duration_s)}   restam {remaining}"
        )
        self._palpite.setText(f"Palpite: {atual.predicted}   confianca {atual.confidence:.2f}")
        self._waveform.set_row(atual)
        # Carrega parada no trecho mais energetico: o usuario da play.
        # Tocar sozinho a cada avanco transforma a revisao em corrida.
        self._player.load(atual.path_hint, int(atual.duration_s * 1000))
        self._player.seek(int(atual.peak_offset_s * 1000))

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

    def keyPressEvent(self, event) -> None:
        sha1 = self.current_sha1
        chave = event.key()

        if chave in _TECLAS and sha1 is not None:
            self.decide_requested.emit(sha1, _TECLAS[chave])
            return
        if chave == Qt.Key.Key_Space:
            self._player.toggle()
            return
        if chave == Qt.Key.Key_Right:
            # Navegacao local, sem round-trip ao worker: so avanca dentro do
            # snapshot ja cacheado. Passar do fim (no maximo 4 tracks) so
            # trava ali ate o proximo set_state trazer dado novo -- sem
            # crash, sem wraparound.
            if self._janela:
                self._posicao = min(self._posicao + 1, len(self._janela) - 1)
                self._atualiza_exibicao()
            self.skip_requested.emit()
            return
        if chave == Qt.Key.Key_Left:
            if self._janela:
                self._posicao = max(self._posicao - 1, 0)
                self._atualiza_exibicao()
            self.back_requested.emit()
            return
        if chave == Qt.Key.Key_Z and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.undo_requested.emit()
            return
        super().keyPressEvent(event)
