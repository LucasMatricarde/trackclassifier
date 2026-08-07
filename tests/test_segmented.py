"""Segmented: alternador de N posicoes visiveis lado a lado.

Substitui o antigo botao unico "Confortavel/Compacta" da Biblioteca (o
rotulo dizia para onde o clique levava); o mockup 3a mostra as duas
posicoes de uma vez, com a corrente acesa.
"""

from trackclassifier.ui.widgets.segmented import Segmented


def test_abre_no_primeiro_segmento(qapp):
    alternador = Segmented(("Confortavel", "Compacta"))

    assert alternador.selecionado() == 0


def test_clique_no_segmento_muda_a_selecao_e_emite(qapp):
    alternador = Segmented(("Confortavel", "Compacta"))
    recebidos = []
    alternador.mudou.connect(recebidos.append)

    alternador._grupo.button(1).click()

    assert alternador.selecionado() == 1
    assert recebidos == [1]


def test_clicar_no_ja_selecionado_nao_reemite(qapp):
    """idToggled dispara duas vezes por troca (o antigo desmarca, o novo
    marca) -- so o toggled(True) deve chegar em `mudou`, e clicar no que ja
    esta aceso nao deveria disparar nada (evita jogar fora o cache de
    pixmap dos delegates da Biblioteca de graca)."""
    alternador = Segmented(("Confortavel", "Compacta"))
    recebidos = []
    alternador.mudou.connect(recebidos.append)

    alternador._grupo.button(0).click()

    assert recebidos == []


def test_set_selecionado_programatico(qapp):
    alternador = Segmented(("Confortavel", "Compacta"))

    alternador.set_selecionado(1)

    assert alternador.selecionado() == 1


def test_texto_selecionado_acompanha_o_indice(qapp):
    from trackclassifier.ui.typography import texto_de_label

    alternador = Segmented(("Confortavel", "Compacta"))

    assert alternador.texto_selecionado() == texto_de_label("Confortavel")

    alternador.set_selecionado(1)

    assert alternador.texto_selecionado() == texto_de_label("Compacta")
