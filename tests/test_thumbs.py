"""Miniatura da capa: thumb em disco, com fallback pra capa original.

paint() chama load_thumbnail() dezenas de vezes por segundo durante o
scroll -- os testes provam que a segunda chamada em diante nunca mais toca
a capa original, e que arquivo ruim (capa ou thumb) degrada pro
placeholder em vez de levantar.
"""

from pathlib import Path

from PySide6.QtGui import QColor, QImage

from trackclassifier.presentation import THUMB_SUFFIX
from trackclassifier.ui.widgets.thumbs import load_thumbnail, thumb_path

LADO = 28


def _jpeg_valido(tmp_path: Path, nome: str = "capa.jpg", tamanho: int = 40) -> Path:
    """JPEG de verdade, grande o bastante pra setScaledSize ter o que reduzir."""
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_RGB32)
    imagem.fill(QColor("#4CC2E0"))
    caminho = tmp_path / nome
    assert imagem.save(str(caminho), "JPG")
    return caminho


def _png_valido(tmp_path: Path, nome: str, cor: str = "#000000") -> Path:
    imagem = QImage(8, 8, QImage.Format.Format_RGB32)
    imagem.fill(QColor(cor))
    caminho = tmp_path / nome
    assert imagem.save(str(caminho), "PNG")
    return caminho


def test_thumb_path_nao_colide_com_capa_png(tmp_path):
    capa = tmp_path / "abc123.png"
    caminho = thumb_path(capa)
    assert caminho != capa
    assert caminho.name == "abc123.thumb.png"
    assert caminho.suffix == THUMB_SUFFIX.removeprefix(".thumb")


def test_gera_thumb_ao_lado_da_capa(qapp, tmp_path):
    capa = _jpeg_valido(tmp_path)
    assert not thumb_path(capa).exists()

    pixmap = load_thumbnail(str(capa), LADO)

    assert pixmap is not None
    assert not pixmap.isNull()
    assert pixmap.width() == LADO and pixmap.height() == LADO
    assert thumb_path(capa).is_file()


def test_segunda_chamada_nao_toca_mais_a_capa_original(qapp, tmp_path):
    capa = _jpeg_valido(tmp_path)
    primeiro = load_thumbnail(str(capa), LADO)
    assert primeiro is not None

    # Sem a capa original, so o caminho do thumb pode alimentar o pixmap --
    # se a implementacao ainda dependesse da capa, isto devolveria None.
    capa.unlink()
    segundo = load_thumbnail(str(capa), LADO)

    assert segundo is not None
    assert not segundo.isNull()


def test_capa_corrompida_nao_gera_thumb(qapp, tmp_path):
    capa = tmp_path / "quebrada.jpg"
    capa.write_bytes(b"isto nao e um jpeg")

    pixmap = load_thumbnail(str(capa), LADO)

    assert pixmap is None
    assert not thumb_path(capa).exists()


def test_thumb_corrompido_cai_na_capa_e_reescreve(qapp, tmp_path):
    capa = _jpeg_valido(tmp_path)
    caminho_thumb = thumb_path(capa)
    caminho_thumb.write_bytes(b"png truncado por interrupcao")

    pixmap = load_thumbnail(str(capa), LADO)

    assert pixmap is not None
    assert not pixmap.isNull()
    # Reescrito: o proximo load nao pode mais falhar por causa do lixo antigo.
    reescrito = QImage(str(caminho_thumb))
    assert not reescrito.isNull()


def test_devolve_pixmap_mesmo_sem_conseguir_gravar(qapp, tmp_path):
    # Pasta somente leitura: o os.replace dentro de _grava_thumb levanta
    # OSError de verdade, sem mock -- prova que load_thumbnail nao propaga.
    import os

    capa = _jpeg_valido(tmp_path)
    os.chmod(tmp_path, 0o500)
    try:
        pixmap = load_thumbnail(str(capa), LADO)
    finally:
        os.chmod(tmp_path, 0o700)  # senao o pytest nao consegue limpar tmp_path

    assert pixmap is not None
    assert not pixmap.isNull()
    assert not thumb_path(capa).exists()


def test_capa_ausente_devolve_none(qapp, tmp_path):
    assert load_thumbnail(str(tmp_path / "nao-existe.jpg"), LADO) is None


def test_lado_zero_ou_negativo_devolve_none_sem_tocar_disco(qapp, tmp_path):
    capa = _jpeg_valido(tmp_path)
    assert load_thumbnail(str(capa), 0) is None
    assert load_thumbnail(str(capa), -5) is None
    assert not thumb_path(capa).exists()
