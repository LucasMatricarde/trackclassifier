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

from .viewmodel import ReviewState, format_duration
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
        return self._state.current.sha1 if self._state and self._state.current else None

    def empty_text(self) -> str:
        return VAZIO

    def set_state(self, state: ReviewState) -> None:
        self._state = state
        atual = state.current

        if atual is None:
            self._titulo.setText(VAZIO)
            self._numeros.setText("")
            self._palpite.setText("")
            self._proximas.setText("")
            self._waveform.set_row(None)
        else:
            self._titulo.setText(atual.filename)
            self._numeros.setText(
                f"{atual.bpm:.0f} BPM   {format_duration(atual.duration_s)}   "
                f"restam {state.remaining}"
            )
            self._palpite.setText(
                f"Palpite: {atual.predicted}   confianca {atual.confidence:.2f}"
            )
            self._proximas.setText(
                "Proximas: " + "   ".join(linha.filename for linha in state.upcoming)
            )
            self._waveform.set_row(atual)
            # Carrega parada no trecho mais energetico: o usuario da play.
            # Tocar sozinho a cada avanco transforma a revisao em corrida.
            self._player.load(atual.path_hint, int(atual.duration_s * 1000))
            self._player.seek(int(atual.peak_offset_s * 1000))

        self._aviso.setText(
            "Modelo com poucos exemplos: confianca reduzida pela metade."
            if state.low_confidence
            else ""
        )

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
            self.skip_requested.emit()
            return
        if chave == Qt.Key.Key_Left:
            self.back_requested.emit()
            return
        if chave == Qt.Key.Key_Z and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.undo_requested.emit()
            return
        super().keyPressEvent(event)
