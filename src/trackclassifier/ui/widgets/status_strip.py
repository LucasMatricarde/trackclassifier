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
puxar o olho. A cor e QSS (QLabel#StatusDot[state=...] no app.qss), nao
QPainter: setProperty()+repolir() troca o seletor que casa, o mesmo idioma
que settings_form.py ja usa pro campo invalido e pro chip de contagem.
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..tokens import SPACE_4
from ..typography import aplica_tracking, repolir

#: Altura da faixa no mockup 3a.
ALTURA = 25

#: Diametro do ponto de estado.
_PONTO = 6


class StatusStrip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusStrip")
        self.setFixedHeight(ALTURA)

        self._ponto = QLabel()
        self._ponto.setObjectName("StatusDot")
        self._ponto.setFixedSize(_PONTO, _PONTO)
        self._ponto.setProperty("state", "success")
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
        self._set_estado("success")
        self._texto.setText(
            f"Scan concluido · {tracks} tracks · {analisadas} analisadas · "
            f"{pendentes} pendentes"
        )

    def mostra_scan(self, concluidas: int, total: int, nome: str) -> None:
        """Scan em andamento. Cor de aviso: o resumo ainda nao vale."""
        self._set_estado("warning")
        self._texto.setText(f"Escaneando {concluidas}/{total} · {nome}")

    def _set_estado(self, estado: str) -> None:
        self._ponto.setProperty("state", estado)
        repolir(self._ponto)
