"""Miniatura da capa para a tabela. Cache de tela, nao dado de dominio.

Mora em `ui/` e nao em `presentation.py` por uma razao dura: `dj scan` e
`dj train` rodam headless e NAO importam Qt (ver CLAUDE.md), e reduzir um
jpeg precisa de um decodificador de imagem. Entao a miniatura e produzida
pela tela, na primeira vez que a linha e pintada, e fica em disco para todas
as aberturas seguintes.

Medido na biblioteca real (349 capas embutidas, 720x720 a 1280x720), para a
miniatura de 34px que a linha da tabela mostra:

    QPixmap(capa) + scaled     4,25 ms   <- decodificava a capa INTEIRA
    QImageReader escalado      2,07 ms   <- primeiro paint, thumb ainda ausente
    thumb de 96px em disco     0,22 ms   <- todo paint seguinte

Com 15 linhas visiveis, `_miniatura` era 72% do tempo de paint da aba
Biblioteca: o primeiro paint custava 482 ms e cada parada de scroll, 21,6 ms.

Os dois caminhos existem porque cobrem momentos diferentes: `setScaledSize`
faz o libjpeg decodificar direto na escala pedida (nao ha como evitar tocar
o arquivo original na primeira vez), e o thumb em disco e o que impede que
esse custo volte na proxima abertura do app.
"""

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImageReader, QPixmap

from ...presentation import THUMB_SUFFIX

#: Lado do thumb gravado em disco. Maior que a linha da tabela (34px) de
#: proposito: a mesma miniatura serve as densidades de tela e a uma eventual
#: linha mais alta sem voltar a capa original. A 96px um PNG sai com ~14 KB,
#: entao uma biblioteca de 350 tracks custa ~5 MB.
THUMB_SIZE = 96


def thumb_path(cover_path: str | Path) -> Path:
    """Caminho do thumb ao lado da capa. Nao garante que ele exista."""
    caminho = Path(cover_path)
    return caminho.with_name(f"{caminho.stem}{THUMB_SUFFIX}")


def load_thumbnail(cover_path: str | Path, side: int) -> QPixmap | None:
    """Miniatura quadrada de `side` px, ou None se a capa nao abre.

    Chamado de dentro de paint(): nao pode levantar. Capa corrompida, formato
    que o Qt nao conhece ou arquivo que sumiu entre o viewmodel montar a linha
    e o paint acontecer viram None, e o delegate desenha o placeholder.
    """
    if side <= 0:
        return None

    thumb = thumb_path(cover_path)
    origem = _decodifica(thumb, side) if thumb.is_file() else None
    if origem is None:
        # Sem thumb, com thumb truncado por interrupcao, ou com thumb que o Qt
        # nao abre: volta para a capa original e reescreve. Um thumb ruim nao
        # pode condenar a linha ao placeholder para sempre.
        origem = _decodifica(Path(cover_path), THUMB_SIZE)
        if origem is None:
            return None
        _grava_thumb(origem, thumb)

    return _quadra(origem, side)


def _decodifica(caminho: Path, lado: int) -> QPixmap | None:
    """Decodifica ja na escala pedida, em vez de decodificar cheio e escalar.

    `setScaledSize` nao e um `scaled()` disfarcado: o plugin de jpeg do Qt
    repassa a escala ao libjpeg, que decodifica menos coeficientes DCT. E de
    onde vem a metade do tempo, nao do `scaled` -- medido, `scaled` sozinho
    era 0,04 s dos 1,27 s que `_miniatura` gastava.
    """
    leitor = QImageReader(str(caminho))
    # Capa embutida em tag as vezes carrega orientacao EXIF; sem isto a
    # miniatura sai deitada enquanto a capa grande (QPixmap direto, na aba
    # Revisao) sai em pe.
    leitor.setAutoTransform(True)

    tamanho = leitor.size()
    if tamanho.isValid() and tamanho.width() > 0 and tamanho.height() > 0:
        # max(), nao min(): e o que corresponde a KeepAspectRatioByExpanding
        # usado em _quadra. Com min() a imagem chegaria menor que o lado pedido
        # num dos eixos e o _quadra teria que AMPLIAR de volta.
        escala = max(lado / tamanho.width(), lado / tamanho.height())
        if escala < 1.0:
            leitor.setScaledSize(
                QSize(
                    max(1, round(tamanho.width() * escala)),
                    max(1, round(tamanho.height() * escala)),
                )
            )

    imagem = leitor.read()
    if imagem.isNull():
        return None
    return QPixmap.fromImage(imagem)


def _quadra(pixmap: QPixmap, lado: int) -> QPixmap:
    return pixmap.scaled(
        lado,
        lado,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )


def _grava_thumb(pixmap: QPixmap, destino: Path) -> None:
    """Escrita atomica, e silenciosa quando falha.

    Atomica pelo mesmo motivo das capas e do parquet: o paint le estes
    arquivos a qualquer momento, e um PNG pela metade vira pixmap nulo sem
    erro nenhum -- que aqui significaria a linha cair no placeholder.

    Silenciosa porque o thumb e so um cache: disco cheio, pasta somente
    leitura ou o diretorio removido por fora custam desempenho, nao correcao.
    A miniatura ja esta em memoria e a linha e pintada do mesmo jeito.
    """
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        if not pixmap.save(str(tmp), "PNG"):
            tmp.unlink(missing_ok=True)
            return
        os.replace(tmp, destino)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
