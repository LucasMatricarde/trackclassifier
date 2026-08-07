"""Trilho de volume: traco de 2px com marcador, clicavel e arrastavel.

Nao herda de Meter, apesar de os dois serem trilhos pintados a mao. Meter e
read-only, preenche a altura inteira e se anuncia como "Medidor"; aqui os
tres pontos mudam, e sobreviveria so o nome da classe.

O que obriga o widget a existir e a diferenca entre a altura DESENHADA e a
altura CLICAVEL: o mockup pede um traco de 2px, e 2px sao intocaveis com o
mouse. O widget tem altura de _ALTURA, pinta o traco centrado nela e aceita
o clique em qualquer ponto da faixa -- um QSlider vestido por QSS nao
consegue separar as duas alturas.
"""

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from ..colors import para_qcolor
from ..tokens import COLOR_BORDER_DEFAULT, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY

#: Do mockup. Nao esticam com a janela: um medidor de volume de 400px nao
#: le melhor que um de 100, so ocupa mais.
_LARGURA = 100
_ALTURA = 12
_ALTURA_TRILHO = 2
_LARGURA_MARCADOR = 2
_ALTURA_MARCADOR = 10


class VolumeRail(QWidget):
    valor_mudou = Signal(int)

    def __init__(self, valor: int = 80, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._valor = 0
        self.setFixedSize(_LARGURA, _ALTURA)
        # NoFocus de proposito: 1/2/3 sao QShortcut de janela e rodam ANTES
        # da entrega normal do evento, entao nem com foco este widget os
        # receberia -- focavel aqui so acrescentaria uma parada no Tab.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName("Volume")
        self.set_valor(valor)

    def valor(self) -> int:
        return self._valor

    def set_valor(self, valor: int) -> None:
        # Clampa aqui e nao em quem chama: o valor vem de uma coordenada de
        # mouse, que passa das bordas em qualquer arrasto um pouco largo.
        self._valor = min(100, max(0, int(valor)))
        # O valor so existe como largura de pixel.
        self.setAccessibleDescription(f"{self._valor}%")
        self.update()
        self.valor_mudou.emit(self._valor)

    # ---- mouse ---------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (assinatura do Qt)
        # So o botao esquerdo muda o volume -- direito e do meio abrem menu
        # de contexto ou fazem outra coisa em widgets nativos, e nao deviam
        # arrastar o volume junto por acidente.
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._valor_do_x(event.position().x())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (assinatura do Qt)
        # Mesmo raciocinio do press: so reage ao arrasto se o botao esquerdo
        # estiver entre os pressionados neste evento.
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        self._valor_do_x(event.position().x())

    def _valor_do_x(self, x: float) -> None:
        # width() - 1 no denominador (nao width()): x vai de 0 ate width()-1
        # em pixel, entao dividir por width() deixa 100 inalcancavel por
        # clique (99 no maximo). max(1, ...) evita divisao por zero num
        # widget de largura 0 ou 1.
        self.set_valor(round(x / max(1, self.width() - 1) * 100))

    # ---- pintura -------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (assinatura do Qt)
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)

        topo = (self.height() - _ALTURA_TRILHO) // 2
        painter.setBrush(para_qcolor(COLOR_BORDER_DEFAULT))
        painter.drawRect(QRect(0, topo, self.width(), _ALTURA_TRILHO))

        preenchido = round(self.width() * self._valor / 100)
        painter.setBrush(para_qcolor(COLOR_TEXT_SECONDARY))
        painter.drawRect(QRect(0, topo, preenchido, _ALTURA_TRILHO))

        # Marcador preso na borda direita no volume maximo: centrado no
        # preenchimento, metade dele sairia do widget e sumiria.
        x = min(preenchido, self.width() - _LARGURA_MARCADOR)
        painter.setBrush(para_qcolor(COLOR_TEXT_PRIMARY))
        painter.drawRect(
            QRect(
                x,
                (self.height() - _ALTURA_MARCADOR) // 2,
                _LARGURA_MARCADOR,
                _ALTURA_MARCADOR,
            )
        )
