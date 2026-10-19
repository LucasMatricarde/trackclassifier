"""ClassChips: o filtro de classe com contagem, no lugar do combo "Todos".

O combo dizia "Todos" sem dizer quantos, e com o filtro ligado escondia que
existiam outras classes no acervo -- o chip diz as duas coisas numa leitura
so (design, secao B).
"""

from PySide6.QtWidgets import QLabel

from trackclassifier.ui.viewmodel import LABELS_EM_ORDEM
from trackclassifier.ui.widgets.class_chips import TODOS, ClassChips


def _texto(botao, nome: str) -> str:
    return botao.findChild(QLabel, nome).text()


def _rotulo(botao) -> str:
    return _texto(botao, "ClassChipLabel")


def _contagem(botao) -> str:
    return _texto(botao, "ClassChipCount")


def test_ordem_dos_chips_e_todos_antes_de_label_order(qapp):
    chips = ClassChips()

    assert [_rotulo(botao) for botao in chips._botoes.values()] == [
        TODOS,
        *LABELS_EM_ORDEM,
    ]


def test_abre_com_todos_aceso(qapp):
    chips = ClassChips()

    assert chips.rotulo_ativo() == TODOS


def test_clicar_em_um_chip_emite_o_rotulo(qapp):
    chips = ClassChips()
    recebidos = []
    chips.mudou.connect(recebidos.append)

    chips._botoes["+1"].click()

    assert chips.rotulo_ativo() == "+1"
    assert recebidos == ["+1"]


def test_clicar_no_chip_aceso_nao_emite(qapp):
    """Num grupo exclusivo o clique no botao aceso ainda alterna (desmarca e
    remarca) -- reemitir o mesmo rotulo jogaria fora o cache de pixmap dos
    delegates da tabela sem nada ter mudado."""
    chips = ClassChips()
    recebidos = []
    chips.mudou.connect(recebidos.append)

    chips._botoes[TODOS].click()

    assert recebidos == []


def test_acionar_percorre_o_mesmo_caminho_do_clique(qapp):
    """`acionar` existe para quem quer o resultado do clique (a aba, ao
    limpar um filtro; os testes) sem depender do mouse."""
    chips = ClassChips()
    recebidos = []
    chips.mudou.connect(recebidos.append)

    chips.acionar("-1")

    assert chips.rotulo_ativo() == "-1"
    assert recebidos == ["-1"]


def test_acionar_o_rotulo_ja_ativo_nao_emite(qapp):
    chips = ClassChips()
    recebidos = []
    chips.mudou.connect(recebidos.append)

    chips.acionar(TODOS)

    assert recebidos == []


def test_set_contagens_escreve_o_total_e_as_tres_classes(qapp):
    chips = ClassChips()

    chips.set_contagens((71, 186, 206), 464)

    assert _contagem(chips._botoes[TODOS]) == "464"
    assert [_contagem(chips._botoes[rotulo]) for rotulo in LABELS_EM_ORDEM] == [
        "71",
        "186",
        "206",
    ]


def test_biblioteca_vazia_mostra_os_quatro_chips_em_zero(qapp):
    """Zero e informacao ("nesta classe nao ha nada"), e sumir com o chip
    faria a barra mudar de largura quando o acervo enchesse. O que muda e a
    barra ficar inerte: sem acervo nao ha o que filtrar, e o "nao ha nada"
    quem diz e o EmptyState da tabela."""
    chips = ClassChips()

    chips.set_contagens((0, 0, 0), 0)

    assert [
        _contagem(chips._botoes[rotulo]) for rotulo in (TODOS, *LABELS_EM_ORDEM)
    ] == ["0", "0", "0", "0"]
    assert not any(botao.isEnabled() for botao in chips._botoes.values())


def test_set_contagens_com_acervo_reativa_os_chips(qapp):
    chips = ClassChips()
    chips.set_contagens((0, 0, 0), 0)

    chips.set_contagens((71, 186, 206), 464)

    assert all(botao.isEnabled() for botao in chips._botoes.values())


def test_o_chip_diz_que_e_filtro_e_quantas_tracks_tem(qapp):
    """O chip nao tem texto proprio -- o conteudo sao os dois QLabel filhos --
    e sem nome acessivel o leitor de tela anuncia so "botao", quatro vezes."""
    chips = ClassChips()

    chips.set_contagens((71, 186, 206), 464)

    assert chips._botoes["neutra"].accessibleName() == "Filtro neutra"
    assert "186" in chips._botoes["neutra"].accessibleDescription()
    assert "464" in chips._botoes[TODOS].accessibleDescription()


def test_chip_de_classe_carrega_a_propriedade_de_cor_do_qss(qapp):
    """`selecao-vs-classe` no design-tokens.json: chip de classe usa azul,
    ambar e coral -- a cor e o que diz de que classe se trata antes de o olho
    ler o rotulo. A propriedade e lida pelo QSS, entao erra-la deixaria os
    quatro chips cinza sem quebrar teste nenhum."""
    chips = ClassChips()

    assert chips._botoes["-1"].property("class") == "low"
    assert chips._botoes["neutra"].property("class") == "neutral"
    assert chips._botoes["+1"].property("class") == "high"
    assert chips._botoes[TODOS].property("class") is None
