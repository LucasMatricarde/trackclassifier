"""O "…" da coluna de acoes da Biblioteca.

Separado dos outros delegates porque nao tem estado: o modelo ja entrega fonte
e cor (FontRole/ForegroundRole, via _ESTILO_POR_COLUNA), e aqui so se desenha
o glifo. Quem CLICA e a LibraryTable -- a QTableView nao emite sinal util por
coluna -- e o menu mora na aba, que tem os sinais de decisao e de remocao.
"""

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import QStyleOptionViewItem

from .delegates import _DelegateComFundo

#: O glifo do menu. Tres pontos deitados, e nao o vertical do inspector: a
#: celula e baixa e larga (36x42), e a versao deitada le melhor nessa caixa.
GLIFO = "…"


class ActionsDelegate(_DelegateComFundo):
    """Desenha o GLIFO no centro da celula.

    Sem sizeHint proprio: a largura e fixa (Column.ACOES.width) e a altura vem
    da linha -- pedir um sizeHint aqui so criaria uma segunda fonte de verdade
    para a largura da coluna.
    """

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        self._pinta_fundo(painter, option, index)

        opcao = QStyleOptionViewItem(option)
        self.initStyleOption(opcao, index)
        painter.save()
        # Fonte e cor saem do modelo, e nao de constante local: o "…" tem que
        # acompanhar o tom apagado da coluna `#` ao lado sem uma segunda copia
        # do token aqui.
        painter.setFont(opcao.font)
        painter.setPen(opcao.palette.brush(QPalette.ColorRole.Text).color())
        painter.drawText(opcao.rect, Qt.AlignmentFlag.AlignCenter, GLIFO)
        painter.restore()
