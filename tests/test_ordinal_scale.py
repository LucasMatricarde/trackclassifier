"""A escala e uma so, usada pela tabela e pela Revisao em tamanhos diferentes."""

from PySide6.QtGui import QColor, QImage, QPainter

from trackclassifier.ui.widgets.ordinal_scale import (
    GAP,
    LADO_LINHA,
    OrdinalScale,
    desenha_escala,
    indice_do_rotulo,
)


def _pinta(aceso, largura=LADO_LINHA, altura=LADO_LINHA) -> QImage:
    from PySide6.QtCore import QPoint

    imagem = QImage(60, 30, QImage.Format.Format_ARGB32)
    imagem.fill(QColor(0, 0, 0))
    painter = QPainter(imagem)
    desenha_escala(painter, QPoint(30, 15), aceso, largura=largura, altura=altura)
    painter.end()
    return imagem


def test_indice_segue_a_ordem_ordinal():
    assert indice_do_rotulo("-1") == 0
    assert indice_do_rotulo("neutra") == 1
    assert indice_do_rotulo("+1") == 2


def test_indice_de_rotulo_ausente_e_none():
    assert indice_do_rotulo(None) is None
    assert indice_do_rotulo("qualquer") is None


def test_cada_posicao_pinta_diferente(qapp):
    pintadas = [_pinta(i) for i in range(3)]

    # A POSICAO acesa e a informacao: se duas coincidissem, a escala nao
    # teria leitura.
    assert pintadas[0] != pintadas[1]
    assert pintadas[1] != pintadas[2]
    assert pintadas[0] != pintadas[2]


def test_nenhum_aceso_ainda_desenha_os_contornos(qapp):
    vazia = QImage(60, 30, QImage.Format.Format_ARGB32)
    vazia.fill(QColor(0, 0, 0))

    assert _pinta(None) != vazia


def test_widget_e_funcao_pintam_o_mesmo(qapp):
    largura, altura = 5, 20
    escala = OrdinalScale(largura, altura)
    escala.set_label("+1")

    # O widget existe so para entrar num layout; se ele desenhasse por
    # conta propria, a mesma classe leria diferente em duas telas.
    assert escala.aceso() == 2
    assert escala.size().width() == largura * 3 + GAP * 2
    assert escala.size().height() == altura


def test_widget_sem_rotulo_nao_acende(qapp):
    escala = OrdinalScale()
    escala.set_label("+1")
    escala.set_label(None)

    assert escala.aceso() is None
