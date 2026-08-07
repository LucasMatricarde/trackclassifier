"""Balanco do treino: o dado mais acionavel da aba Modelo.

Nenhuma metrica revela que a biblioteca tem 51 animadas contra 89 neutras
-- e e isso que explica os erros. A aba tem que terminar em "o que faco
agora", e a resposta quase sempre e a classe minoritaria.
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..tokens import (
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_SECONDARY,
    FONT_SIZE_CAPTION,
    SPACE_2,
    SPACE_5,
    classification_base,
)
from ..typography import estiliza_label
from ..viewmodel import LABELS_EM_ORDEM
from .meter import Meter

_CLASSE = {"+1": "animada", "neutra": "neutro", "-1": "lento"}

_ALTURA_BARRA = 6
#: Abaixo disto a classe minoritaria vira recomendacao na tela. Acima, o
#: treino esta equilibrado o bastante e o texto so ocuparia espaco.
_LIMIAR_DESBALANCO = 0.70


def recomendacao(counts: tuple[int, ...]) -> str | None:
    """Texto derivado, nao fixo: some quando o treino esta equilibrado."""
    maior = max(counts, default=0)
    if maior == 0:
        # Biblioteca vazia nao esta desbalanceada, esta vazia. O empty
        # state da aba cobre esse caso, e uma recomendacao aqui mandaria
        # rotular uma classe num acervo sem nenhuma track.
        return None
    indice = min(range(len(counts)), key=lambda i: counts[i])
    proporcao = counts[indice] / maior
    if proporcao >= _LIMIAR_DESBALANCO:
        return None
    rotulo = LABELS_EM_ORDEM[indice]
    maior_rotulo = LABELS_EM_ORDEM[counts.index(maior)]
    return (
        f"{rotulo} tem {proporcao:.0%} dos exemplos de {maior_rotulo}. "
        f"Rotular mais {rotulo} e o que mais reduz o erro agora."
    )


class ClassBalance(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        titulo = QLabel()
        titulo.setObjectName("MicroLabel")
        estiliza_label(titulo, "Balanco do treino")

        self._contagens: list[QLabel] = []
        self._barras: list[Meter] = []

        barras = QVBoxLayout()
        barras.setContentsMargins(0, 0, 0, 0)
        # O mockup usa 10 entre classes; a escala tem 8 (SPACE_4) e 12
        # (SPACE_5). Fica com SPACE_5 -- inventar um valor fora da escala
        # e o comeco de nao ter escala nenhuma.
        barras.setSpacing(SPACE_5)
        for rotulo in LABELS_EM_ORDEM:
            barras.addWidget(self._faixa(rotulo))

        self.recomendacao_label = QLabel("")
        self.recomendacao_label.setWordWrap(True)
        self.recomendacao_label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};"
            f"border-top: 1px solid {COLOR_BORDER_SUBTLE}; padding-top: 10px;"
        )
        self.recomendacao_label.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_5)
        layout.addWidget(titulo)
        layout.addLayout(barras)
        layout.addWidget(self.recomendacao_label)
        layout.addStretch(1)

    def _faixa(self, rotulo: str) -> QWidget:
        cor = classification_base(_CLASSE[rotulo])

        nome = QLabel(rotulo)
        nome.setObjectName("Numeric")
        nome.setStyleSheet(f"color: {cor}; font-size: {FONT_SIZE_CAPTION};")

        contagem = QLabel("0")
        contagem.setObjectName("Numeric")
        contagem.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};"
        )
        self._contagens.append(contagem)

        topo = QHBoxLayout()
        topo.setContentsMargins(0, 0, 0, 0)
        topo.addWidget(nome)
        topo.addStretch(1)
        topo.addWidget(contagem)

        barra = Meter(cor, _ALTURA_BARRA)
        self._barras.append(barra)

        faixa = QWidget()
        layout = QVBoxLayout(faixa)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_2)
        layout.addLayout(topo)
        layout.addWidget(barra)
        return faixa

    def proporcao(self, indice: int) -> float:
        return self._barras[indice].fraction()

    def contagem(self, indice: int) -> QLabel:
        return self._contagens[indice]

    def set_counts(self, counts: tuple[int, ...]) -> None:
        maior = max(counts, default=0)
        for indice, valor in enumerate(counts):
            self._contagens[indice].setText(str(valor))
            # Normaliza pela maior, nao pelo total: com 74/89/51 o olho
            # compara as classes entre si, que e a pergunta que a barra
            # responde. Pelo total, as tres ficariam parecidas.
            self._barras[indice].set_fraction(round(valor / maior, 4) if maior else 0.0)

        texto = recomendacao(counts)
        self.recomendacao_label.setText(texto or "")
        self.recomendacao_label.setVisible(texto is not None)
