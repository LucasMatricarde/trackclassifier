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


def _com_inbox_de_quatro(config):
    # Conteudo distinto por faixa -- nao so o nome. A identidade de uma
    # track e o sha1 do conteudo (nunca o caminho), e decide() busca em
    # _inbox por sha1; com np.zeros(100) repetido as 4 tracks colidiriam
    # no mesmo sha1 e decide() moveria sempre a primeira encontrada,
    # mascarando exatamente o bug que estes testes existem para pegar.
    # Amplitude tem que ficar dentro de [-1, 1]: sf.write grava PCM16 por
    # padrao, e valores fora da faixa saturam todos no mesmo extremo --
    # o que colidiria de novo, so que por um motivo diferente (clipping,
    # nao ausencia de sinal).
    for i in range(4):
        sinal = np.full(100, (i + 1) / 10.0, dtype=np.float32)
        sf.write(config.inbox / f"n{i}_0.{i}.wav", sinal, 22050)


def test_pular_avanca_e_voltar_recua_na_janela_local(qapp, tmp_path):
    config = _config(tmp_path)
    _com_inbox_de_quatro(config)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        fila = servico.queue()
        primeira, segunda = fila[0].sha1, fila[1].sha1
        assert janela.review_tab.current_sha1 == primeira

        _tecla(janela.review_tab, Qt.Key.Key_Right)
        assert janela.review_tab.current_sha1 == segunda

        _tecla(janela.review_tab, Qt.Key.Key_Left)
        assert janela.review_tab.current_sha1 == primeira

        # Ja na posicao 0: voltar de novo nao pode dar wraparound nem quebrar.
        _tecla(janela.review_tab, Qt.Key.Key_Left)
        assert janela.review_tab.current_sha1 == primeira
    finally:
        janela.close()


def test_pular_para_alem_da_janela_local_para_na_ultima_track_cacheada(qapp, tmp_path):
    config = _config(tmp_path)
    _com_inbox_de_quatro(config)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        fila = servico.queue()
        # current + ate 3 upcoming = no maximo 4 tracks na janela local.
        ultima_da_janela = fila[3].sha1

        for _ in range(5):
            _tecla(janela.review_tab, Qt.Key.Key_Right)

        assert janela.review_tab.current_sha1 == ultima_da_janela
    finally:
        janela.close()


def test_decidir_apos_pular_afeta_a_track_exibida_localmente_nao_a_original(qapp, tmp_path):
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    _com_inbox_de_quatro(config)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        fila = servico.queue()
        primeira_nome, segunda_nome = fila[0].filename, fila[1].filename

        _tecla(janela.review_tab, Qt.Key.Key_Right)
        assert janela.review_tab.current_sha1 == fila[1].sha1

        _tecla(janela.review_tab, Qt.Key.Key_3)
        _espera_sinal(janela._worker.states_changed)

        # A que foi movida e a que estava exibida (a segunda, pos-skip) --
        # nao a primeira, que era state.current no snapshot original.
        assert list(config.folders[Label.UP].glob(segunda_nome))
        assert not list(config.folders[Label.UP].glob(primeira_nome))
    finally:
        janela.close()
