"""Resumo permanente do acervo, no rodape esquerdo da janela.

Diferente do statusBar().showMessage() que MainWindow ja usa para progresso
de scan e erros: aquele e transitorio (some sozinho ou na proxima
mensagem), este e o estado de repouso -- "quantas tracks existem, quantas
ja tem classe" -- e fica escrito o tempo todo. Os dois convivem no mesmo
QStatusBar: showMessage() cobre este widget por cima enquanto dura (e o
comportamento padrao do Qt para o widget da esquerda de uma status bar), e
some sozinho revelando o resumo de novo.

O ponto colorido antes do texto e o unico lugar da faixa que muda de cor --
o texto ao lado fica sempre em text.muted, porque so um sinal por vez deve
puxar o olho.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..colors import para_qcolor
from ..tokens import COLOR_STATE_SUCCESS, COLOR_STATE_WARNING, SPACE_4
from ..typography import aplica_tracking

#: Altura da faixa no mockup 3a.
ALTURA = 25

#: Diametro do ponto de estado.
_PONTO = 6


class _Ponto(QWidget):
    """Circulo solido do tamanho fixo de _PONTO. QLabel nao desenha forma
    nenhuma sozinho -- seria preciso um pixmap so para um circulo de 6px."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_PONTO, _PONTO)
        self._cor = para_qcolor(COLOR_STATE_SUCCESS)

    def set_cor(self, cor_token: str) -> None:
        self._cor = para_qcolor(cor_token)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (assinatura do Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._cor)
        painter.drawEllipse(QRectF(0, 0, _PONTO, _PONTO))


class StatusStrip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusStrip")
        self.setFixedHeight(ALTURA)

        self._ponto = _Ponto()
        self._texto = QLabel()
        self._texto.setObjectName("MicroLabel")
        # SO tracking, sem caixa alta: diferente de todo outro MicroLabel do
        # app (cabecalho de coluna, HintBar), o mockup mostra este texto em
        # frase normal -- "Scan concluido", nao "SCAN CONCLUIDO". Uma capa
        # nao pode passar por .upper() de qualquer forma: e nome de arquivo
        # de verdade, e "TRACK1.WAV" mentiria sobre o nome real no disco.
        aplica_tracking(self._texto)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_4)
        layout.addWidget(self._ponto)
        layout.addWidget(self._texto)
        layout.addStretch(1)

    def mostra_resumo(self, tracks: int, analisadas: int, pendentes: int) -> None:
        """Estado de repouso: scan concluido, o que ha para revisar."""
        self._ponto.set_cor(COLOR_STATE_SUCCESS)
        self._texto.setText(
            f"Scan concluido · {tracks} tracks · {analisadas} analisadas · "
            f"{pendentes} pendentes"
        )

    def mostra_scan(self, concluidas: int, total: int, nome: str) -> None:
        """Scan em andamento. Cor de aviso: o resumo ainda nao vale."""
        self._ponto.set_cor(COLOR_STATE_WARNING)
        self._texto.setText(f"Escaneando {concluidas}/{total} · {nome}")
