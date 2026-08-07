"""Render da onda. Um so lugar, usado pela onda grande e pela mini.

Dois modos coexistem de proposito: `render_bands` desenha o RGB por banda
(graves no vermelho, medios no verde, agudos no azul) quando os buckets ja
foram computados, e `render_curve` desenha o mono derivado do energy_curve
quando ainda nao foram. O mono nao e legado -- e o fallback que mantem a
tela util enquanto o computo preguicoso nao chegou naquela track.
"""

from collections import OrderedDict

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from ..tokens import (
    COLOR_ACCENT_BASE,
    COLOR_SURFACE_WAVEFORM,
    COLOR_WAVEBAND_FLOOR,
    COLOR_WAVEBAND_HIGH_GAIN,
    COLOR_WAVEBAND_LOW_GAIN,
    COLOR_WAVEBAND_MID_GAIN,
)

_EPS = 1e-9


def _resample(curva: np.ndarray, barras: int) -> np.ndarray:
    """Reduz N pontos para `barras` pegando o maximo de cada bucket.

    Maximo e nao media de proposito: media achata transientes e a onda
    perde justamente a informacao de ataque que o DJ procura.
    """
    if barras <= 0 or len(curva) == 0:
        return np.zeros(max(0, barras), dtype=np.float32)
    if len(curva) <= barras:
        # Estica, nao repete a borda. `pad(mode="edge")` deixava a curva
        # ocupar so os primeiros len(curva) pixels e transformava todo o
        # resto num bloco chapado do ultimo valor -- invisivel na coluna de
        # 480px da Biblioteca (onde a curva quase sempre tem mais pontos
        # que barras), e gritante na onda de largura inteira da Revisao,
        # onde uma track curta virava 60% de retangulo solido.
        if len(curva) == 1:
            return np.full(barras, curva[0], dtype=np.float32)
        origem = np.linspace(0.0, 1.0, len(curva))
        destino = np.linspace(0.0, 1.0, barras)
        return np.interp(destino, origem, curva).astype(np.float32)

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


#: Os ganhos em tokens.py sao STRINGS ("1.00", "0.92"), nao floats -- o
#: build_tokens.py emite tudo do JSON como string. A conversao explicita
#: aqui e o que evita um TypeError na multiplicacao com o array numpy.
_GANHOS = np.array(
    [
        float(COLOR_WAVEBAND_LOW_GAIN),
        float(COLOR_WAVEBAND_MID_GAIN),
        float(COLOR_WAVEBAND_HIGH_GAIN),
    ],
    dtype=np.float32,
)
_PISO = float(COLOR_WAVEBAND_FLOOR)

#: Peso de cada banda na ALTURA da barra (a cor vem do RGB direto). Graves
#: pesam mais porque e o que da a silhueta reconhecivel de uma track -- uma
#: onda ponderada igualmente vira um bloco sem forma. O 1.5 compensa o fato
#: de os tres pesos somarem 1.0 e a maioria das tracks nunca saturar as tres
#: bandas ao mesmo tempo.
_PESOS_ALTURA = np.array([0.55, 0.30, 0.15], dtype=np.float32)
_GANHO_ALTURA = 1.5


def load_peaks(path: str | None) -> np.ndarray | None:
    """Le um .npy de buckets. Devolve None em qualquer problema.

    Chamado de dentro de paint(): nao pode levantar. Um .npy truncado por
    interrupcao faz a onda cair no render mono, que e o comportamento certo.
    """
    if path is None:
        return None
    try:
        return np.load(path)
    except Exception:
        # np.load levanta ValueError (nao OSError) num arquivo invalido, e
        # FileNotFoundError se o arquivo sumiu entre o viewmodel montar a
        # linha e o paint acontecer.
        return None


def _cores(bandas: np.ndarray) -> np.ndarray:
    """(barras, 3) normalizado -> (barras, 3) uint8 pronto para QColor.

    O piso existe para uma banda zerada nao virar preto absoluto: uma coluna
    so de graves ficaria vermelho puro sobre fundo escuro e sumiria nas
    bordas. Com o piso ela mantem um minimo de presenca nos outros canais.
    """
    escalado = _PISO + (1.0 - _PISO) * np.clip(bandas, 0.0, 1.0) * _GANHOS
    return (np.clip(escalado, 0.0, 1.0) * 255).astype(np.uint8)


def _resample_bandas(picos: np.ndarray, barras: int) -> np.ndarray:
    """Reduz (N, 3) para (barras, 3) pelo maximo, igual ao mono."""
    if barras <= 0 or len(picos) == 0:
        return np.zeros((max(0, barras), 3), dtype=np.float32)
    if len(picos) <= barras:
        return np.pad(
            picos.astype(np.float32), ((0, barras - len(picos)), (0, 0)), mode="edge"
        )

    bordas = np.linspace(0, len(picos), barras + 1, dtype=int)
    return np.stack(
        [picos[bordas[i] : bordas[i + 1]].max(axis=0) for i in range(barras)]
    ).astype(np.float32)


def render_bands(
    peaks: np.ndarray,
    size: QSize,
    bar_width: int = 2,
    gap: int = 0,
    background: QColor | None = None,
) -> QPixmap:
    """Desenha a onda RGB: a cor de cada coluna E a energia das tres bandas.

    Nao e um gradiente aplicado sobre uma envoltoria -- graves viram vermelho,
    medios verde, agudos azul, e a mistura resultante e a cor da coluna.

    Chame uma vez por track e guarde o resultado, igual ao render_curve:
    redesenhar dentro de paint() com dezenas de linhas visiveis derruba o
    scroll.
    """
    largura = max(1, size.width())
    altura = max(1, size.height())

    imagem = QImage(largura, altura, QImage.Format.Format_ARGB32_Premultiplied)
    imagem.fill(background if background is not None else QColor(COLOR_SURFACE_WAVEFORM))

    picos = np.asarray(peaks, dtype=np.float32)
    if picos.size:
        passo = max(1, bar_width + gap)
        barras = max(1, largura // passo)
        bandas = _resample_bandas(picos, barras)
        cores = _cores(bandas)
        amplitude = np.clip(bandas @ _PESOS_ALTURA * _GANHO_ALTURA, 0.0, 1.0)

        pintor = QPainter(imagem)
        pintor.setPen(Qt.PenStyle.NoPen)
        for i in range(barras):
            altura_barra = max(1.0, float(amplitude[i]) * altura)
            y = (altura - altura_barra) / 2.0
            r, g, b = cores[i]
            pintor.fillRect(
                int(i * passo),
                int(y),
                bar_width,
                int(round(altura_barra)),
                QColor(int(r), int(g), int(b)),
            )
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
