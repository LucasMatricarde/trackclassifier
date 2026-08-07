from trackclassifier.ui.tokens import (
    COLOR_CLASSIFICATION_NEUTRO_BG,
    COLOR_STATE_DANGER,
    COLOR_SURFACE_2,
    COLOR_TEXT_DISABLED,
)
from trackclassifier.ui.widgets.confusion_matrix import ConfusionMatrix, severidade

CHEIA = ((62, 10, 2), (13, 68, 8), (3, 11, 37))


def test_severidade_e_a_distancia_ordinal():
    assert severidade(0, 0) == 0
    assert severidade(0, 1) == 1
    assert severidade(0, 2) == 2
    assert severidade(2, 0) == 2


def test_diagonal_usa_superficie_e_borda(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(CHEIA)

    assert COLOR_SURFACE_2 in matriz.celula(1, 1).styleSheet()


def test_erro_grave_usa_a_tinta_de_danger(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(CHEIA)

    # 0,2 e 2,0 sao os dois cantos de distancia 2 -- confundir lento com
    # animada. O vermelho aparece so neles.
    assert COLOR_STATE_DANGER in matriz.celula(0, 2).styleSheet()
    assert COLOR_STATE_DANGER in matriz.celula(2, 0).styleSheet()
    assert COLOR_STATE_DANGER not in matriz.celula(0, 1).styleSheet()


def test_erro_leve_usa_o_bg_de_neutro(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(CHEIA)

    assert COLOR_CLASSIFICATION_NEUTRO_BG in matriz.celula(0, 1).styleSheet()


def test_celula_zerada_fica_apagada(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(((0, 0, 0), (0, 0, 0), (0, 0, 0)))

    # Presente mas sem chamar atencao: uma matriz de zeros nao pode
    # parecer uma matriz de erros graves.
    assert COLOR_TEXT_DISABLED in matriz.celula(0, 2).styleSheet()


def test_celula_zerada_mantem_o_fundo_da_severidade(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(((0, 0, 0), (0, 0, 0), (0, 0, 0)))

    # So o numero apaga: o fundo continua dizendo onde a celula fica na
    # escala, senao a grade inteira vira um bloco cinza sem leitura.
    assert COLOR_SURFACE_2 in matriz.celula(0, 0).styleSheet()


def test_diagonal_toda_zerada_nao_quebra(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(((0, 5, 5), (5, 0, 5), (5, 5, 0)))

    assert matriz.celula(0, 0).text() == "0"


def test_antidiagonal_toda_zerada_nao_quebra(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(((5, 5, 0), (5, 5, 5), (0, 5, 5)))

    assert matriz.celula(0, 2).text() == "0"


def test_sem_matriz_esconde_a_grade(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(CHEIA)
    matriz.set_confusion(None)

    # Modelo nao treinado esconde a grade em vez de mostrar nove zeros:
    # matriz zerada e um resultado, "ainda nao ha matriz" e outra coisa.
    assert not matriz.grade.isVisibleTo(matriz)


def test_valores_aparecem_na_ordem_real_x_previsto(qapp):
    matriz = ConfusionMatrix()
    matriz.set_confusion(CHEIA)

    # Linha = real, coluna = previsto: a convencao de hoje, mantida.
    assert matriz.celula(0, 1).text() == "10"
    assert matriz.celula(1, 0).text() == "13"
