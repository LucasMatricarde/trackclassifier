"""Fumaca da janela: abre, carrega, aperta 1/2/3, fecha.

Roda com QT_QPA_PLATFORM=offscreen (conftest) e SimulatedPlayer, entao nao
precisa de display nem de dispositivo de audio.
"""

import numpy as np
import soundfile as sf
from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtGui import QKeyEvent

from tests.test_viewmodel import _config, _servico
from trackclassifier.ui.viewmodel import library_state, model_state, review_state
from trackclassifier.ui.widgets.track_model import Column, TrackTableModel
from trackclassifier.ui.window import MainWindow


def _tecla(widget, chave):
    evento = QKeyEvent(QKeyEvent.Type.KeyPress, chave, Qt.KeyboardModifier.NoModifier)
    widget.keyPressEvent(evento)


def _espera_sinal(sinal, timeout_ms=2000):
    """Bombeia o loop de eventos ate o sinal disparar ou estourar o timeout.

    O worker mora numa QThread propria (ver window.MainWindow); a conexao
    entre o sinal da aba e o slot do worker e QueuedConnection porque emissor
    e receptor vivem em threads diferentes. Sem isto, o assert rodaria antes
    do worker ter tido a chance de processar o evento -- falha deterministica,
    nao flakiness, porque nada aqui cede o controle para a outra thread.
    """
    loop = QEventLoop()
    sinal.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


def test_table_model_expoe_as_colunas_da_fase_1(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    modelo = TrackTableModel(list(library_state(servico).rows))

    assert modelo.rowCount() == 9
    assert modelo.columnCount() == len(Column)
    cabecalhos = [
        modelo.headerData(coluna, Qt.Orientation.Horizontal) for coluna in Column
    ]
    assert cabecalhos == ["Onda", "Arquivo", "BPM", "Classificacao", "Confianca", "Duracao"]


def test_table_model_ordena_por_bpm_com_none_no_fim(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    modelo = TrackTableModel(list(library_state(servico).rows))
    modelo.sort(Column.BPM, Qt.SortOrder.AscendingOrder)

    bpms = [modelo.row_at(i).bpm for i in range(modelo.rowCount())]
    assert bpms == sorted(bpms)


def test_janela_abre_com_as_tres_abas(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        assert janela.tabs.count() == 3
        assert [janela.tabs.tabText(i) for i in range(3)] == [
            "Revisao",
            "Biblioteca",
            "Modelo",
        ]
    finally:
        janela.close()


def test_tecla_3_classifica_a_atual_como_up(qapp, tmp_path):
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        assert janela.review_tab.current_sha1 is not None

        _tecla(janela.review_tab, Qt.Key.Key_3)
        _espera_sinal(janela._worker.states_changed)

        assert list(config.folders[Label.UP].glob("nova_0.7.wav"))
    finally:
        janela.close()


def test_fila_vazia_mostra_estado_orientando_a_escanear(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        assert janela.review_tab.current_sha1 is None
        assert "escanear" in janela.review_tab.empty_text().lower()
    finally:
        janela.close()
