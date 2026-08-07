from trackclassifier.ui.widgets.class_balance import ClassBalance, recomendacao


def test_sem_recomendacao_quando_as_tres_sao_iguais():
    assert recomendacao((50, 50, 50)) is None


def test_sem_recomendacao_logo_acima_do_limiar():
    # 71 / 100 = 71% > 70%: desbalanceado, mas nao o bastante para ocupar
    # espaco na tela toda vez.
    assert recomendacao((71, 100, 100)) is None


def test_recomendacao_nomeia_a_classe_minoritaria():
    texto = recomendacao((74, 89, 51))

    assert texto is not None
    # +1 tem 51/89 = 57% da maior. E a classe a rotular.
    assert "+1" in texto
    assert "57%" in texto


def test_recomendacao_com_biblioteca_vazia_nao_divide_por_zero():
    # Biblioteca vazia nao esta desbalanceada, esta vazia -- e o empty
    # state da aba ja cobre esse caso.
    assert recomendacao((0, 0, 0)) is None


def test_recomendacao_com_uma_classe_zerada():
    texto = recomendacao((0, 40, 40))

    assert texto is not None
    assert "-1" in texto
    assert "0%" in texto


def test_barra_da_maior_classe_ocupa_tudo(qapp):
    balanco = ClassBalance()
    balanco.set_counts((74, 89, 51))

    # Normalizada pela maior: a barra de neutra vai a 100% e as outras
    # sao lidas em relacao a ela.
    assert balanco.proporcao(1) == 1.0


def test_barra_proporcional_a_maior(qapp):
    balanco = ClassBalance()
    balanco.set_counts((74, 89, 51))

    assert balanco.proporcao(2) == round(51 / 89, 4)


def test_contagem_aparece_no_rotulo(qapp):
    balanco = ClassBalance()
    balanco.set_counts((74, 89, 51))

    assert balanco.contagem(0).text() == "74"


def test_biblioteca_vazia_desenha_tres_barras_em_zero(qapp):
    balanco = ClassBalance()
    balanco.set_counts((0, 0, 0))

    # Barra em zero e informacao ("falta esta classe"), nao ausencia de
    # linha -- por isso nada some.
    assert all(balanco.proporcao(i) == 0.0 for i in range(3))


def test_recomendacao_some_quando_o_treino_equilibra(qapp):
    balanco = ClassBalance()
    balanco.set_counts((74, 89, 51))
    balanco.set_counts((89, 89, 89))

    assert not balanco.recomendacao_label.isVisibleTo(balanco)
