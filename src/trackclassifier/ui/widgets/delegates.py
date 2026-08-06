"""Delegates da tabela. Tudo que QSS nao alcanca e pintado aqui."""

from PySide6.QtCore import QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from ..tokens import SIZE_WAVE_BAR, classification_colors
from ..viewmodel import TrackRow
from .waveform_render import PixmapCache, render_curve

#: Role customizado: os delegates pedem a TrackRow inteira por aqui, em vez
#: de reconstruir dados a partir das strings de DisplayRole.
TRACK_ROLE = Qt.ItemDataRole.UserRole + 1

#: Rotulo do dominio (labels.Label) -> nome do chip no design system.
#: A traducao mora aqui porque tokens.py e gerado e nao pode conhecer o
#: dominio, e viewmodel.py nao pode conhecer o design system.
_CHIP = {"+1": "animada", "neutra": "neutro", "-1": "lento"}
_TEXTO = {"+1": "+1", "neutra": "neutra", "-1": "-1"}


class _DelegateComFundo(QStyledItemDelegate):
    """Base dos delegates que pintam a celula inteira a mao.

    QStyledItemDelegate.paint desenha o fundo do item (selecao, hover, linha
    alternada) antes do conteudo. Um paint() sobrescrito que nunca chama a
    base pinta so o conteudo, e o fundo some -- na tabela da Biblioteca isso
    aparece como a linha selecionada se apagando exatamente sob as colunas
    Onda e Classificacao, as duas que tem delegate. Redesenhar pelo proprio
    QStyle (e nao com uma cor fixa) e o que mantem app.qss no comando:
    selection-background-color de la continua valendo.
    """

    def _pinta_fundo(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        opcao = QStyleOptionViewItem(option)
        self.initStyleOption(opcao, index)
        # initStyleOption puxa o texto do DisplayRole. Estas colunas nao tem
        # nenhum, mas zerar deixa explicito que aqui so o fundo e desenhado.
        opcao.text = ""
        estilo = opcao.widget.style() if opcao.widget else QApplication.style()
        estilo.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, opcao, painter, opcao.widget
        )


class WaveformDelegate(_DelegateComFundo):
    """Pinta a mini onda da linha a partir da curva ja calculada.

    O pixmap e cacheado por (sha1, largura, altura). O paint() nunca
    decodifica audio nem recalcula a curva -- so faz drawPixmap.
    """

    def __init__(self, parent: QWidget | None = None, margin: int = 4) -> None:
        super().__init__(parent)
        self._cache = PixmapCache(capacity=256)
        self._margin = margin

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        # Sempre antes de qualquer `return`: uma celula sem onda para desenhar
        # continua sendo uma celula selecionavel.
        self._pinta_fundo(painter, option, index)

        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None or not linha.energy_curve:
            return

        rect = option.rect.adjusted(self._margin, self._margin, -self._margin, -self._margin)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        chave = (linha.sha1, rect.width(), rect.height())
        pixmap = self._cache.get(chave)
        if pixmap is None:
            pixmap = render_curve(
                linha.energy_curve,
                QSize(rect.width(), rect.height()),
                bar_width=SIZE_WAVE_BAR,
                gap=0,
            )
            self._cache.put(chave, pixmap)

        painter.drawPixmap(rect.topLeft(), pixmap)

    def clear_cache(self) -> None:
        self._cache.clear()


class ClassificationDelegate(_DelegateComFundo):
    """Chip do rotulo: fundo em tint escuro e texto claro da mesma matiz.

    Preenchimento saturado atras de texto de 11px reprova em contraste;
    tint mais texto claro passa AA com folga.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius = 4.0
        self._padding_h = 8
        self._padding_v = 3

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        # Idem WaveformDelegate: o fundo vem antes de qualquer desistencia.
        self._pinta_fundo(painter, option, index)

        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None:
            return
        rotulo = linha.label or linha.predicted
        if rotulo is None:
            return

        fundo, frente = classification_colors(_CHIP[rotulo])
        texto = _TEXTO[rotulo]

        metricas = QFontMetrics(option.font)
        largura = metricas.horizontalAdvance(texto) + self._padding_h * 2
        altura = metricas.height() + self._padding_v * 2

        chip = QRect(0, 0, largura, altura)
        chip.moveCenter(option.rect.center())

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(fundo))
        painter.drawRoundedRect(chip, self._radius, self._radius)
        painter.setPen(QColor(frente))
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, texto)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(96, 24)
