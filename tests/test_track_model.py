"""TrackTableModel: larguras, alinhamento e tipografia das colunas fixas.

TrackRow e construida a mao, sem TrackService/ffmpeg -- o mesmo padrao de
tests/test_library_tab.py. Estes testes olham so o CONTRATO do modelo com o
QTableView (o que data()/headerData() devolvem por role), nao pintura --
isso e coberto em tests/test_delegates.py para as colunas que tem delegate
proprio.
"""

from PySide6.QtCore import Qt

from trackclassifier.ui.viewmodel import TrackRow
from trackclassifier.ui.widgets.track_model import Column, TrackTableModel


def _linha() -> TrackRow:
    return TrackRow(
        sha1="sha0001",
        filename="track0001.wav",
        label="+1",
        predicted=None,
        score=None,
        confidence=None,
        bpm=128.0,
        duration_s=245.0,
        energy_curve=(0.1, 0.4, 0.2),
        peak_offset_s=1.0,
        path_hint="/fake/track0001.wav",
        genre="Progressive House",
    )


def test_genero_tem_106px_no_mockup_3a():
    """96 elidia rotulo comum do acervo real ("Progressive House"); 106 e
    o que o mockup mede para a coluna."""
    assert Column.GENERO.width == 106


def test_cabecalho_alinha_tudo_a_esquerda(qapp):
    """QHeaderView centraliza por padrao -- o mockup alinha os OITO
    cabecalhos a esquerda, inclusive os de colunas cuja celula e a
    direita (BPM, Dur): o cabecalho rotula a coluna, nao espelha o dado."""
    modelo = TrackTableModel([_linha()])

    for coluna in Column:
        alinhamento = modelo.headerData(
            coluna, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole
        )
        assert alinhamento == (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


def test_alinhamento_de_celula_por_coluna(qapp):
    """Diferente do cabecalho (sempre a esquerda): a CELULA de CAPA/KEY/
    CLASSIFICACAO centraliza (chip/quadrados), BPM/DUR vao a direita (dado
    numerico), e o resto fica a esquerda -- o mesmo lookup que resolve
    FontRole/ForegroundRole (_ESTILO_POR_COLUNA) resolve este role tambem."""
    modelo = TrackTableModel([_linha()])
    esquerda = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    centro = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
    direita = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

    def alinhamento(coluna: Column):
        return modelo.data(modelo.index(0, coluna), Qt.ItemDataRole.TextAlignmentRole)

    assert alinhamento(Column.CAPA) == centro
    assert alinhamento(Column.KEY) == centro
    assert alinhamento(Column.CLASSIFICACAO) == centro
    assert alinhamento(Column.BPM) == direita
    assert alinhamento(Column.DURACAO) == direita
    assert alinhamento(Column.TITULO) == esquerda
    assert alinhamento(Column.WAVEFORM) == esquerda
    assert alinhamento(Column.GENERO) == esquerda


def test_genero_e_duracao_pintam_em_text_secondary(qapp):
    """GENERO e DUR ficam mais apagadas que o resto da linha no mockup;
    BPM continua em text.primary (sem ForegroundRole)."""
    from trackclassifier.ui.tokens import COLOR_TEXT_SECONDARY

    modelo = TrackTableModel([_linha()])

    cor_genero = modelo.data(modelo.index(0, Column.GENERO), Qt.ItemDataRole.ForegroundRole)
    cor_duracao = modelo.data(modelo.index(0, Column.DURACAO), Qt.ItemDataRole.ForegroundRole)
    cor_bpm = modelo.data(modelo.index(0, Column.BPM), Qt.ItemDataRole.ForegroundRole)

    assert cor_genero.name() == COLOR_TEXT_SECONDARY.lower()
    assert cor_duracao.name() == COLOR_TEXT_SECONDARY.lower()
    assert cor_bpm is None


def test_bpm_e_duracao_usam_fonte_mono_genero_usa_sans(qapp):
    modelo = TrackTableModel([_linha()])

    fonte_bpm = modelo.data(modelo.index(0, Column.BPM), Qt.ItemDataRole.FontRole)
    fonte_duracao = modelo.data(modelo.index(0, Column.DURACAO), Qt.ItemDataRole.FontRole)
    fonte_genero = modelo.data(modelo.index(0, Column.GENERO), Qt.ItemDataRole.FontRole)
    fonte_titulo = modelo.data(modelo.index(0, Column.TITULO), Qt.ItemDataRole.FontRole)

    assert "Mono" in fonte_bpm.family()
    assert "Mono" in fonte_duracao.family()
    assert "Mono" not in fonte_genero.family()
    # TITULO tem delegate proprio (TitleDelegate) -- o modelo nao opina
    # sobre a fonte dele.
    assert fonte_titulo is None
