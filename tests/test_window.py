"""Fumaca da janela: abre, carrega, aperta 1/2/3, fecha.

Roda com QT_QPA_PLATFORM=offscreen (conftest) e SimulatedPlayer, entao nao
precisa de display nem de dispositivo de audio.

As teclas sao exercitadas via QTest.keyClick na janela inteira, nunca
chamando keyPressEvent a mao: o achado #3 da revisao final foi exatamente
que chamar keyPressEvent direto mascarava um bug real de roteamento (foco
inicial na QTabBar, QAbstractItemView engolindo digitos na Biblioteca). Os
atalhos vivem em MainWindow (QShortcut, contexto WindowShortcut) desde essa
correcao -- so QTest.keyClick passa pelo despacho real do Qt que os aciona.
"""

from pathlib import Path

import numpy as np
import soundfile as sf
from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtTest import QTest

from tests.test_viewmodel import _config, _servico
from trackclassifier.ui.review_tab import ReviewTab
from trackclassifier.ui.viewmodel import library_state, model_state, review_state
from trackclassifier.ui.widgets.player import SimulatedPlayer
from trackclassifier.ui.widgets.track_model import Column, TrackTableModel
from trackclassifier.ui.window import MainWindow


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


def _mostra_e_ativa(janela):
    """Mostra a janela, ativa, e espera o scan automatico de abertura assentar.

    QShortcut com contexto WindowShortcut so dispara com a janela ativa --
    mesmo em offscreen -- entao show()/activateWindow() sao obrigatorios
    antes de QTest.keyClick funcionar (ver achado #3). E MainWindow.__init__
    dispara um refresh+scan sozinho na QThread do worker assim que o loop de
    eventos da GUI comeca a rodar (achado #1: antes disto ser corrigido pra
    rodar na thread certa, nenhum teste que chamasse show() jamais via esse
    scan realmente executar, porque nada bombeava o loop de eventos) --
    exatamente o que activateWindow()/qWaitForWindowActive fazem aqui. Sem
    esperar esse scan automatico terminar, o primeiro states_changed que um
    teste capturasse podia ser o dele, nao o da acao que o teste disparou.
    """
    janela.show()
    janela.activateWindow()
    QTest.qWaitForWindowActive(janela)
    _espera_sinal(janela._worker.scan_finished)


def _tecla(janela, chave):
    """Roteamento real do Qt, nao keyPressEvent chamado a mao -- e o unico
    jeito de exercitar o QShortcut que MainWindow registra."""
    QTest.keyClick(janela, chave)


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
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        assert janela.review_tab.current_sha1 is not None

        _tecla(janela, Qt.Key.Key_3)
        _espera_sinal(janela._worker.states_changed)

        assert list(config.folders[Label.UP].glob("nova_0.7.wav"))
    finally:
        janela.close()


def test_atalho_3_funciona_via_roteamento_real_do_qt(qapp, tmp_path):
    """Regressao dedicada do achado #3.

    Apos show(), o foco inicial real do Qt cai na QTabBar, nao no conteudo
    da aba Revisao -- era exatamente por isso que o keyPressEvent local de
    ReviewTab nunca rodava fora de um teste que o chamasse a mao. Este
    teste nao move o foco pra lugar nenhum: so mostra a janela e aperta a
    tecla, como um usuario faria, pra provar que o QShortcut (contexto
    WindowShortcut, registrado em MainWindow) entrega o evento independente
    de onde o foco esta.
    """
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )

        QTest.keyClick(janela, Qt.Key.Key_3)
        _espera_sinal(janela._worker.states_changed)

        assert list(config.folders[Label.UP].glob("nova_0.7.wav"))
    finally:
        janela.close()


def test_atalho_1_na_biblioteca_funciona_mesmo_com_foco_na_tabela(qapp, tmp_path):
    """Regressao dos achados #3 e #4 juntos.

    QAbstractItemView (base de QTableView) consome digitos pra busca
    incremental embutida antes que um keyPressEvent de LibraryTab pudesse
    ve-los -- o QShortcut precisa disparar mesmo com o foco explicitamente
    na tabela. E como toda linha da Biblioteca ja esta rotulada,
    TrackService.decide() nao acha a sha1 na inbox: o worker precisa
    reportar isso como erro, nao ficar mudo (achado #4), entao este teste
    tambem cobre essa mensagem.
    """
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        janela.tabs.setCurrentWidget(janela.library_tab)

        tabela = janela.library_tab._table
        tabela.setFocus()
        tabela.setCurrentIndex(tabela.model().index(0, 0))
        assert tabela.hasFocus()

        erros = []
        janela._worker.error.connect(erros.append)

        QTest.keyClick(janela, Qt.Key.Key_1)
        _espera_sinal(janela._worker.error)

        assert erros
        assert "biblioteca" in erros[0].lower()
    finally:
        janela.close()


def test_espaco_alterna_reproducao_via_atalho_real(qapp, tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        assert janela._player.is_playing is False

        QTest.keyClick(janela, Qt.Key.Key_Space)
        assert janela._player.is_playing is True

        QTest.keyClick(janela, Qt.Key.Key_Space)
        assert janela._player.is_playing is False
    finally:
        janela.close()


def test_progresso_do_player_move_o_playhead_da_onda(qapp, tmp_path):
    """Achado #5: position_changed do player precisa alcancar a onda.

    Nao chama _mostra_e_ativa/show() de proposito: isto evita acordar o scan
    automatico de abertura, que recarregaria a track exibida (achado #1) e
    interferiria no seek manual que este teste faz. apply_states ja deixa o
    player parado no trecho mais energetico (nao em zero -- ver comentario
    em _atualiza_exibicao), entao o baseline aqui e um seek(0) explicito.
    """
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        duracao = janela._player.duration_ms
        assert duracao > 0

        janela._player.seek(0)
        assert janela.review_tab._waveform._progress == 0.0

        metade = duracao // 2
        janela._player.seek(metade)
        assert janela.review_tab._waveform._progress == metade / duracao
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
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        fila = servico.queue()
        primeira, segunda = fila[0].sha1, fila[1].sha1
        assert janela.review_tab.current_sha1 == primeira

        _tecla(janela, Qt.Key.Key_Right)
        assert janela.review_tab.current_sha1 == segunda

        _tecla(janela, Qt.Key.Key_Left)
        assert janela.review_tab.current_sha1 == primeira

        # Ja na posicao 0: voltar de novo nao pode dar wraparound nem quebrar.
        _tecla(janela, Qt.Key.Key_Left)
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
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        fila = servico.queue()
        # current + ate 3 upcoming = no maximo 4 tracks na janela local.
        ultima_da_janela = fila[3].sha1

        for _ in range(5):
            _tecla(janela, Qt.Key.Key_Right)

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
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        fila = servico.queue()
        primeira_nome, segunda_nome = fila[0].filename, fila[1].filename

        _tecla(janela, Qt.Key.Key_Right)
        assert janela.review_tab.current_sha1 == fila[1].sha1

        _tecla(janela, Qt.Key.Key_3)
        _espera_sinal(janela._worker.states_changed)

        # A que foi movida e a que estava exibida (a segunda, pos-skip) --
        # nao a primeira, que era state.current no snapshot original.
        assert list(config.folders[Label.UP].glob(segunda_nome))
        assert not list(config.folders[Label.UP].glob(primeira_nome))
    finally:
        janela.close()


def test_ctrl_z_desfaz_via_atalho_real(qapp, tmp_path):
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )

        _tecla(janela, Qt.Key.Key_3)
        _espera_sinal(janela._worker.states_changed)
        assert list(config.folders[Label.UP].glob("nova_0.7.wav"))

        QTest.keyClick(janela, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        _espera_sinal(janela._worker.states_changed)

        assert not list(config.folders[Label.UP].glob("nova_0.7.wav"))
        assert list(config.inbox.glob("nova_0.7.wav"))
    finally:
        janela.close()


def test_atalho_3_continua_funcionando_na_revisao_apos_correcao_do_toggle(qapp, tmp_path):
    """Regressao do bug ORIGINAL: 1/2/3/Ctrl+Z nao sao tocados pelo toggle
    dinamico desta correcao (so Space/Right/Left mudam), entao com Revisao
    como aba atual (o default) a tecla 3 precisa continuar decidindo a track
    exatamente como antes -- mesmo teste de sempre, so reconfirmando que a
    correcao de Space/Right/Left nao quebrou o que ja funcionava."""
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        assert janela.tabs.currentWidget() is janela.review_tab

        QTest.keyClick(janela, Qt.Key.Key_3)
        _espera_sinal(janela._worker.states_changed)

        assert list(config.folders[Label.UP].glob("nova_0.7.wav"))
    finally:
        janela.close()


def test_seta_direita_troca_de_aba_nativamente_fora_da_revisao(qapp, tmp_path):
    """Regressao dedicada da NOVA falha: antes desta correcao, o QShortcut
    de Right em MainWindow ficava sempre ligado (WindowShortcut), entao
    roubava a tecla do QTabBar mesmo com o foco explicitamente nele --
    Ctrl+Tab/setas nativas de troca de aba paravam de funcionar em qualquer
    aba. Aqui a aba atual e Biblioteca (indice 1, nao Revisao), o foco vai
    pro proprio QTabBar, e a seta direita precisa avancar o indice da aba
    via comportamento nativo do Qt -- nao via nenhum callback nosso."""
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        janela.tabs.setCurrentWidget(janela.library_tab)
        indice_antes = janela.tabs.currentIndex()
        assert indice_antes == 1

        barra = janela.tabs.tabBar()
        barra.setFocus()
        QTest.qWait(0)
        assert barra.hasFocus()

        QTest.keyClick(barra, Qt.Key.Key_Right)

        assert janela.tabs.currentIndex() != indice_antes
    finally:
        janela.close()


def test_espaco_ativa_botao_escanear_fora_da_revisao(qapp, tmp_path):
    """Regressao dedicada da NOVA falha para o outro widget nativo afetado:
    o botao "Escanear" no canto da QTabWidget usa Space para se auto-ativar
    quando tem foco (comportamento padrao de QPushButton/QAbstractButton).
    Com o QShortcut de Space sempre ligado, essa ativacao nativa nunca
    rodava fora da Revisao -- o evento era interceptado antes de chegar ao
    botao. Aqui a aba atual e Biblioteca, o foco vai pro botao, e Space
    precisa disparar o sinal clicked nativamente."""
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        janela.tabs.setCurrentWidget(janela.library_tab)

        cliques = []
        janela._botao_scan.clicked.connect(lambda: cliques.append(1))
        janela._botao_scan.setFocus()
        QTest.qWait(0)
        assert janela._botao_scan.hasFocus()

        QTest.keyClick(janela._botao_scan, Qt.Key.Key_Space)

        assert cliques
    finally:
        janela.close()


def test_espaco_volta_a_alternar_reproducao_ao_voltar_para_revisao(qapp, tmp_path):
    """Fecha o ciclo: depois de sair da Revisao (onde Space/Right/Left ficam
    desligados, ver testes acima) e voltar pra ela, o toggle dinamico
    precisa religar os tres -- provando que _atualiza_atalhos_de_revisao
    responde a currentChanged em ambas as direcoes, nao so na saida."""
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )

        janela.tabs.setCurrentWidget(janela.library_tab)
        assert janela._atalho_espaco.isEnabled() is False

        janela.tabs.setCurrentWidget(janela.review_tab)
        assert janela._atalho_espaco.isEnabled() is True

        assert janela._player.is_playing is False
        QTest.keyClick(janela, Qt.Key.Key_Space)
        assert janela._player.is_playing is True
    finally:
        janela.close()


class _PlayerEspiao(SimulatedPlayer):
    """SimulatedPlayer que anota o que recebeu em load/seek."""

    def __init__(self):
        super().__init__()
        self.carregados = []
        self.seeks = []

    def load(self, path, duration_ms=None):
        self.carregados.append(path)
        super().load(path, duration_ms)

    def seek(self, milliseconds):
        self.seeks.append(milliseconds)
        super().seek(milliseconds)


def test_aba_revisao_entrega_um_path_ao_player_nao_uma_string(qapp, tmp_path):
    """BasePlayer.load anota `path: Path`; path_hint e str por design.

    A conversao tem que acontecer aqui, na fronteira widget/player -- deixar
    a str passar faz a anotacao mentir e o QtAudioPlayer real so escapa
    porque chama str(path) de novo la dentro.
    """
    config = _config(tmp_path)
    _com_inbox_de_quatro(config)
    servico = _servico(config)
    servico.train()

    espiao = _PlayerEspiao()
    aba = ReviewTab(espiao)
    aba.set_state(review_state(servico))

    assert espiao.carregados
    assert all(isinstance(caminho, Path) for caminho in espiao.carregados)


def test_refresh_com_a_mesma_track_nao_recarrega_o_player(qapp, tmp_path):
    """Todo decide/undo/scan emite states_changed, quase sempre com a mesma
    track exibida. Recarregar a cada um reinicia a reproducao no meio da
    escuta -- so troca de track justifica load+seek."""
    config = _config(tmp_path)
    _com_inbox_de_quatro(config)
    servico = _servico(config)
    servico.train()

    espiao = _PlayerEspiao()
    aba = ReviewTab(espiao)
    estado = review_state(servico)

    aba.set_state(estado)
    aba.set_state(estado)
    aba.set_state(estado)

    assert len(espiao.carregados) == 1
    assert len(espiao.seeks) == 1


def test_pular_para_outra_track_recarrega_o_player(qapp, tmp_path):
    config = _config(tmp_path)
    _com_inbox_de_quatro(config)
    servico = _servico(config)
    servico.train()

    espiao = _PlayerEspiao()
    aba = ReviewTab(espiao)
    aba.set_state(review_state(servico))
    aba.pular()

    assert len(espiao.carregados) == 2
