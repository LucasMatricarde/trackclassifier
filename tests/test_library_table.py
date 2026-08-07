"""O anel de foco: 'o teclado age NESTA linha agora'.

A tabela e SingleSelection + SelectRows, entao selecao e linha atual sao
sempre a mesma -- o anel nao distingue as duas. Ele responde a pergunta que
hoje nao tem resposta visual: com o foco no campo de busca, a linha continua
pintada como selecionada, mas digitar 1/2/3 nao a reclassifica.

O foco e estado explicito do widget (focusInEvent/focusOutEvent) e nao uma
consulta a hasFocus() no meio do paint: em QT_QPA_PLATFORM=offscreen o foco
real de janela nao e confiavel, e o QTableView nao repinta o viewport quando
o foco entra ou sai.
"""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFocusEvent, QImage

from tests.test_viewmodel import _config, _servico
from trackclassifier.ui.colors import para_qcolor
from trackclassifier.ui.tokens import COLOR_ACCENT_BASE
from trackclassifier.ui.viewmodel import library_state
from trackclassifier.ui.widgets.library_table import LibraryTable
from trackclassifier.ui.widgets.track_model import TrackTableModel


def _tabela(tmp_path) -> LibraryTable:
    servico = _servico(_config(tmp_path))
    tabela = LibraryTable()
    tabela.setModel(TrackTableModel(list(library_state(servico).rows)))
    tabela.resize(600, 200)
    tabela.setCurrentIndex(tabela.model().index(0, 0))
    return tabela


def _imagem(tabela: LibraryTable) -> QImage:
    imagem = QImage(tabela.viewport().size(), QImage.Format.Format_ARGB32)
    imagem.fill(QColor("#000000"))
    tabela.viewport().render(imagem)
    return imagem


def _foco(tabela: LibraryTable, entrando: bool) -> None:
    evento = QFocusEvent(
        QFocusEvent.Type.FocusIn if entrando else QFocusEvent.Type.FocusOut,
        Qt.FocusReason.OtherFocusReason,
    )
    if entrando:
        tabela.focusInEvent(evento)
    else:
        tabela.focusOutEvent(evento)


def test_sem_foco_nao_ha_anel(qapp, tmp_path):
    tabela = _tabela(tmp_path)

    _foco(tabela, False)

    assert tabela.tem_foco_de_teclado() is False


def test_com_foco_a_linha_atual_muda_de_pintura(qapp, tmp_path):
    tabela = _tabela(tmp_path)

    _foco(tabela, False)
    sem_anel = _imagem(tabela)
    _foco(tabela, True)
    com_anel = _imagem(tabela)

    assert tabela.tem_foco_de_teclado() is True
    assert sem_anel != com_anel


def test_o_anel_some_quando_o_foco_sai(qapp, tmp_path):
    tabela = _tabela(tmp_path)

    _foco(tabela, True)
    com_anel = _imagem(tabela)
    _foco(tabela, False)
    depois = _imagem(tabela)

    assert com_anel != depois


def _conta_pixels_do_anel(imagem: QImage, retangulo: QRect) -> int:
    cor_anel = para_qcolor(COLOR_ACCENT_BASE)
    contagem = 0
    for y in range(retangulo.top(), retangulo.bottom() + 1):
        for x in range(retangulo.left(), retangulo.right() + 1):
            if imagem.pixelColor(x, y) == cor_anel:
                contagem += 1
    return contagem


def test_o_anel_pinta_a_linha_atual_e_nao_a_vizinha(qapp, tmp_path):
    """As quatro asercoes de imagem-inteira acima provam que ALGO muda de
    pintura com o foco, mas nao ONDE -- a spec promete explicitamente 'a
    linha vizinha, nao'. Este teste conta pixels de verdade dentro da linha
    atual (index 0, tem que haver alguns) e dentro da faixa vertical da
    linha vizinha (index 1, tem que ser zero)."""
    tabela = _tabela(tmp_path)
    assert tabela.model().rowCount() >= 2, "precisa de pelo menos duas linhas para comparar"

    _foco(tabela, True)
    imagem = _imagem(tabela)

    linha_atual = tabela.visualRect(tabela.model().index(0, 0))
    linha_vizinha = tabela.visualRect(tabela.model().index(1, 0))

    # O anel e da linha inteira (largura do viewport), nao so da celula da
    # coluna 0 -- ver o comentario em library_table.LibraryTable.paintEvent.
    # Aqui varremos a largura toda em ambas as faixas para nao dar falso
    # negativo por olhar so a coluna 0.
    faixa_atual = QRect(0, linha_atual.top(), tabela.viewport().width(), linha_atual.height())
    faixa_vizinha = QRect(
        0, linha_vizinha.top(), tabela.viewport().width(), linha_vizinha.height()
    )

    assert _conta_pixels_do_anel(imagem, faixa_atual) > 0
    assert _conta_pixels_do_anel(imagem, faixa_vizinha) == 0


def test_sem_linha_atual_nao_quebra(qapp, tmp_path):
    """Biblioteca vazia (ou antes da primeira selecao) tem currentIndex
    invalido -- visualRect de um index invalido e um retangulo vazio."""
    tabela = LibraryTable()
    tabela.setModel(TrackTableModel([]))
    tabela.resize(600, 200)

    _foco(tabela, True)

    _imagem(tabela)  # nao levanta
