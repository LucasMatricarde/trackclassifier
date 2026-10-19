"""Behavior and geometry of the new dashboard composition."""

from trackclassifier.ui.viewmodel import TrackRow
from trackclassifier.ui.widgets.app_header import AppHeader
from trackclassifier.ui.widgets.review_header import ReviewHeader
from trackclassifier.ui.widgets.review_queue import ReviewQueueStrip
from trackclassifier.ui.widgets.track_inspector import TrackInspector
from trackclassifier.ui.widgets.waveform_overview import WaveformOverview


def _row() -> TrackRow:
    return TrackRow(
        sha1="track-a",
        filename="sample.wav",
        label="-1",
        predicted="neutra",
        score=0.2,
        confidence=0.73,
        bpm=123.0,
        duration_s=433.0,
        energy_curve=(0.2, 0.8, 0.3),
        peak_offset_s=154.0,
        path_hint="/tmp/sample.wav",
        title="The 11th Hour",
        artist="Brunello & Cella Babini",
        genre="Tech House",
    )


def test_header_roteia_pagina_e_scan(qapp):
    header = AppHeader(("Revisao", "Biblioteca", "Modelo", "Configuracao"))
    pages = []
    scans = []
    header.page_requested.connect(pages.append)
    header.scan_requested.connect(lambda: scans.append(True))

    header._buttons[1].click()
    header.scan_button.click()

    assert pages == [1]
    assert scans == [True]
    assert header._buttons[1].isChecked()


def test_review_header_mostra_dados_reais_e_progresso_local(qapp):
    header = ReviewHeader()
    header.set_track(_row(), remaining=30, position=2, low_confidence=False)

    assert header.title.text() == "The 11th Hour"
    assert header.genre.text() == "Tech House"
    assert header.prediction.text() == "neutra"
    assert header.confidence.text() == "0.73"
    assert header.progress.text() == "2 / 30"
    assert header.progress_bar.fraction() == 2 / 30


def test_overview_descarta_peaks_de_outra_track(qapp):
    overview = WaveformOverview()
    overview.set_row(_row())
    overview.set_peaks_path("outra", "/tmp/late.npy")
    # O estado da mini-onda mora no _MiniOnda interno desde que os botoes
    # < > da Fase 4 dividiram o widget em moldura + onda.
    assert overview._mini._peaks_path is None


def test_fila_e_inspector_refletem_a_track_sem_acao_falsa(qapp):
    queue = ReviewQueueStrip()
    queue.set_rows((_row(),), remaining=1)
    assert queue.total() == 1
    assert queue.model().row_at(0).display_title == "The 11th Hour"

    inspector = TrackInspector()
    inspector.set_track(_row())
    assert inspector.isEnabled()
    assert inspector.title.text() == "The 11th Hour"
    assert inspector.ficha["Classe atual"].valor.text() == "-1"


def test_a_ficha_tecnica_tem_os_pares_na_ordem_do_design(qapp):
    """Genero, BPM, Key, Duracao, Classe -- e Confianca depois.

    A ficha substitui a linha unica de texto ("Genero: X\nBPM: Y...") por
    pares rotulo/valor: o olho acha o numero sem ler a frase inteira, e o
    valor numerico pode ficar em mono, que e a regra do sistema."""
    from dataclasses import replace

    from trackclassifier.ui.viewmodel import format_duration

    inspector = TrackInspector()
    inspector.set_track(
        replace(_row(), genre="Progressive House", bpm=128.0, duration_s=433.0)
    )

    assert list(inspector.ficha) == [
        "Genero",
        "BPM",
        "Key (Camelot)",
        "Duracao",
        "Classe atual",
        "Confianca",
    ]
    assert inspector.ficha["Genero"].valor.text() == "Progressive House"
    assert inspector.ficha["BPM"].valor.text() == "128"
    assert inspector.ficha["Duracao"].valor.text() == format_duration(433.0)
    assert inspector.ficha["Classe atual"].valor.text() == "-1"


def test_a_key_da_ficha_e_camelot_e_sem_key_e_travessao(qapp):
    """Camelot sempre: o painel nao segue o alternador de notacao da tabela, e
    o proprio rotulo diz qual notacao esta mostrando.

    Sem key, o chip mostra o travessao apagado -- um chip colorido vazio
    sugeriria que a track TEM tonalidade e o app so nao soube formatar."""
    from dataclasses import replace

    from trackclassifier.keys import Key, KeyNotation, Mode
    from trackclassifier.ui.widgets.key_chip import format_key

    inspector = TrackInspector()
    inspector.set_track(replace(_row(), key=Key(3, Mode.MAJOR)))
    assert inspector.ficha["Key (Camelot)"].valor.text() == Key(3, Mode.MAJOR).camelot

    inspector.set_track(replace(_row(), key=None))
    assert inspector.ficha["Key (Camelot)"].valor.text() == format_key(
        None, KeyNotation.CAMELOT
    )


def test_confianca_so_aparece_quando_existe(qapp):
    """Na Biblioteca a confianca e None por construcao (a track ja esta
    classificada, e a confianca do modelo sobre uma decisao humana tomada nao
    muda acao -- ver o design). Uma linha fixa com travessao seria ruido
    permanente: mostrar condicional e a diferenca entre "nao se aplica" e
    "faltou dado"."""
    from dataclasses import replace

    inspector = TrackInspector()
    inspector.set_track(replace(_row(), confidence=None))
    assert not inspector.ficha["Confianca"].caixa.isVisibleTo(inspector)

    inspector.set_track(replace(_row(), confidence=0.73))
    assert inspector.ficha["Confianca"].caixa.isVisibleTo(inspector)
    assert inspector.ficha["Confianca"].valor.text() == "73%"


def test_capa_ausente_cai_no_placeholder_com_a_inicial(qapp):
    """Sem capa e o caso comum (acervo de promos nao tem tag nenhuma, e sem
    tag nao ha capa): em vez de area vazia, a inicial do titulo sobre o fundo
    de capa -- a mesma leitura que a coluna Capa da tabela ja faz."""
    from dataclasses import replace

    inspector = TrackInspector()
    inspector.set_track(replace(_row(), cover_path=""))

    assert inspector.cover.text() == "T"
    assert inspector.cover.pixmap().isNull()
