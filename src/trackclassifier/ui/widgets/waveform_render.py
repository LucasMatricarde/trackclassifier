"""Render da onda. Um so lugar, usado pela onda grande e pela mini.

Fase 1 desenha mono, a partir do energy_curve que TrackAnalysis ja
carrega. O render RGB por banda (graves no vermelho, medios no verde,
agudos no azul) entra na fase 3, quando existir o dado por banda.
"""

from collections import OrderedDict

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from ..tokens import COLOR_ACCENT_BASE, COLOR_SURFACE_WAVEFORM

_EPS = 1e-9


def _resample(curva: np.ndarray, barras: int) -> np.ndarray:
    """Reduz N pontos para `barras` pegando o maximo de cada bucket.

    Maximo e nao media de proposito: media achata transientes e a onda
    perde justamente a informacao de ataque que o DJ procura.
    """
    if barras <= 0 or len(curva) == 0:
        return np.zeros(max(0, barras), dtype=np.float32)
    if len(curva) <= barras:
        return np.pad(curva, (0, barras - len(curva)), mode="edge").astype(np.float32)

    bordas = np.linspace(0, len(curva), barras + 1, dtype=int)
    return np.asarray(
        [curva[bordas[i] : bordas[i + 1]].max() for i in range(barras)], dtype=np.float32
    )


def render_curve(
    curve: tuple[float, ...],
    size: QSize,
    bar_width: int = 2,
    gap: int = 0,
    background: QColor | None = None,
) -> QPixmap:
    """Desenha a curva de energia num QPixmap do tamanho pedido.

    Chame uma vez por track e guarde o resultado. Redesenhar dentro de
    paint() com dezenas de linhas visiveis derruba o scroll.
    """
    largura = max(1, size.width())
    altura = max(1, size.height())

    imagem = QImage(largura, altura, QImage.Format.Format_ARGB32_Premultiplied)
    imagem.fill(background if background is not None else QColor(COLOR_SURFACE_WAVEFORM))

    curva = np.asarray(curve, dtype=np.float32)
    if curva.size:
        passo = max(1, bar_width + gap)
        barras = max(1, largura // passo)
        amostras = _resample(curva, barras)
        # Normaliza pelo proprio maximo: a energia absoluta varia muito entre
        # masterizacoes, e sem isto uma track baixa vira uma linha reta.
        amplitude = np.clip(amostras / (float(amostras.max()) + _EPS), 0.0, 1.0)

        cor = QColor(COLOR_ACCENT_BASE)
        pintor = QPainter(imagem)
        pintor.setPen(Qt.PenStyle.NoPen)
        for i in range(barras):
            altura_barra = max(1.0, float(amplitude[i]) * altura)
            y = (altura - altura_barra) / 2.0
            pintor.fillRect(int(i * passo), int(y), bar_width, int(round(altura_barra)), cor)
        pintor.end()

    return QPixmap.fromImage(imagem)


class PixmapCache:
    """LRU de pixmaps por (sha1, largura, altura).

    A chave e o sha1, nao o caminho: decidir um rotulo MOVE o arquivo de
    pasta, e uma chave por caminho invalidaria a entrada de toda track
    classificada -- a Biblioteca repintaria tudo depois de uma sessao de
    revisao, que e exatamente o engasgo que este cache existe para evitar.
    O tamanho entra na chave porque redimensionar a coluna invalida o
    render. Capacidade baixa de proposito: so precisa cobrir o viewport
    mais a margem de scroll, nao a biblioteca inteira.
    """

    def __init__(self, capacity: int = 256) -> None:
        self._capacity = capacity
        self._items: OrderedDict[tuple[str, int, int], QPixmap] = OrderedDict()

    def get(self, key: tuple[str, int, int]) -> QPixmap | None:
        pixmap = self._items.get(key)
        if pixmap is not None:
            self._items.move_to_end(key)
        return pixmap

    def put(self, key: tuple[str, int, int], pixmap: QPixmap) -> None:
        self._items[key] = pixmap
        self._items.move_to_end(key)
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()
