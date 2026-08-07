"""O trilho de volume: 2px de traco, faixa de clique mais alta que ele."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from trackclassifier.ui.widgets.volume_rail import VolumeRail


def test_nasce_no_valor_pedido(qapp):
    trilho = VolumeRail(80)

    assert trilho.valor() == 80


def test_set_valor_clampa_fora_da_faixa(qapp):
    trilho = VolumeRail(80)

    trilho.set_valor(140)
    assert trilho.valor() == 100

    trilho.set_valor(-5)
    assert trilho.valor() == 0


def test_clique_no_meio_do_trilho_vai_para_metade(qapp):
    trilho = VolumeRail(0)
    recebidos = []
    trilho.valor_mudou.connect(recebidos.append)

    meio = QPoint(trilho.width() // 2, trilho.height() // 2)
    QTest.mouseClick(trilho, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, meio)

    assert 45 <= trilho.valor() <= 55
    assert recebidos and 45 <= recebidos[-1] <= 55


def test_a_faixa_de_clique_e_mais_alta_que_o_traco(qapp):
    """Um trilho desenhado com 2px e intocavel com o mouse -- e por isso
    que este widget existe em vez de um QSlider vestido por QSS."""
    trilho = VolumeRail(0)

    assert trilho.height() >= 10


def test_o_valor_aparece_para_um_leitor_de_tela(qapp):
    """O valor so existe como largura de pixel: sem descricao acessivel,
    um leitor de tela anuncia "Volume" e nada mais."""
    trilho = VolumeRail(30)

    assert trilho.accessibleName() == "Volume"
    assert "30" in trilho.accessibleDescription()
