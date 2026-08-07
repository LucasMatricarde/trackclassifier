"""O cabecalho ordenavel: a coluna ativa acende, as outras so no hover.

Testes de imagem comparam DOIS estados entre si, nunca contra cor absoluta:
a cor exata sai do token e o teste nao pode virar uma segunda copia dele.
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QImage

from trackclassifier.ui.widgets.library_header import LibraryHeader
from trackclassifier.ui.widgets.track_model import Column, TrackTableModel


def _cabecalho(qapp) -> LibraryHeader:
    from PySide6.QtWidgets import QApplication, QTableView

    tabela = QTableView()
    cabecalho = LibraryHeader(tabela)
    tabela.setHorizontalHeader(cabecalho)
    tabela.setModel(TrackTableModel([]))
    tabela.resize(1180, 60)
    for coluna in Column:
        tabela.setColumnWidth(coluna, coluna.width)
    # A secao Stretch (Titulo) so recalcula a largura final num
    # QEvent::LayoutRequest que o Qt AGENDA, nao entrega na hora -- sem
    # bombear a fila aqui, o primeiro render() de cada teste pintaria um
    # cabecalho ainda com a largura provisoria (a da soma das colunas
    # fixas) e QImage's teriam tamanhos diferentes so por causa disso,
    # nao da cor. processEvents() entrega o LayoutRequest antes do
    # primeiro _imagem(), entao toda comparacao fica sobre pixels do
    # mesmo tamanho.
    QApplication.processEvents()
    cabecalho._tabela_para_teste = tabela  # mantem viva
    return cabecalho


def _imagem(cabecalho: LibraryHeader) -> QImage:
    imagem = QImage(cabecalho.size(), QImage.Format.Format_ARGB32)
    imagem.fill(QColor("#000000"))
    cabecalho.render(imagem)
    return imagem


def test_a_coluna_ordenada_e_pintada_diferente_das_outras(qapp):
    cabecalho = _cabecalho(qapp)

    cabecalho.setSortIndicator(Column.TITULO, Qt.SortOrder.AscendingOrder)
    por_titulo = _imagem(cabecalho)
    cabecalho.setSortIndicator(Column.BPM, Qt.SortOrder.AscendingOrder)
    por_bpm = _imagem(cabecalho)

    assert por_titulo != por_bpm


def test_ascendente_e_descendente_desenham_setas_diferentes(qapp):
    cabecalho = _cabecalho(qapp)

    cabecalho.setSortIndicator(Column.BPM, Qt.SortOrder.AscendingOrder)
    subindo = _imagem(cabecalho)
    cabecalho.setSortIndicator(Column.BPM, Qt.SortOrder.DescendingOrder)
    descendo = _imagem(cabecalho)

    assert subindo != descendo


def test_o_hover_acende_a_coluna_sob_o_mouse(qapp):
    cabecalho = _cabecalho(qapp)
    cabecalho.setSortIndicator(Column.TITULO, Qt.SortOrder.AscendingOrder)

    sem_hover = _imagem(cabecalho)
    cabecalho.marca_hover(int(Column.BPM))
    com_hover = _imagem(cabecalho)

    assert cabecalho.secao_sob_o_mouse() == int(Column.BPM)
    assert sem_hover != com_hover


def test_sair_do_cabecalho_apaga_o_hover(qapp):
    cabecalho = _cabecalho(qapp)
    cabecalho.marca_hover(int(Column.BPM))

    cabecalho.leaveEvent(QEvent(QEvent.Type.Leave))

    assert cabecalho.secao_sob_o_mouse() == -1


def test_a_onda_nao_recebe_seta_nem_acende(qapp):
    """TrackTableModel.sort retorna cedo para Onda e Capa -- um indicador
    ali prometeria uma ordenacao que nao acontece."""
    cabecalho = _cabecalho(qapp)

    cabecalho.setSortIndicator(Column.TITULO, Qt.SortOrder.AscendingOrder)
    antes = _imagem(cabecalho)
    cabecalho.setSortIndicator(Column.WAVEFORM, Qt.SortOrder.AscendingOrder)
    depois = _imagem(cabecalho)

    assert antes == depois
