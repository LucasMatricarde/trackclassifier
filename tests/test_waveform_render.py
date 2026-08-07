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


def _bandas(low, mid, high, buckets=64):
    import numpy as np

    banda = np.zeros((buckets, 3), dtype=np.float16)
    banda[:, 0] = low
    banda[:, 1] = mid
    banda[:, 2] = high
    return banda


def test_render_bands_devolve_pixmap_do_tamanho_pedido(qapp):
    from PySide6.QtCore import QSize

    from trackclassifier.ui.widgets.waveform_render import render_bands

    pixmap = render_bands(_bandas(0.5, 0.5, 0.5), QSize(120, 18))

    assert pixmap.width() == 120
    assert pixmap.height() == 18


def test_render_bands_de_grave_sai_vermelho_dominante(qapp):
    from PySide6.QtCore import QSize

    from trackclassifier.ui.widgets.waveform_render import render_bands

    imagem = render_bands(_bandas(1.0, 0.05, 0.05), QSize(60, 20)).toImage()

    # Coluna central, na altura do meio: onde a barra com certeza foi pintada.
    cor = imagem.pixelColor(30, 10)
    assert cor.red() > cor.green()
    assert cor.red() > cor.blue()


def test_render_bands_de_agudo_sai_azul_dominante(qapp):
    from PySide6.QtCore import QSize

    from trackclassifier.ui.widgets.waveform_render import render_bands

    imagem = render_bands(_bandas(0.05, 0.05, 1.0), QSize(60, 20)).toImage()

    cor = imagem.pixelColor(30, 10)
    assert cor.blue() > cor.red()
    assert cor.blue() > cor.green()


def test_render_bands_com_array_vazio_nao_quebra(qapp):
    import numpy as np
    from PySide6.QtCore import QSize

    from trackclassifier.ui.widgets.waveform_render import render_bands

    pixmap = render_bands(np.zeros((0, 3), dtype=np.float16), QSize(50, 10))

    assert pixmap.width() == 50


def test_load_peaks_le_o_arquivo_gravado(tmp_path):
    import numpy as np

    from trackclassifier.ui.widgets.waveform_render import load_peaks

    caminho = tmp_path / "abc.npy"
    np.save(caminho, _bandas(0.3, 0.4, 0.5))

    carregado = load_peaks(str(caminho))

    assert carregado is not None
    assert carregado.shape == (64, 3)


def test_load_peaks_de_none_devolve_none(tmp_path):
    from trackclassifier.ui.widgets.waveform_render import load_peaks

    assert load_peaks(None) is None


def test_load_peaks_de_arquivo_corrompido_devolve_none(tmp_path):
    # np.load levanta ValueError num arquivo invalido -- a onda tem que cair
    # no fallback mono em vez de derrubar o paint().
    from trackclassifier.ui.widgets.waveform_render import load_peaks

    caminho = tmp_path / "ruim.npy"
    caminho.write_bytes(b"isto nao e um npy")

    assert load_peaks(str(caminho)) is None


def test_load_peaks_de_arquivo_inexistente_devolve_none(tmp_path):
    from trackclassifier.ui.widgets.waveform_render import load_peaks

    assert load_peaks(str(tmp_path / "nao_existe.npy")) is None


def test_resample_estica_curva_curta_em_vez_de_repetir_a_borda():
    """pad(mode='edge') virava bloco chapado na onda de largura inteira."""
    import numpy as np

    from trackclassifier.ui.widgets.waveform_render import _resample

    curva = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    esticada = _resample(curva, 9)

    assert len(esticada) == 9
    # O pico fica no MEIO da faixa esticada. Com o pad antigo ele ficaria
    # no segundo pixel e os seis ultimos seriam todos 0.0.
    assert esticada.argmax() == 4
    assert esticada[-1] == 0.0


def test_resample_de_um_ponto_so_nao_quebra():
    import numpy as np

    from trackclassifier.ui.widgets.waveform_render import _resample

    resultado = _resample(np.array([0.5], dtype=np.float32), 5)

    assert len(resultado) == 5
    assert all(valor == 0.5 for valor in resultado)
