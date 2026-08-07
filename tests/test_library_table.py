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

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFocusEvent, QImage

from tests.test_viewmodel import _config, _servico
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


def test_sem_linha_atual_nao_quebra(qapp, tmp_path):
    """Biblioteca vazia (ou antes da primeira selecao) tem currentIndex
    invalido -- visualRect de um index invalido e um retangulo vazio."""
    tabela = LibraryTable()
    tabela.setModel(TrackTableModel([]))
    tabela.resize(600, 200)

    _foco(tabela, True)

    _imagem(tabela)  # nao levanta
