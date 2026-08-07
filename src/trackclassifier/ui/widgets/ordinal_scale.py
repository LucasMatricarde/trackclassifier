"""A escala ordinal de tres segmentos, compartilhada entre tabela e tela.

Nasceu dentro do ClassificationDelegate. A Revisao precisa da MESMA escala
num tamanho maior (5x20 em vez de 9x9), e um segundo desenho equivalente e
como as duas divergem: bastaria alguem trocar o contorno por preenchimento
num dos lados para a mesma informacao ler diferente em duas telas.

A funcao serve ao delegate (que ja tem um QPainter na mao) e o widget
serve ao layout. O desenho e um so.
"""

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from ..colors import para_qcolor
from ..tokens import COLOR_BORDER_DEFAULT, classification_base
from ..viewmodel import LABELS_EM_ORDEM

#: Rotulo do dominio -> nome da classe no design system. Mesma tabela de
#: delegates.py: tokens.py e gerado e nao pode conhecer o dominio.
_CLASSE = {"+1": "animada", "neutra": "neutro", "-1": "lento"}

#: Tamanhos das duas ocorrencias, do LEIA-ME. Na linha da tabela o segmento
#: e quadrado (9x9); na faixa de palpite da Revisao e uma barra vertical
#: (5x20), porque ali ha altura de sobra e a escala e o elemento principal.
LADO_LINHA = 9
LARGURA_PALPITE = 5
ALTURA_PALPITE = 20
GAP = 3


def indice_do_rotulo(rotulo: str | None) -> int | None:
    """Posicao na escala, ou None quando nao ha classe."""
    if rotulo in LABELS_EM_ORDEM:
        return LABELS_EM_ORDEM.index(rotulo)
    return None


def desenha_escala(
    painter: QPainter,
    centro: QPoint,
    aceso: int | None,
    *,
    largura: int = LADO_LINHA,
    altura: int = LADO_LINHA,
    gap: int = GAP,
) -> None:
    """Tres segmentos centrados em `centro`, com `aceso` preenchido.

    Segmento apagado sai so em contorno: com fundo ele leria como um
    quarto estado ("meio aceso") em vez de "esta classe nao".
    """
    total = largura * 3 + gap * 2
    origem = centro.x() - total // 2
    topo = centro.y() - altura // 2

    painter.save()
    for posicao in range(3):
        quadro = QRect(origem + posicao * (largura + gap), topo, largura, altura)
        if posicao == aceso:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(classification_base(_CLASSE[LABELS_EM_ORDEM[posicao]])))
            painter.drawRect(quadro)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(para_qcolor(COLOR_BORDER_DEFAULT))
            painter.drawRect(quadro.adjusted(0, 0, -1, -1))
    painter.restore()


class OrdinalScale(QWidget):
    """Versao widget, para entrar num layout em vez de num paint de celula."""

    def __init__(
        self,
        largura: int = LARGURA_PALPITE,
        altura: int = ALTURA_PALPITE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._largura = largura
        self._altura = altura
        self._aceso: int | None = None
        self.setFixedSize(largura * 3 + GAP * 2, altura)

    def set_label(self, rotulo: str | None) -> None:
        self._aceso = indice_do_rotulo(rotulo)
        # Tres retangulos pintados nao tem texto nenhum: sem isto a escala
        # e invisivel para um leitor de tela, e ela e o unico lugar da
        # faixa de palpite que carrega a classe.
        self.setAccessibleName("Escala de classificacao")
        self.setAccessibleDescription(rotulo or "sem classificacao")
        self.update()

    def aceso(self) -> int | None:
        return self._aceso

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (assinatura do Qt)
        painter = QPainter(self)
        desenha_escala(
            painter,
            QPoint(self.width() // 2, self.height() // 2),
            self._aceso,
            largura=self._largura,
            altura=self._altura,
        )
