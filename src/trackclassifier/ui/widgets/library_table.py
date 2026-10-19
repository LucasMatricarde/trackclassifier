"""QTableView da Biblioteca. O anel de foco de teclado mora aqui.

Por que aqui e nao num delegate: tres das oito colunas (GENERO, BPM,
DURACAO) nao tem delegate proprio -- usam o padrao do Qt. Pintar o anel por
celula obrigaria a dar delegate as tres, espalhar a pintura pelas cinco
subclasses de _DelegateComFundo e ainda emendar cinco retangulos num so sem
costura visivel. No paintEvent da view e um retangulo unico, num lugar so.

O anel usa accent.base, que na v0.2 e a MESMA cor de surface.selection-bar.
Isso e aproveitado, nao contornado: com foco, a barra de 2px que o
CoverDelegate ja pinta na borda esquerda vira o lado esquerdo do anel e o
retangulo fecha continuo; sem foco, sobra a barra sozinha.

O clique da coluna de acoes tambem mora aqui: a QTableView nao emite sinal por
coluna (clicked chega igual para qualquer celula), e a coluna de acoes quer um
menu, nao uma selecao. A view so AVISA que pediram o menu -- quem monta e a
aba, que tem os sinais de decisao e de remocao. A coluna vem do enum, e nao de
um setter: um setter esquecido deixaria a coluna morta em silencio.
"""

from PySide6.QtCore import QModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QFocusEvent, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QTableView, QWidget

from ..colors import para_qcolor
from ..tokens import COLOR_ACCENT_BASE, SIZE_FOCUS_RING
from .track_model import Column


class LibraryTable(QTableView):
    #: Pediram o menu da coluna de acoes. Carrega o indice (e nao a sha1)
    #: porque quem resolve a linha e a aba, dona do modelo.
    acoes_pedidas = Signal(QModelIndex)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._com_foco = False

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (assinatura do Qt)
        # So o botao esquerdo: o direito ja tem o menu de contexto do Qt, e
        # abrir dois menus no mesmo clique seria pior que nao ter nenhum.
        if event.button() is Qt.MouseButton.LeftButton:
            index = self.indexAt(event.position().toPoint())
            if index.isValid() and index.column() == int(Column.ACOES):
                # Sem super(): nao ha selecao a fazer numa celula que e um
                # botao, e mudar a linha acesa aqui apagaria a selecao que o
                # usuario tinha (o menu age na linha CLICADA, nao na acesa).
                self.acoes_pedidas.emit(index)
                return
        super().mousePressEvent(event)

    def tem_foco_de_teclado(self) -> bool:
        return self._com_foco

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802 (assinatura do Qt)
        super().focusInEvent(event)
        self._muda_foco(True)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802 (assinatura do Qt)
        super().focusOutEvent(event)
        self._muda_foco(False)

    def _muda_foco(self, tem_foco: bool) -> None:
        self._com_foco = tem_foco
        # O QTableView nao repinta o viewport quando o foco entra ou sai --
        # sem este update o anel so apareceria (ou sumiria) na proxima
        # rolagem, que e pior que nao ter anel nenhum.
        self.viewport().update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (assinatura do Qt)
        super().paintEvent(event)
        if not self._com_foco:
            return
        index = self.currentIndex()
        if not index.isValid():
            return
        linha = self.visualRect(index)
        if linha.isEmpty():
            return

        # Largura do viewport, e nao da celula: o anel e da LINHA. visualRect
        # devolve so a celula da coluna atual.
        alvo = QRect(0, linha.top(), self.viewport().width(), linha.height())
        cor = para_qcolor(COLOR_ACCENT_BASE)
        painter = QPainter(self.viewport())
        # Quatro retangulos cheios em vez de um contorno com QPen: a caneta
        # centra o traco na borda e metade dos 2px sairia da linha, invadindo
        # a linha vizinha.
        painter.fillRect(QRect(alvo.left(), alvo.top(), alvo.width(), SIZE_FOCUS_RING), cor)
        painter.fillRect(
            QRect(
                alvo.left(),
                alvo.bottom() - SIZE_FOCUS_RING + 1,
                alvo.width(),
                SIZE_FOCUS_RING,
            ),
            cor,
        )
        painter.fillRect(QRect(alvo.left(), alvo.top(), SIZE_FOCUS_RING, alvo.height()), cor)
        painter.fillRect(
            QRect(
                alvo.right() - SIZE_FOCUS_RING + 1,
                alvo.top(),
                SIZE_FOCUS_RING,
                alvo.height(),
            ),
            cor,
        )
