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
from PySide6.QtCore import QEventLoop, QObject, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMenu, QStatusBar

from tests.test_viewmodel import _config, _servico
from trackclassifier.ui.review_tab import ReviewTab
from trackclassifier.ui.update_worker import VerificadorDeAtualizacao
from trackclassifier.ui.viewmodel import library_state, model_state, review_state
from trackclassifier.ui.widgets.player import SimulatedPlayer
from trackclassifier.ui.widgets.track_model import Column, TrackTableModel
from trackclassifier.ui.window import MainWindow


def _verificador_falso(**kwargs) -> VerificadorDeAtualizacao:
    """Nunca bate na rede: `buscar` fixo em "nao ha release", para a
    checagem automatica de boot (deve_checar() com updates.json fresco)
    resolver na hora em vez de fazer um GET real em api.github.com.
    """
    kwargs.setdefault("buscar", lambda: None)
    return VerificadorDeAtualizacao(**kwargs)


class _ReinicioDeSilencio(QObject):
    """QObject de verdade so pra dar afinidade de thread ao reset do timer.

    `sinal` (ex.: worker.states_changed) e emitido na thread do WORKER; o
    QTimer `quieto` foi criado na thread da GUI (quem chama _espera_sinal).
    Conectar `sinal` direto a uma lambda solta nao basta: uma lambda nao e
    QObject, entao o Qt nao tem afinidade de thread pra comparar e a conexao
    vira DIRETA -- roda na thread de quem EMITE, nao na dona do QTimer.
    `QTimer.start()` fora da propria thread falha em silencio (Qt so avisa
    no stderr e ignora a chamada), entao o timer de silencio nunca reiniciava
    e _espera_sinal sempre caia no timeout absoluto inteiro. Um metodo de um
    QObject de verdade, criado aqui na thread da GUI, da ao Qt o que falta
    pra detectar a troca de thread na conexao e enfileirar a chamada -- so
    assim o reset roda na thread certa.
    """

    def __init__(self, quieto: QTimer, quiet_ms: int) -> None:
        super().__init__()
        self._quieto = quieto
        self._quiet_ms = quiet_ms

    def reinicia(self, *_args) -> None:
        self._quieto.start(self._quiet_ms)


def _espera_sinal(sinal, timeout_ms=2000, quiet_ms=150):
    """Bombeia o loop de eventos ate o sinal assentar ou estourar o timeout.

    O worker mora numa QThread propria (ver window.MainWindow); a conexao
    entre o sinal da aba e o slot do worker e QueuedConnection porque emissor
    e receptor vivem em threads diferentes. Sem isto, o assert rodaria antes
    do worker ter tido a chance de processar o evento -- falha deterministica,
    nao flakiness, porque nada aqui cede o controle para a outra thread.

    Nao basta parar no PRIMEIRO states_changed (Task 7): quando a track
    exibida na Revisao ainda nao tem buckets, set_state reemite
    peaks_requested a cada vez que roda -- inclusive o apply_states manual
    que estes testes chamam antes de disparar a tecla. Isso enfileira um
    compute_peaks no worker ANTES do decide/undo real, e o primeiro
    states_changed que chega pode ser o do computo dos buckets, nao o da
    acao que o teste quer observar. Por isso o loop reinicia um temporizador
    de folga a cada emissao e so retorna depois de `quiet_ms` sem nada
    novo -- o que garante a fila do worker (peaks + acao real) drenada,
    nao so o primeiro evento a chegar. O reset roda via `_ReinicioDeSilencio`
    (ver a classe) e nao por lambda direta -- ver o motivo la.
    """
    loop = QEventLoop()
    quieto = QTimer()
    quieto.setSingleShot(True)
    quieto.timeout.connect(loop.quit)
    reinicio = _ReinicioDeSilencio(quieto, quiet_ms)
    conexao = sinal.connect(reinicio.reinicia)
    limite = QTimer()
    limite.setSingleShot(True)
    limite.timeout.connect(loop.quit)
    limite.start(timeout_ms)
    # Nao arma `quieto` aqui: se o sinal nunca disparar, quem tem que decidir
    # que acabou e o `limite` (o teto de verdade), nao um quiet_ms que seria
    # curto demais pra cobrir o tempo ATE o primeiro evento chegar (o worker
    # pode estar ocupado com um compute_peaks de verdade -- ffmpeg + librosa
    # -- antes mesmo do primeiro states_changed sair). `quieto` so entra em
    # jogo a partir da primeira emissao, via reinicio.reinicia.
    loop.exec()
    sinal.disconnect(conexao)


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


def test_table_model_expoe_as_colunas_da_rodada_3a(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    modelo = TrackTableModel(list(library_state(servico).rows))

    assert modelo.rowCount() == 9
    assert modelo.columnCount() == len(Column)
    cabecalhos = [
        modelo.headerData(coluna, Qt.Orientation.Horizontal) for coluna in Column
    ]
    # A ordem e a do mockup 3a. Artista foi absorvido pela coluna de
    # titulo e Confianca saiu: na Biblioteca a track ja esta classificada,
    # e a confianca do modelo sobre uma decisao humana ja tomada nao muda
    # nenhuma acao (na Revisao ela continua, explicando a fila).
    # Caixa alta por font.case.label, aplicada em Column.header.
    assert cabecalhos == [
        "CAPA",
        "TITULO · ARTISTA",
        "ONDA",
        "GENERO",
        "BPM",
        "KEY",
        "CLASSE",
        "DUR",
    ]


def test_coluna_key_ordena_pela_roda_de_camelot_nao_pelo_alfabeto(qapp, tmp_path):
    # 10A vem depois de 2A na roda; alfabeticamente viria antes. Ordenar pela
    # string quebraria a leitura harmonica, que e o proposito da coluna.
    from dataclasses import replace

    from trackclassifier.keys import Key, Mode

    config = _config(tmp_path)
    servico = _servico(config)
    linhas = list(library_state(servico).rows)

    linhas[0] = replace(linhas[0], key=Key(11, Mode.MINOR))  # 10A
    linhas[1] = replace(linhas[1], key=Key(3, Mode.MINOR))   # 2A
    linhas[2] = replace(linhas[2], key=None)

    modelo = TrackTableModel(linhas)
    modelo.sort(Column.KEY, Qt.SortOrder.AscendingOrder)

    numeros = [
        modelo.row_at(i).key.camelot_number if modelo.row_at(i).key else None
        for i in range(modelo.rowCount())
    ]
    assert numeros[0] == 2
    assert numeros[1] == 10
    assert numeros[-1] is None  # sem key sempre no fim


def test_modelo_formata_a_key_na_notacao_corrente(qapp, tmp_path):
    from dataclasses import replace

    from trackclassifier.keys import Key, KeyNotation, Mode

    config = _config(tmp_path)
    servico = _servico(config)
    linhas = list(library_state(servico).rows)
    linhas[0] = replace(linhas[0], key=Key(9, Mode.MINOR))

    modelo = TrackTableModel(linhas)

    assert modelo.data(modelo.index(0, Column.KEY)) == "8A"
    modelo.set_notation(KeyNotation.CLASSIC)
    assert modelo.data(modelo.index(0, Column.KEY)) == "Am"


def test_coluna_key_sem_key_mostra_travessao(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    modelo = TrackTableModel(list(library_state(servico).rows))

    assert modelo.data(modelo.index(0, Column.KEY)) == "—"


def test_coluna_titulo_mostra_a_tag_e_cai_para_o_nome_do_arquivo(qapp, tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.labels import Label

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "r9_0.9.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Glue"]
    arquivo.save()

    servico = _servico(config)
    modelo = TrackTableModel(list(library_state(servico).rows))

    titulos = [
        modelo.data(modelo.index(i, Column.TITULO)) for i in range(modelo.rowCount())
    ]
    assert "Glue" in titulos
    # As nove sem tag continuam identificaveis pelo nome do arquivo.
    assert "r0_0.1.wav" in titulos


def test_coluna_sem_tag_mostra_travessao_em_vez_de_vazio(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    modelo = TrackTableModel(list(library_state(servico).rows))

    assert modelo.data(modelo.index(0, Column.GENERO)) == "—"
    # O artista perdeu a coluna e virou desenho do TitleDelegate; o
    # travessao dele e testado em test_delegates.py.


# Nao ha mais teste de ordenacao por artista: a rodada 3a fundiu artista
# na coluna de titulo, e sem cabecalho proprio nao ha o que clicar para
# disparar a ordem. Buscar por artista continua funcionando -- ver
# test_delegates.py::test_busca_encontra_por_titulo_e_por_artista.


def test_table_model_ordena_por_bpm_com_none_no_fim(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    modelo = TrackTableModel(list(library_state(servico).rows))
    modelo.sort(Column.BPM, Qt.SortOrder.AscendingOrder)

    bpms = [modelo.row_at(i).bpm for i in range(modelo.rowCount())]
    assert bpms == sorted(bpms)


def test_a_coluna_de_classificacao_tem_texto_para_leitor_de_tela(qapp, tmp_path):
    """DisplayRole, e nao AccessibleTextRole: data() e chamado ~88 mil vezes
    por rolagem da biblioteca real e o proprio codigo documenta que trabalho
    descartado ali custou 9% do tempo de paint. O Qt cai no DisplayRole
    sozinho para o texto acessivel da celula, e este ramo ja existia.

    Visualmente nada muda: _pinta_fundo zera opcao.text e o
    ClassificationDelegate desenha os segmentos por conta propria.
    """
    config = _config(tmp_path)
    servico = _servico(config)
    modelo = TrackTableModel(list(library_state(servico).rows))

    textos = {
        modelo.data(modelo.index(i, Column.CLASSIFICACAO), Qt.ItemDataRole.DisplayRole)
        for i in range(modelo.rowCount())
    }

    assert textos <= {"-1", "neutra", "+1", None}
    assert textos & {"-1", "neutra", "+1"}

    # A asercao acima so exige que EXISTA uma linha com texto -- passaria
    # igual se uma regressao devolvesse None pra quase todas. Aperta aqui:
    # toda linha com rotulo DECIDIDO (row_at(i).label is not None) tem que
    # ter o mesmo texto no DisplayRole daquela celula.
    for i in range(modelo.rowCount()):
        linha = modelo.row_at(i)
        if linha is not None and linha.label is not None:
            assert (
                modelo.data(modelo.index(i, Column.CLASSIFICACAO), Qt.ItemDataRole.DisplayRole)
                == linha.label
            )


def test_a_coluna_de_capa_continua_sem_texto(qapp, tmp_path):
    """Uma capa nao carrega informacao que valha anunciar."""
    config = _config(tmp_path)
    servico = _servico(config)
    modelo = TrackTableModel(list(library_state(servico).rows))

    assert (
        modelo.data(modelo.index(0, Column.CAPA), Qt.ItemDataRole.DisplayRole) is None
    )


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


def test_hint_bar_troca_de_texto_com_a_aba(qapp, tmp_path):
    """A faixa de atalhos e chrome da janela, nao da aba -- HintBar troca
    de conteudo com MainWindow.tabs.currentChanged, e some nas abas que
    nao tem atalho nenhum (Modelo, Configuracao)."""
    config = _config(tmp_path)
    servico = _servico(config)

    janela = MainWindow(servico)
    try:
        # A janela nao e mostrada neste teste (nao precisa de show() para
        # trocar de aba) -- por isso isHidden(), nao isVisible(): sem show(),
        # isVisible() e sempre False (a cadeia de ancestrais nao esta na
        # tela), mas isHidden() reflete so o setVisible() que HintBar chamou.
        assert janela.tabs.currentWidget() is janela.review_tab
        assert janela._hint_bar.isHidden() is False
        texto_revisao = [r.text() for r in janela._hint_bar._rotulos]

        janela.tabs.setCurrentWidget(janela.library_tab)

        texto_biblioteca = [r.text() for r in janela._hint_bar._rotulos]
        assert texto_biblioteca != texto_revisao
        assert any("RECLASSIFICAR" in item for item in texto_biblioteca)

        janela.tabs.setCurrentWidget(janela.model_tab)

        assert janela._hint_bar.isHidden() is True
    finally:
        janela.close()


def test_status_strip_mostra_o_resumo_apos_apply_states(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )

        texto = janela._status._texto.text()
        n_analisadas = len(library_state(servico).rows)
        n_pendentes = review_state(servico).remaining

        assert str(n_analisadas) in texto
        assert str(n_pendentes) in texto
        assert str(n_analisadas + n_pendentes) in texto
    finally:
        janela.close()


def test_aviso_de_qtmultimedia_tem_timeout(qapp, tmp_path, monkeypatch):
    """Achado do code review: sem timeout, o aviso de boot fica preso na
    status bar pra sempre e esconde a StatusStrip -- ela e widget normal
    (addWidget), e showMessage() sem prazo nunca "some sozinho revelando o
    resumo de novo" como o docstring de StatusStrip promete. Quem nao tem o
    extra `audio` instalado nunca veria o progresso do scan que
    _inicia_scan() dispara logo depois deste aviso."""
    import trackclassifier.ui.window as window_mod

    monkeypatch.setattr(window_mod, "MULTIMEDIA_AVAILABLE", False)

    chamadas = []
    original = QStatusBar.showMessage

    def espiao(self, texto, timeout=0):
        chamadas.append((texto, timeout))
        return original(self, texto, timeout)

    monkeypatch.setattr(QStatusBar, "showMessage", espiao)

    config = _config(tmp_path)
    servico = _servico(config)

    janela = MainWindow(servico)
    try:
        avisos = [c for c in chamadas if "QtMultimedia" in c[0]]
        assert avisos, "esperava um showMessage() com 'QtMultimedia' no texto"
        assert avisos[0][1] > 0, "timeout 0 e 'sem prazo' no Qt -- fica preso pra sempre"
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


def test_atalho_de_rotulo_na_biblioteca_reclassifica_mesmo_com_foco_na_tabela(
    qapp, tmp_path
):
    """Regressao do achado #3, agora exercitando a reclassificacao de verdade.

    QAbstractItemView (base de QTableView) consome digitos pra busca
    incremental embutida antes que um keyPressEvent de LibraryTab pudesse
    ve-los -- o QShortcut precisa disparar mesmo com o foco explicitamente na
    tabela. O 3 aqui rotula como +1 a linha selecionada, que ja tem rotulo:
    e o caminho de reclassificacao, nao o de decide().
    """
    from trackclassifier.labels import Label

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

        # A linha 0 da tabela, e nao a primeira de _labeled: a Biblioteca
        # ordena por Titulo, entao as duas ordens nao coincidem.
        alvo = janela.library_tab._model.row_at(0)
        assert alvo.label != Label.UP.value  # senao o 3 seria no-op

        erros = []
        janela._worker.error.connect(erros.append)

        QTest.keyClick(janela, Qt.Key.Key_3)
        _espera_sinal(janela._worker.states_changed)

        assert erros == []
        movida = next(ref for ref in servico._labeled if ref.sha1 == alvo.sha1)
        assert movida.label is Label.UP
        assert movida.path.parent == config.folders[Label.UP]
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
    """A orientacao para escanear virou um botao no EmptyState (Task 8), nao
    mais so texto: o teste original conferia a string devolvida por
    empty_text(), mas essa string parou de mencionar "escanear" quando o
    verbo migrou para o rotulo do botao. Ver ReviewTab.acionar_empty_state
    para quem exercita o clique de verdade."""
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        assert janela.review_tab.current_sha1 is None
        assert janela.review_tab._vazio.tem_botao()
        assert "escanear" in janela.review_tab._vazio._botao.text().lower()
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


def test_ctrl_z_desfaz_uma_reclassificacao_na_biblioteca(qapp, tmp_path):
    """O desfazer e estado do SERVICO (_ultima_decisao), nao da tela.

    undo_last ja sabe devolver uma reclassificacao para a biblioteca com o
    rotulo antigo em vez de joga-la na fila de revisao -- so a janela e que
    checava a aba atual antes de chamar o worker.
    """
    import threading

    from trackclassifier.labels import Label

    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    # Grava em que thread undo_last de fato roda -- e o unico jeito de
    # provar que o Ctrl+Z despacha pra thread do ServiceWorker em vez de
    # chamar TrackService direto na thread da GUI (o bug que a revisao
    # final encontrou: o teste antigo so conferia o resultado do arquivo,
    # que fica identico nos dois casos).
    threads_de_undo: list[threading.Thread] = []
    undo_original = servico.undo_last

    def _undo_gravando_thread(*args, **kwargs):
        threads_de_undo.append(threading.current_thread())
        return undo_original(*args, **kwargs)

    servico.undo_last = _undo_gravando_thread

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        janela.tabs.setCurrentWidget(janela.library_tab)

        tabela = janela.library_tab._table
        tabela.setCurrentIndex(tabela.model().index(0, Column.TITULO))
        linha = tabela.model().row_at(0)
        origem = next(
            rotulo
            for rotulo, pasta in config.folders.items()
            if list(pasta.glob(linha.filename))
        )
        destino = Label.UP if origem is not Label.UP else Label.DOWN

        teclas = {Label.DOWN: Qt.Key.Key_1, Label.NEUTRAL: Qt.Key.Key_2, Label.UP: Qt.Key.Key_3}
        _tecla(janela, teclas[destino])
        _espera_sinal(janela._worker.states_changed)
        assert list(config.folders[destino].glob(linha.filename))

        QTest.keyClick(janela, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        _espera_sinal(janela._worker.states_changed)

        assert list(config.folders[origem].glob(linha.filename))
        assert not list(config.folders[destino].glob(linha.filename))

        # O ponto central deste teste: undo_last rodou fora da MainThread.
        # Uma chamada direta (self._worker.undo() sem QTimer.singleShot)
        # rodaria sincronamente aqui na thread da GUI e este assert cairia.
        assert threads_de_undo, "undo_last nao foi chamado"
        assert threads_de_undo[-1] is not threading.main_thread()
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


def test_botao_de_scan_alterna_entre_escanear_e_cancelar(qapp, tmp_path):
    """Um botao so para as duas acoes.

    E o que impede iniciar um segundo scan por cima do primeiro: enquanto ha
    um em andamento, nao existe controle na tela que dispare outro.
    """
    from trackclassifier.ui.window import TEXTO_CANCELAR, TEXTO_ESCANEAR

    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)  # espera o scan automatico de abertura acabar
        assert janela._botao_scan.text() == TEXTO_ESCANEAR
        assert janela._escaneando is False

        janela._inicia_scan()
        assert janela._botao_scan.text() == TEXTO_CANCELAR
        assert janela._escaneando is True

        janela._scan_concluido(cancelado=True)
        assert janela._botao_scan.text() == TEXTO_ESCANEAR
        assert janela._botao_scan.isEnabled()
        assert "cancelado" in janela.statusBar().currentMessage().lower()
    finally:
        janela.close()


def test_clique_no_botao_durante_o_scan_pede_cancelamento(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela._inicia_scan()

        pedidos = []
        janela._worker.request_cancel = lambda: pedidos.append(True)

        janela._botao_scan.click()

        assert pedidos == [True]
        # Desabilitado ate o scan reportar o fim: sem isso, um segundo clique
        # cairia no ramo de iniciar scan, ja que _escaneando so vira False la.
        assert not janela._botao_scan.isEnabled()
    finally:
        janela.close()


def test_empty_state_scan_requested_nao_cancela_scan_em_andamento(qapp, tmp_path):
    """Achado Important da revisao final.

    O auto-scan de abertura (fim de MainWindow.__init__) comeca ANTES de
    qualquer aba receber estado -- nesse intervalo review_tab/library_tab
    ainda estao no empty state, mostrando um botao "Escanear" enquanto ha,
    de fato, um scan rodando. Antes desta correcao, scan_requested das duas
    abas estava ligado ao MESMO handler do botao do canto
    (_clique_no_botao_scan), que e um toggle: clicar "Escanear" nesse
    momento cancelava o scan que acabou de comecar -- o oposto do que o
    rotulo do botao promete.
    """
    from trackclassifier.ui.window import TEXTO_CANCELAR

    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)  # espera o scan automatico de abertura acabar
        janela._inicia_scan()
        assert janela._escaneando is True

        pedidos_de_cancelamento = []
        janela._worker.request_cancel = lambda: pedidos_de_cancelamento.append(True)

        janela.review_tab.scan_requested.emit()
        janela.library_tab.scan_requested.emit()

        assert pedidos_de_cancelamento == []
        assert janela._escaneando is True
        assert janela._botao_scan.text() == TEXTO_CANCELAR
    finally:
        janela.close()


def test_revisao_mostra_titulo_artista_e_genero(qapp, tmp_path):
    from mutagen.flac import FLAC

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.7.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Glue"]
    arquivo["artist"] = ["Bicep"]
    arquivo["genre"] = ["Techno"]
    arquivo.save()

    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    assert aba._titulo.text() == "Glue"
    assert "Bicep" in aba._subtitulo.text()
    assert "Techno" in aba._subtitulo.text()


def test_revisao_sem_tag_usa_o_nome_do_arquivo_e_esconde_o_subtitulo(qapp, tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)

    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    assert aba._titulo.text() == "nova_0.7.wav"
    # Sem artista nem genero, uma linha vazia so consome espaco vertical.
    assert aba._subtitulo.text() == ""


def test_revisao_mostra_so_o_artista_quando_nao_ha_genero(qapp, tmp_path):
    from mutagen.flac import FLAC

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.7.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["artist"] = ["Bicep"]
    arquivo.save()

    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    # Sem separador solto: " · " sobrando parece dado faltando por bug.
    assert aba._subtitulo.text() == "Bicep"


def test_revisao_limpa_o_cabecalho_na_fila_vazia(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    assert aba._subtitulo.text() == ""
    assert aba._capa.pixmap().isNull()


def test_proximas_mostra_o_titulo_da_tag_nao_o_nome_do_arquivo(qapp, tmp_path):
    """As proximas tem que ser consistentes com o titulo principal: ambos
    mostram display_title (tag com fallback pro nome do arquivo), nunca o
    filename cru quando ha tag.

    Desde a Fase 3 as proximas sao a linha da Biblioteca em densidade
    compacta, e nao um QLabel de texto corrido -- entao a checagem passou a
    ser sobre o DisplayRole da coluna de titulo."""
    from mutagen.flac import FLAC

    config = _config(tmp_path)
    _com_inbox_de_quatro(config)
    for caminho in config.inbox.glob("*.wav"):
        # sf.write so escreve wav aqui; troca por flac pra poder gravar tag.
        flac_caminho = caminho.with_suffix(".flac")
        dados, taxa = sf.read(caminho)
        sf.write(flac_caminho, dados.astype(np.float32), int(taxa), format="FLAC")
        caminho.unlink()
        arquivo = FLAC(flac_caminho)
        arquivo["title"] = [f"Titulo de {flac_caminho.stem}"]
        arquivo.save()

    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    estado = review_state(servico)
    assert estado.upcoming, "fixture precisa de pelo menos uma proxima track"
    from trackclassifier.ui.widgets.track_model import Column

    modelo = aba._proximas.model()
    titulos = [
        modelo.data(modelo.index(i, Column.TITULO)) for i in range(modelo.rowCount())
    ]
    assert len(titulos) == len(estado.upcoming)
    for linha in estado.upcoming:
        assert linha.title in titulos
        assert linha.filename not in titulos


def test_waveform_view_desenha_rgb_quando_ha_buckets(qapp, tmp_path):
    """Testa o WaveformView direto, nao pela ReviewTab.

    Renderizar atraves da aba faria o tamanho do widget depender do layout
    ja ter rodado, e um widget de 0x0 produziria duas imagens vazias iguais
    -- o teste passaria sem provar nada. Com resize() direto no widget, o
    tamanho e deterministico.
    """
    from dataclasses import replace

    import numpy as np

    from trackclassifier.ui.widgets.waveform_view import WaveformView

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    estado = review_state(servico)
    assert estado.current is not None
    assert estado.current.energy_curve  # senao o fallback mono nao desenha nada

    caminho = tmp_path / "picos.npy"
    bandas = np.zeros((64, 3), dtype=np.float16)
    bandas[:, 2] = 1.0  # agudo puro: azul, bem longe do accent do mono
    np.save(caminho, bandas)

    view = WaveformView()
    view.resize(200, 40)

    view.set_row(estado.current)
    mono = view.grab().toImage()

    view.set_row(replace(estado.current, peaks_path=str(caminho)))
    rgb = view.grab().toImage()

    assert rgb != mono


def test_waveform_view_cai_no_mono_com_npy_corrompido(qapp, tmp_path):
    from dataclasses import replace

    import numpy as np

    from trackclassifier.ui.widgets.waveform_view import WaveformView

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    estado = review_state(servico)
    ruim = tmp_path / "ruim.npy"
    ruim.write_bytes(b"isto nao e um npy")

    view = WaveformView()
    view.resize(200, 40)

    view.set_row(estado.current)
    mono = view.grab().toImage()

    view.set_row(replace(estado.current, peaks_path=str(ruim)))
    apos_corrompido = view.grab().toImage()

    # Identicas: o .npy invalido some e sobra exatamente o render mono.
    assert apos_corrompido == mono


def test_revisao_pede_computo_dos_buckets_da_track_atual(qapp, tmp_path):
    import numpy as np

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    pedidos = []
    aba.peaks_requested.connect(lambda sha1, caminho: pedidos.append(sha1))

    estado = review_state(servico)
    aba.set_state(estado)

    assert pedidos == [estado.current.sha1]


def test_revisao_nao_reenfileira_computo_apos_falha_persistente(qapp, tmp_path):
    # Regressao do achado Critical da revisao final: sem dedup, uma track
    # cujo computo de peaks falha (ou cujo refresh e disparado por qualquer
    # outro motivo antes do computo terminar) faria a aba pedir de novo a
    # cada set_state, travando a thread do servico num loop sem fim.
    import numpy as np

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    pedidos = []
    aba.peaks_requested.connect(lambda sha1, caminho: pedidos.append(sha1))

    estado = review_state(servico)
    # Tres set_state seguidos com a MESMA track ainda sem peaks_path --
    # simula tres refreshes enquanto o computo nao termina (ou falha).
    aba.set_state(estado)
    aba.set_state(estado)
    aba.set_state(estado)

    assert pedidos == [estado.current.sha1]


def test_peaks_prontos_na_biblioteca_nao_reseta_a_selecao(qapp, tmp_path):
    # Regressao do achado Important da revisao final: antes da correcao,
    # compute_peaks terminava chamando refresh(), que reconstruia os tres
    # estados e resetava o QTableView inteiro -- perdendo a selecao a cada
    # computo de peaks em segundo plano (disparado por scroll, podendo
    # acontecer dezenas de vezes numa sessao).
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
        tabela.setCurrentIndex(tabela.model().index(2, 0))
        alvo = janela.library_tab._model.row_at(2)
        assert tabela.currentIndex().row() == 2

        janela.library_tab.peaks_prontos(alvo.sha1, "/fake/caminho.npy")

        assert tabela.currentIndex().row() == 2
    finally:
        janela.close()


def test_alternador_de_notacao_muda_biblioteca_e_revisao_juntas(qapp, tmp_path):
    # A notacao e preferencia global: ver "8A" na tabela e "Am" no cabecalho
    # ao mesmo tempo seria dois modelos mentais para o mesmo dado.
    from mutagen.flac import FLAC

    from trackclassifier.labels import Label

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "r9_0.9.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["initialkey"] = ["8A"]
    arquivo.save()

    sf.write(config.inbox / "nova_0.7.flac", np.zeros(22050, dtype="float32"), 22050,
             format="FLAC")
    entrada = FLAC(config.inbox / "nova_0.7.flac")
    entrada["initialkey"] = ["8A"]
    entrada.save()

    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )

        modelo = janela.library_tab._model
        indice_flac = next(
            i for i in range(modelo.rowCount())
            if modelo.row_at(i).filename.endswith(".flac")
        )
        assert modelo.data(modelo.index(indice_flac, Column.KEY)) == "8A"
        assert janela.review_tab._key_chip.text() == "8A"

        janela.library_tab._notacao.setCurrentText("Classica")

        assert modelo.data(modelo.index(indice_flac, Column.KEY)) == "Am"
        assert janela.review_tab._key_chip.text() == "Am"
    finally:
        janela.close()


def test_revisao_sem_key_mostra_travessao_no_chip(qapp, tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    assert aba._key_chip.text() == "—"


def test_trocar_notacao_nao_perde_a_selecao_da_biblioteca(qapp, tmp_path):
    # set_notation usa dataChanged, nao reset de modelo: e a mesma licao do
    # computo de peaks na fase 3.
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
        tabela.setCurrentIndex(tabela.model().index(2, 0))
        assert tabela.currentIndex().row() == 2

        janela.library_tab._notacao.setCurrentText("Classica")

        assert tabela.currentIndex().row() == 2
    finally:
        janela.close()


def test_janela_sem_config_path_nao_mostra_a_aba_configuracao(qapp, tmp_path):
    config = _config(tmp_path)
    janela = MainWindow(_servico(config))
    try:
        titulos = [janela.tabs.tabText(i) for i in range(janela.tabs.count())]
        assert "Configuracao" not in titulos
    finally:
        janela.close()


def test_janela_com_config_path_mostra_a_aba_configuracao(qapp, tmp_path):
    from trackclassifier.config import save_config

    config = _config(tmp_path)
    caminho = tmp_path / "config.toml"
    save_config(caminho, config)

    janela = MainWindow(_servico(config), config_path=caminho)
    try:
        titulos = [janela.tabs.tabText(i) for i in range(janela.tabs.count())]
        assert titulos[-1] == "Configuracao"
    finally:
        janela.close()


def test_reload_config_via_salvar_atravessa_a_fila_do_worker(qapp, tmp_path):
    """Fecha o buraco do teste direto em test_worker.py: la, worker.reload_config
    e chamado a mao, na mesma thread do teste -- nada prova que o caminho real
    (SettingsTab.salvar() -> config_saved -> MainWindow._aplica_config ->
    QTimer.singleShot(0, worker, ...)) de fato cruza para a thread do worker.
    Uma regressao que trocasse o singleShot por uma chamada direta passaria no
    teste do worker sem esbarrar em nada, e travaria (ou corromperia) a
    unica dona do TrackService sem que nenhum teste acusasse."""
    from trackclassifier.config import SettingsDraft, save_config
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    servico = _servico(config)
    caminho = tmp_path / "config.toml"
    save_config(caminho, config)

    (tmp_path / "outra").mkdir()
    segunda = _config(tmp_path / "outra")

    janela = MainWindow(servico, config_path=caminho)
    try:
        _mostra_e_ativa(janela)
        assert janela.settings_tab is not None

        rascunho = SettingsDraft(
            inbox=str(segunda.inbox),
            up=str(segunda.folders[Label.UP]),
            neutral=str(segunda.folders[Label.NEUTRAL]),
            down=str(segunda.folders[Label.DOWN]),
            data_dir=str(segunda.data_dir),
            retrain_every=segunda.retrain_every,
            min_examples=segunda.min_examples,
            create_under_root=False,
            root="",
        )
        janela.settings_tab.form.set_draft(rascunho)

        janela.settings_tab.salvar()
        _espera_sinal(janela._worker.states_changed)

        # O novo servico so tem a segunda config se o reload realmente rodou
        # na thread do worker: a inbox mudou de pasta, e a biblioteca (que
        # tinha 9 tracks na primeira config) esvaziou porque a segunda config
        # aponta para pastas vazias.
        assert janela._worker._service.config.inbox == segunda.inbox
        assert library_state(janela._worker._service).rows == ()
    finally:
        janela.close()


def test_revisao_vazia_esconde_o_bloco_da_track(qapp, tmp_path):
    """O stretch=1 da onda sobre um bloco vazio e o que produzia o vazio de
    altura inteira nas capturas."""
    config = _config(tmp_path)
    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(_servico(config)))

    assert aba.bloco_visivel() is False


def test_revisao_com_track_mostra_o_bloco(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico.analyze_all()
    # queue() so devolve algo com o modelo treinado (is_fitted) -- sem isto
    # review_state().current fica None e o teste nao provaria nada.
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    assert aba.bloco_visivel() is True


def test_empty_state_da_revisao_pede_scan(qapp, tmp_path):
    config = _config(tmp_path)
    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(_servico(config)))

    pedidos = []
    aba.scan_requested.connect(lambda: pedidos.append(True))
    aba.acionar_empty_state()

    assert pedidos == [True]


def test_capa_ausente_nao_reserva_espaco(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico.analyze_all()
    # Sem isto review_state().current fica None (queue() exige is_fitted) e o
    # teste passaria vazio -- pelo ramo de fila vazia, nao pelo de capa
    # ausente que ele existe para cobrir.
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    # ExtratorFalso nao produz capa, entao o QLabel de 44x44 ficaria
    # reservando o buraco.
    assert aba.capa_visivel() is False


def _release_falso(versao="0.9.0", recomputa=frozenset()):
    from trackclassifier.updates import Release

    return Release(
        version=versao,
        url_zip="https://z/app.zip",
        url_sha256="https://z/s",
        notas="",
        recomputa=recomputa,
    )


def test_sem_bundle_nao_ha_menu_de_atualizacao(qapp, tmp_path):
    """Em desenvolvimento o recurso nao existe: nao ha .app para trocar."""
    config = _config(tmp_path)
    servico = _servico(config)

    janela = MainWindow(servico)
    try:
        assert janela.acao_atualizar is None
        assert janela.menuBar().actions() == []
    finally:
        janela.close()


def test_com_bundle_o_menu_de_atualizacao_existe(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    janela = MainWindow(
        servico,
        bundle=tmp_path / "TrackClassifier.app",
        verificador=_verificador_falso(),
    )
    try:
        assert janela.acao_atualizar is not None
        assert "atualiza" in janela.acao_atualizar.text().lower()
        # A regressao real (achado #1 da revisao final): uma QAction solta
        # adicionada via menuBar().addAction() nunca chega em [NSApp
        # mainMenu] no cocoa nativo -- so QActions que vivem DENTRO de um
        # QMenu sao encaminhadas ao menu nativo. `is not None` sozinho
        # passava tanto com o bug quanto com o conserto; isto prova que a
        # acao esta de fato alcancavel atraves de um menu.
        menus = janela.menuBar().findChildren(QMenu)
        assert any(janela.acao_atualizar in menu.actions() for menu in menus)
    finally:
        janela.close()


def test_release_disponivel_mostra_a_faixa_com_a_versao(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    janela = MainWindow(
        servico,
        bundle=tmp_path / "TrackClassifier.app",
        verificador=_verificador_falso(),
    )
    try:
        janela._atualizacao_disponivel(_release_falso("0.9.0"))

        assert not janela.banner.isHidden()
        assert "0.9.0" in janela.banner.texto()
    finally:
        janela.close()


def test_dispensar_esconde_a_faixa_e_grava_a_versao(qapp, tmp_path):
    from trackclassifier.update_state import EstadoDeAtualizacao

    config = _config(tmp_path)
    servico = _servico(config)
    estado = EstadoDeAtualizacao(tmp_path / "updates.json")

    janela = MainWindow(
        servico,
        bundle=tmp_path / "TrackClassifier.app",
        atualizacoes=estado,
        verificador=_verificador_falso(),
    )
    try:
        janela._atualizacao_disponivel(_release_falso("0.9.0"))
        janela.banner.dispensar()

        assert janela.banner.isHidden()
        assert estado.esta_dispensada("0.9.0")
    finally:
        janela.close()


def test_versao_ja_dispensada_nao_mostra_a_faixa(qapp, tmp_path):
    from trackclassifier.update_state import EstadoDeAtualizacao

    config = _config(tmp_path)
    servico = _servico(config)
    estado = EstadoDeAtualizacao(tmp_path / "updates.json")
    estado.dispensa("0.9.0")

    janela = MainWindow(
        servico,
        bundle=tmp_path / "TrackClassifier.app",
        atualizacoes=estado,
        verificador=_verificador_falso(),
    )
    try:
        janela._atualizacao_disponivel(_release_falso("0.9.0"))

        assert janela.banner.isHidden()
    finally:
        janela.close()


def test_menu_forca_a_checagem_mesmo_com_a_versao_dispensada(qapp, tmp_path):
    """Pedido explicito ignora tanto o intervalo quanto o dispensado."""
    from trackclassifier.update_state import EstadoDeAtualizacao

    config = _config(tmp_path)
    servico = _servico(config)
    estado = EstadoDeAtualizacao(tmp_path / "updates.json")
    estado.dispensa("0.9.0")

    janela = MainWindow(
        servico,
        bundle=tmp_path / "TrackClassifier.app",
        atualizacoes=estado,
        verificador=_verificador_falso(),
    )
    try:
        janela.acao_atualizar.trigger()
        janela._atualizacao_disponivel(_release_falso("0.9.0"))

        assert not janela.banner.isHidden()
    finally:
        janela.close()


def test_falha_de_checagem_nao_mostra_faixa_nem_derruba_a_janela(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    janela = MainWindow(
        servico,
        bundle=tmp_path / "TrackClassifier.app",
        verificador=_verificador_falso(),
    )
    try:
        janela._atualizacao_falhou("Nao foi possivel verificar atualizacoes.")

        assert janela.banner.isHidden()
        assert janela.isEnabled()
    finally:
        janela.close()
