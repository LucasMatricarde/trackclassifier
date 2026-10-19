"""Icones SVG tintados na cor de um token, em runtime.

Os arquivos em icons/ usam `currentColor` de proposito: o mesmo asset
serve ao estado normal (text.secondary) e ao ativo (accent.base) sem
duplicar SVG por cor. QIcon("arquivo.svg") renderiza com a cor gravada no
arquivo, entao aqui o texto do SVG e lido, o placeholder trocado pela cor
do token e o resultado rasterizado com QSvgRenderer -- que esta no
PySide6-Essentials e cujo plugin (libqsvg) o hook do PySide6 ja empacota.

Nenhum hex mora neste modulo: a cor chega como argumento, vinda de
tokens.py -- e o que mantem tests/test_tokens.py::test_nenhum_hex_fora_do_json
verde com os SVGs fora da varredura (ela so le *.py).
"""

from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

DIRETORIO = Path(__file__).parent / "icons"

#: Um QIcon por (nome, cor, tamanho): os estados de um botao pedem o mesmo
#: icone a cada polish, e rasterizar SVG nao e de graca.
_cache: dict[tuple[str, str, int], QIcon] = {}


def icon(nome: str, cor: str, tamanho: int) -> QIcon:
    """Devolve o icone `nome` (sem .svg) na cor e no tamanho pedidos.

    Um nome inexistente devolve QIcon() vazio em vez de levantar: um asset
    que faltou no bundle nao pode impedir a janela de abrir -- o botao
    fica sem desenho, mas funciona.
    """
    chave = (nome, cor, tamanho)
    if chave in _cache:
        return _cache[chave]

    caminho = DIRETORIO / f"{nome}.svg"
    resultado = QIcon()
    if caminho.exists():
        svg = caminho.read_text(encoding="utf-8").replace("currentColor", cor)
        renderizador = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        if renderizador.isValid():
            # devicePixelRatio 2: sem isto o icone fica serrilhado em tela
            # Retina, que e onde o app roda na pratica.
            pixmap = QPixmap(QSize(tamanho, tamanho) * 2)
            pixmap.setDevicePixelRatio(2)
            pixmap.fill(Qt.GlobalColor.transparent)
            pintor = QPainter(pixmap)
            renderizador.render(pintor)
            pintor.end()
            resultado = QIcon(pixmap)
    _cache[chave] = resultado
    return resultado
