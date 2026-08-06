from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap

from trackclassifier.ui.widgets.waveform_render import PixmapCache, render_curve


def test_render_devolve_pixmap_do_tamanho_pedido(qapp):
    pixmap = render_curve((0.1, 0.5, 0.9, 0.4), QSize(120, 18))

    assert isinstance(pixmap, QPixmap)
    assert pixmap.width() == 120
    assert pixmap.height() == 18


def test_render_de_curva_vazia_nao_quebra(qapp):
    pixmap = render_curve((), QSize(50, 10))

    assert pixmap.width() == 50
    assert pixmap.height() == 10


def test_render_normaliza_pelo_maximo_da_curva(qapp):
    """Duas curvas com a mesma forma e escalas diferentes desenham igual.

    A energia absoluta varia muito entre tracks masterizadas de formas
    diferentes; sem normalizar, uma track baixa viraria uma linha reta.
    """
    baixa = render_curve((0.01, 0.02, 0.01), QSize(40, 20))
    alta = render_curve((0.5, 1.0, 0.5), QSize(40, 20))

    assert baixa.toImage() == alta.toImage()


def test_cache_devolve_o_mesmo_pixmap_para_a_mesma_chave(qapp):
    cache = PixmapCache(capacity=4)
    chave = ("abc123", 100, 18)
    pixmap = render_curve((0.5, 1.0), QSize(100, 18))

    cache.put(chave, pixmap)

    assert cache.get(chave) is pixmap
    assert cache.get(("outro", 100, 18)) is None


def test_cache_descarta_o_menos_usado_ao_estourar(qapp):
    cache = PixmapCache(capacity=2)
    pixmap = render_curve((0.5,), QSize(10, 10))

    cache.put(("a", 10, 10), pixmap)
    cache.put(("b", 10, 10), pixmap)
    cache.get(("a", 10, 10))  # 'a' passa a ser o mais recente
    cache.put(("c", 10, 10), pixmap)  # estoura: sai 'b'

    assert cache.get(("a", 10, 10)) is pixmap
    assert cache.get(("b", 10, 10)) is None
    assert cache.get(("c", 10, 10)) is pixmap


def test_cache_e_chaveado_por_sha1_e_nao_por_caminho(qapp):
    """Regressao: o arquivo muda de pasta a cada decisao de rotulo.

    Se a chave fosse o caminho, classificar uma track invalidaria a entrada
    dela e a Biblioteca repintaria tudo depois de uma sessao de revisao.
    """
    cache = PixmapCache(capacity=4)
    pixmap = render_curve((0.5, 1.0), QSize(100, 18))
    cache.put(("sha1abc", 100, 18), pixmap)

    # Mesmo sha1, arquivo agora em outra pasta: segue sendo hit.
    assert cache.get(("sha1abc", 100, 18)) is pixmap
