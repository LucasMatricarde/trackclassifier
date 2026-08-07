"""O Meter existe por causa de um bug que os testes de estado nao pegam.

A versao anterior posicionava um filho por setGeometry sobre a largura do
trilho. Quem chamasse set_counts() antes do primeiro layout calculava a
fracao sobre o tamanho default e todas as barras saiam em 100% -- os
testes passavam, porque liam a fracao guardada e nao o que foi pintado.
Estes testes olham o pixel.
"""

from PySide6.QtGui import QColor

from trackclassifier.ui.colors import para_qcolor
from trackclassifier.ui.tokens import (
    COLOR_BORDER_SUBTLE,
    COLOR_CLASSIFICATION_LENTO_BASE,
)
from trackclassifier.ui.widgets.meter import Meter

ALTURA = 6


def _pintado(barra: Meter) -> "QColor":
    imagem = barra.grab().toImage()
    return imagem.pixelColor(0, ALTURA // 2)


def test_para_qcolor_le_hex():
    assert para_qcolor(COLOR_CLASSIFICATION_LENTO_BASE) == QColor(
        COLOR_CLASSIFICATION_LENTO_BASE
    )


def test_para_qcolor_le_rgba():
    cor = para_qcolor("rgba(255,255,255,0.05)")

    assert (cor.red(), cor.green(), cor.blue()) == (255, 255, 255)
    assert cor.alpha() == 13  # round(0.05 * 255)


def test_para_qcolor_aceita_os_tokens_de_borda():
    # Metade dos tokens de superficie e borda da v0.2 e rgba; se um deles
    # nao parseia, o widget pinta preto e ninguem ve o erro.
    assert para_qcolor(COLOR_BORDER_SUBTLE).isValid()


def test_fracao_e_clampada(qapp):
    barra = Meter(COLOR_CLASSIFICATION_LENTO_BASE, ALTURA)

    barra.set_fraction(1.6)
    assert barra.fraction() == 1.0

    barra.set_fraction(-0.2)
    assert barra.fraction() == 0.0


def test_fracao_definida_antes_do_resize_sobrevive(qapp):
    barra = Meter(COLOR_CLASSIFICATION_LENTO_BASE, ALTURA)
    # A ordem que quebrava a versao anterior: valor primeiro, largura
    # depois. E a ordem real -- set_state() roda antes do layout.
    barra.set_fraction(0.5)
    barra.resize(100, ALTURA)

    imagem = barra.grab().toImage()

    assert imagem.pixelColor(10, ALTURA // 2).red() > 0
    # Depois da metade so ha trilho: se a barra tivesse sido calculada
    # sobre a largura antiga, o preenchimento cobriria os 100px.
    assert imagem.pixelColor(90, ALTURA // 2) != imagem.pixelColor(10, ALTURA // 2)


def test_fracao_zero_deixa_so_o_trilho(qapp):
    barra = Meter(COLOR_CLASSIFICATION_LENTO_BASE, ALTURA)
    barra.resize(100, ALTURA)
    barra.set_fraction(0.0)

    cheia = Meter(COLOR_CLASSIFICATION_LENTO_BASE, ALTURA)
    cheia.resize(100, ALTURA)
    cheia.set_fraction(1.0)

    assert _pintado(barra) != _pintado(cheia)
