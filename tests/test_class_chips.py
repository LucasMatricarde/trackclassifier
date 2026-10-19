"""ClassChips: o filtro de classe com contagem, no lugar do combo "Todos".

O combo dizia "Todos" sem dizer quantos, e com o filtro ligado escondia que
existiam outras classes no acervo -- o chip diz as duas coisas numa leitura
so (design, secao B).
"""

from pathlib import Path

from PySide6.QtWidgets import QLabel

from trackclassifier.ui.tokens import (
    COLOR_CLASSIFICATION_LENTO_BASE,
    COLOR_CLASSIFICATION_NEUTRO_BASE,
)
from trackclassifier.ui.viewmodel import LABELS_EM_ORDEM
from trackclassifier.ui.widgets.class_chips import TODOS, ClassChips

RAIZ = Path(__file__).resolve().parent.parent


def _tem_a_cor(img, geo, alvo: str, tolerancia: int = 24) -> bool:
    """Algum pixel da regiao chega perto da cor alvo?

    Com antialiasing o miolo do glifo chega na cor pura e as bordas sao mistura
    com o fundo; exigir o hex exato faria o teste depender da fonte de cada
    plataforma.
    """
    r, g, b = (int(alvo[i : i + 2], 16) for i in (1, 3, 5))
    for y in range(geo.top(), geo.bottom() + 1):
        for x in range(geo.left(), geo.right() + 1):
            cor = img.pixelColor(x, y)
            if (
                abs(cor.red() - r) <= tolerancia
                and abs(cor.green() - g) <= tolerancia
                and abs(cor.blue() - b) <= tolerancia
            ):
                return True
    return False


def _label(botao, nome: str) -> QLabel:
    return botao.findChild(QLabel, nome)


def _texto(botao, nome: str) -> str:
    return _label(botao, nome).text()


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


def test_o_chip_cabe_o_rotulo_e_o_numero(qapp):
    """QPushButton::sizeHint() sai do texto/icone do BOTAO e ignora o layout
    dos filhos: como o chip nao tem texto proprio (o conteudo sao dois QLabel),
    o padrao pedia 26px, os labels ficavam com 1px e o chip saia VAZIO na tela,
    so com a borda. Achado do render da 1.5 -- nenhum teste que so le `.text()`
    pega isto, porque geometria so existe com o widget mostrado e o layout
    ativado, e os testes acima nunca chamam show()."""
    chips = ClassChips()
    chips.set_contagens((71, 186, 206), 464)
    chips.resize(600, chips.sizeHint().height())
    chips.show()
    qapp.processEvents()

    for rotulo, botao in chips._botoes.items():
        texto = _label(botao, "ClassChipLabel")
        numero = _label(botao, "ClassChipCount")
        assert texto.width() >= texto.sizeHint().width(), f"rotulo {rotulo!r} cortado"
        assert numero.width() >= numero.sizeHint().width(), f"numero {rotulo!r} cortado"

    chips.close()


def _chips_com_qss(qapp, contagens, total):
    """Chips com o app.qss de verdade aplicado.

    A fixture qapp nao aplica o stylesheet (o resto dos testes nao precisa
    dele), entao o QSS entra aqui e quem chama o devolve: mesma abordagem do
    test_a_altura_renderizada_dos_controles_bate_com_os_tokens.
    """
    from PySide6.QtWidgets import QApplication

    from trackclassifier.ui.fonts import registra_fontes

    registra_fontes()
    anterior = QApplication.instance().styleSheet()
    QApplication.instance().setStyleSheet(
        (RAIZ / "src" / "trackclassifier" / "ui" / "app.qss").read_text(encoding="utf-8")
    )
    chips = ClassChips()
    chips.set_contagens(contagens, total)
    chips.resize(600, 28)
    chips.show()
    for _ in range(4):
        qapp.processEvents()
    return chips, anterior


def test_o_texto_do_chip_sai_na_cor_da_classe(qapp):
    """Regra QSS de DESCENDENTE nao chega no QLabel filho.

    Com `QPushButton#ClassChip[class="low"] QLabel { color: ... }` o chip aceso
    pintava fundo e borda da classe e o TEXTO continuava no cinza do fallback,
    em qualquer estado. Nenhum teste que le `.text()` chega perto disto: so o
    pixel mostra, e foi o render da Biblioteca que revelou (Task 1.5).
    """
    from PySide6.QtWidgets import QApplication

    chips, anterior = _chips_com_qss(qapp, (71, 186, 206), 464)
    try:
        img = chips.grab().toImage()

        assert _tem_a_cor(
            img, chips._botoes["-1"].geometry(), COLOR_CLASSIFICATION_LENTO_BASE
        )
        assert _tem_a_cor(
            img, chips._botoes["neutra"].geometry(), COLOR_CLASSIFICATION_NEUTRO_BASE
        )
        chips.close()
    finally:
        QApplication.instance().setStyleSheet(anterior)


def test_o_chip_do_acervo_vazio_apaga_o_texto(qapp):
    """No acervo vazio o texto apaga (textDisabled) e a cor de classe NAO pode
    aparecer: o `color` de QPushButton:disabled nao desce para os filhos, entao
    sem as regras `:disabled` nos label o chip do acervo vazio apagaria so a
    borda e continuaria parecendo clicavel. No template elas ficam DEPOIS das
    regras de classe -- a especificidade empata (id + atributo contra id +
    pseudo-estado) e quem desempata e a ordem."""
    from PySide6.QtWidgets import QApplication

    from trackclassifier.ui.tokens import COLOR_TEXT_DISABLED

    chips, anterior = _chips_com_qss(qapp, (0, 0, 0), 0)
    try:
        img = chips.grab().toImage()

        assert _tem_a_cor(img, chips._botoes["neutra"].geometry(), COLOR_TEXT_DISABLED)
        assert not _tem_a_cor(
            img, chips._botoes["neutra"].geometry(), COLOR_CLASSIFICATION_NEUTRO_BASE
        )
        chips.close()
    finally:
        QApplication.instance().setStyleSheet(anterior)
