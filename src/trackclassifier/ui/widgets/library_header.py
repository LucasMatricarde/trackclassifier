"""Cabecalho da tabela da Biblioteca, pintado a mao.

Tres coisas do mockup 06 que o Qt Style Sheets nao alcanca:

- **A coluna ativa acende.** Nao ha seletor de "secao ordenada" no QSS.
  `setHighlightSections(True)` acende a secao CLICADA, que nao e a mesma
  coisa: depois de um reset de modelo a ordenacao continua e o destaque
  some.
- **O hover.** `QHeaderView::section:hover` existe, mas so alcanca a secao
  inteira -- e aqui o hover muda a cor do TEXTO, que ja e pintado aqui.
  Deixar metade no QSS e metade no paint deixaria as duas cores mudando em
  arquivos diferentes.
- **A posicao da seta.** O estilo nativo desenha o indicador na borda
  direita da secao. Na coluna Titulo, que e `Stretch`, isso a joga a ~80px
  do rotulo -- o mockup a quer a 6px dele.

Mesmo movimento de `library_table.py`: o que o QSS nao alcanca vira
`paintEvent`/`paintSection` num lugar so, com token, e nao cinco delegates
emendando retangulos.
"""

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QMouseEvent, QPainter, QPolygon
from PySide6.QtWidgets import QHeaderView, QWidget

from ..colors import para_qcolor
from ..tokens import (
    COLOR_BORDER_DEFAULT,
    COLOR_SURFACE_0,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    SPACE_3,
    SPACE_4,
)

#: Colunas sem ordem natural. Espelha o early-return de
#: `TrackTableModel.sort` -- se as duas listas divergirem, o cabecalho
#: promete uma ordenacao que o modelo nao faz. Por indice, e nao por
#: `Column`, para este modulo nao importar track_model (que importa
#: delegates, que ja e um ciclo apertado).
SEM_ORDEM = (0, 2)  # Column.CAPA, Column.WAVEFORM

#: Lado do triangulo da seta, em px. Nao vem da escala de espaco: e a
#: dimensao de um glifo desenhado, do mesmo tipo que SIZE_WAVE_BAR.
_LADO_SETA = 7


class LibraryHeader(QHeaderView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._hover = -1
        # Sem isto o Qt so entrega mouseMoveEvent com botao apertado, e o
        # hover do cabecalho so apareceria durante um arrasto.
        self.setMouseTracking(True)
        self.setSectionsClickable(True)
        # O destaque nativo da secao clicada seria uma SEGUNDA nocao de
        # "coluna ativa", concorrendo com a do indicador de ordenacao.
        self.setHighlightSections(False)

    def setSortIndicator(  # noqa: N802 (assinatura do Qt)
        self, logical_index: int, order: Qt.SortOrder
    ) -> None:
        # `TrackTableModel.sort` retorna cedo para SEM_ORDEM: ordenar por
        # elas nao muda a lista. Se o cabecalho aceitasse o indicador
        # mesmo assim, um clique em Onda apagaria o destaque da coluna que
        # de fato ordena a tabela, prometendo visualmente uma ordenacao
        # que nunca acontece.
        if logical_index in SEM_ORDEM:
            return
        super().setSortIndicator(logical_index, order)

    # ---- hover ----------------------------------------------------------

    def secao_sob_o_mouse(self) -> int:
        return self._hover

    def marca_hover(self, secao: int) -> None:
        """Publico para o teste nao precisar sintetizar QMouseEvent com
        coordenada, que depende da largura real das colunas."""
        if secao == self._hover:
            return
        anterior, self._hover = self._hover, secao
        for alvo in (anterior, secao):
            if alvo >= 0:
                self.updateSection(alvo)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (assinatura do Qt)
        super().mouseMoveEvent(event)
        self.marca_hover(self.logicalIndexAt(event.position().toPoint()))

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802 (assinatura do Qt)
        super().leaveEvent(event)
        self.marca_hover(-1)

    # ---- pintura --------------------------------------------------------

    def _cor_do_texto(self, logical: int):
        if logical == self.sortIndicatorSection() and logical not in SEM_ORDEM:
            return para_qcolor(COLOR_TEXT_PRIMARY)
        if logical == self._hover and logical not in SEM_ORDEM:
            return para_qcolor(COLOR_TEXT_SECONDARY)
        return para_qcolor(COLOR_TEXT_MUTED)

    def paintSection(  # noqa: N802 (assinatura do Qt)
        self, painter: QPainter, rect: QRect, logical: int
    ) -> None:
        # Nao chama super(): o desenho nativo traria o texto na cor da
        # paleta e a seta na borda direita, e os dois teriam que ser
        # cobertos depois. Pintar do zero e menos codigo e nao depende da
        # ordem em que o estilo desenha.
        painter.save()
        painter.fillRect(rect, para_qcolor(COLOR_SURFACE_0))
        painter.fillRect(
            QRect(rect.left(), rect.bottom(), rect.width(), 1),
            para_qcolor(COLOR_BORDER_DEFAULT),
        )

        texto = str(
            self.model().headerData(
                logical, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            )
            or ""
        )
        cor = self._cor_do_texto(logical)
        # A fonte vem do widget: familia, tamanho e tracking ja foram
        # aplicados por ui/typography.aplica_tracking na aba.
        painter.setFont(self.font())
        painter.setPen(cor)

        alinhamento = ALINHAMENTO.get(logical, Qt.AlignmentFlag.AlignLeft)
        interno = rect.adjusted(SPACE_4, 0, -SPACE_4, 0)
        metricas = painter.fontMetrics()
        largura = metricas.horizontalAdvance(texto)

        if alinhamento & Qt.AlignmentFlag.AlignRight:
            x_texto = interno.right() - largura
        elif alinhamento & Qt.AlignmentFlag.AlignHCenter:
            x_texto = interno.center().x() - largura // 2
        else:
            x_texto = interno.left()

        painter.drawText(
            QRect(x_texto, interno.top(), largura, interno.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            texto,
        )

        if logical == self.sortIndicatorSection() and logical not in SEM_ORDEM:
            self._desenha_seta(painter, x_texto + largura + SPACE_3, interno, cor)
        painter.restore()

    def _desenha_seta(self, painter: QPainter, x: int, interno: QRect, cor) -> None:
        """Triangulo cheio a SPACE_3 do fim do rotulo.

        Apontando para BAIXO em ordem crescente: a leitura e "a lista corre
        deste valor para baixo a partir do topo", que e a mesma convencao do
        mockup (a seta descendente e a mesma girada 180 graus).
        """
        meio = interno.center().y()
        topo = meio - _LADO_SETA // 3
        base = meio + _LADO_SETA // 3
        if self.sortIndicatorOrder() is Qt.SortOrder.AscendingOrder:
            pontos = [
                QPoint(x, base),
                QPoint(x + _LADO_SETA, base),
                QPoint(x + _LADO_SETA // 2, topo),
            ]
        else:
            pontos = [
                QPoint(x, topo),
                QPoint(x + _LADO_SETA, topo),
                QPoint(x + _LADO_SETA // 2, base),
            ]
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(cor)
        painter.drawPolygon(QPolygon(pontos))
        painter.restore()


#: Alinhamento do rotulo por coluna, espelhando o TextAlignmentRole do
#: TrackTableModel: cabecalho desalinhado do dado obriga o olho a procurar
#: a qual numero cada rotulo pertence. Por indice pelo mesmo motivo de
#: SEM_ORDEM.
ALINHAMENTO = {
    4: Qt.AlignmentFlag.AlignRight,  # Column.BPM
    5: Qt.AlignmentFlag.AlignHCenter,  # Column.KEY
    6: Qt.AlignmentFlag.AlignHCenter,  # Column.CLASSIFICACAO
    7: Qt.AlignmentFlag.AlignRight,  # Column.DURACAO
}
