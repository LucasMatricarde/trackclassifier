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
    assert overview._peaks_path is None


def test_fila_e_inspector_refletem_a_track_sem_acao_falsa(qapp):
    queue = ReviewQueueStrip()
    queue.set_rows((_row(),))
    assert queue.total() == 1
    assert queue.model().row_at(0).display_title == "The 11th Hour"

    inspector = TrackInspector()
    inspector.set_track(_row())
    assert inspector.isEnabled()
    assert inspector.title.text() == "The 11th Hour"
    assert "Classe: -1" in inspector.details.text()
