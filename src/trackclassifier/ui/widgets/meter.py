"""Trilho com preenchimento proporcional, pintado a mao.

A primeira versao era um QWidget filho posicionado por setGeometry dentro
de outro. Nao funciona: quem chama set_counts() antes do primeiro layout
calcula a largura sobre o tamanho default do trilho, e o preenchimento
nasce com a largura errada -- na pratica, todas as barras em 100%.
Reagir ao resizeEvent do pai tambem nao resolve, porque o filho so recebe
a largura final depois que o layout do pai roda.

paintEvent nao tem esse problema: a largura vem de self.width() no
momento do desenho, que por definicao e depois do layout.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..colors import para_qcolor
from ..tokens import COLOR_BORDER_SUBTLE, RADIUS_XS


class Meter(QWidget):
    """Barra de progresso sem texto, na altura que o chamador pedir."""

    def __init__(self, cor: str, altura: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cor = cor
        self._fracao = 0.0
        self.setFixedHeight(altura)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def fraction(self) -> float:
        return self._fracao

    def color(self) -> str:
        return self._cor

    def set_color(self, cor: str) -> None:
        """A cor pode depender do VALOR, nao so de qual medidor e este.

        A confianca da Revisao vira warning abaixo de 0.4: e a cor que faz
        "0.31" ser lido como problema sem o usuario precisar lembrar onde
        fica o corte.
        """
        self._cor = cor
        self.update()

    def set_fraction(self, fraction: float) -> None:
        # Clampa aqui em vez de confiar em quem chama: a fracao sai de
        # divisoes com dado de disco (decisoes / retrain_every), e um
        # valor acima de 1 pintaria fora do widget.
        self._fracao = min(1.0, max(0.0, fraction))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (assinatura do Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        altura = float(self.height())
        painter.setBrush(para_qcolor(COLOR_BORDER_SUBTLE))
        painter.drawRoundedRect(
            QRectF(0.0, 0.0, float(self.width()), altura), RADIUS_XS, RADIUS_XS
        )

        largura = self.width() * self._fracao
        if largura <= 0.0:
            return
        painter.setBrush(para_qcolor(self._cor))
        painter.drawRoundedRect(QRectF(0.0, 0.0, largura, altura), RADIUS_XS, RADIUS_XS)
