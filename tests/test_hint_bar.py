"""HintBar: legenda de atalhos, chrome comum a Revisao e Biblioteca."""

from trackclassifier.ui.widgets.hint_bar import HintBar


def test_faixa_vazia_fica_escondida(qapp):
    """Modelo e Configuracao nao tem atalho nenhum -- a faixa some, em vez
    de ficar 31px de altura sem nada dentro (leria como rodape quebrado)."""
    faixa = HintBar()

    faixa.set_atalhos(())

    assert faixa.isVisible() is False


def test_atalhos_aparecem_na_ordem_e_com_o_texto_certo(qapp):
    faixa = HintBar()

    faixa.set_atalhos((("espaco tocar", False), ("← → navegar", False)))

    # estiliza_label aplica caixa alta -- o texto exibido nao e o que foi
    # passado, e a versao em caixa alta dele (font.case.label).
    assert [rotulo.text() for rotulo in faixa._rotulos] == [
        "ESPACO TOCAR",
        "← → NAVEGAR",
    ]
    assert faixa.isVisible() is True


def test_item_destacado_ganha_a_propriedade_de_tom(qapp):
    """So a acao PRINCIPAL da aba sobe de muted para secondary -- ver o
    QSS gerado (QLabel#MicroLabel[tone="secondary"])."""
    faixa = HintBar()

    faixa.set_atalhos((("1 / 2 / 3 reclassificar", True), ("Z desfazer", False)))

    destacado, normal = faixa._rotulos
    assert destacado.property("tone") == "secondary"
    assert normal.property("tone") is None


def test_trocar_atalhos_substitui_os_rotulos_antigos(qapp):
    """Sem limpar os widgets antigos, trocar de aba duas vezes acumularia
    legendas por cima umas das outras."""
    faixa = HintBar()

    faixa.set_atalhos((("espaco tocar", False),))
    faixa.set_atalhos((("↑↓ navegar", False), ("Z desfazer", False)))

    assert [rotulo.text() for rotulo in faixa._rotulos] == ["↑↓ NAVEGAR", "Z DESFAZER"]
