"""O worker e testado chamando os slots direto, sem thread.

Mover para uma QThread e responsabilidade de ServiceThread; a logica dos
slots nao depende disso e testa-la sem thread evita flakiness de timing.
"""

import numpy as np
import soundfile as sf

from tests.test_viewmodel import _config, _servico
from trackclassifier.ui.viewmodel import LibraryState, ModelState, ReviewState
from trackclassifier.ui.worker import ServiceWorker


def test_refresh_emite_os_tres_estados(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    worker = ServiceWorker(servico)
    recebidos = []
    worker.states_changed.connect(lambda r, b, m: recebidos.append((r, b, m)))

    worker.refresh()

    assert len(recebidos) == 1
    revisao, biblioteca, modelo = recebidos[0]
    assert isinstance(revisao, ReviewState)
    assert isinstance(biblioteca, LibraryState)
    assert isinstance(modelo, ModelState)
    assert modelo.n_examples == 9


def test_decide_move_o_arquivo_e_reemite_os_estados(qapp, tmp_path):
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    worker = ServiceWorker(servico)
    recebidos = []
    worker.states_changed.connect(lambda r, b, m: recebidos.append(r))

    sha1 = servico.queue()[0].sha1
    worker.decide(sha1, "+1")

    assert recebidos[-1].current is None
    assert list(config.folders[Label.UP].glob("nova_0.7.wav"))


def test_undo_devolve_a_track_e_reemite(qapp, tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    worker = ServiceWorker(servico)
    sha1 = servico.queue()[0].sha1
    worker.decide(sha1, "+1")

    recebidos = []
    worker.states_changed.connect(lambda r, b, m: recebidos.append(r))
    worker.undo()

    assert recebidos[-1].current is not None
    assert recebidos[-1].current.sha1 == sha1


def test_scan_emite_progresso_e_fim(qapp, tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)

    worker = ServiceWorker(servico)
    progresso = []
    fim = []
    worker.scan_progress.connect(lambda feitas, total, nome: progresso.append(nome))
    worker.scan_finished.connect(fim.append)

    worker.scan()

    assert fim == [False]  # terminou sozinho, nao cancelado


def test_train_sem_todas_as_classes_emite_error_em_vez_de_estourar(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    # Deixa so uma classe rotulada: train() deve levantar NotEnoughClassesError
    # la dentro, e o worker precisa converter isso em sinal de erro.
    servico._labeled = [ref for ref in servico._labeled if ref.label is not None][:1]

    worker = ServiceWorker(servico)
    erros = []
    worker.error.connect(erros.append)

    worker.train()

    assert len(erros) == 1
    assert "rotulos" in erros[0].lower() or "classes" in erros[0].lower()


def test_refresh_com_cache_inconsistente_emite_error_em_vez_de_estourar(qapp, tmp_path):
    """library_state chama service._analysis, que tem `assert analise is not None`.

    Uma track rotulada sem entrada no cache (parquet truncado, extractor.name
    bumpado sem rescan) vira AssertionError dentro de um slot rodando na
    QThread do worker, onde nao ha nada para captura-la. Como todo o resto da
    UI degrada por mensagem, refresh nao pode ser a excecao.
    """
    config = _config(tmp_path)
    servico = _servico(config)

    def _sem_analise(ref):
        raise AssertionError("cache sem a analise desta track")

    servico._analysis = _sem_analise

    worker = ServiceWorker(servico)
    erros = []
    estados = []
    worker.error.connect(erros.append)
    worker.states_changed.connect(lambda r, b, m: estados.append(r))

    worker.refresh()

    assert len(erros) == 1
    assert estados == []


def test_decide_na_biblioteca_reclassifica_em_vez_de_recusar(qapp, tmp_path):
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    servico = _servico(config)

    alvo = next(ref for ref in servico._labeled if ref.label is Label.DOWN)
    nome = alvo.path.name

    worker = ServiceWorker(servico)
    erros = []
    worker.error.connect(erros.append)

    worker.decide(alvo.sha1, "+1")

    assert erros == []
    assert (config.folders[Label.UP] / nome).is_file()
    assert not (config.folders[Label.DOWN] / nome).exists()


def test_decide_de_sha1_fora_da_fila_e_da_biblioteca_emite_error(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    worker = ServiceWorker(servico)
    erros = []
    worker.error.connect(erros.append)

    worker.decide("sha1-que-nunca-existiu", "+1")

    assert len(erros) == 1
    assert "nao esta mais" in erros[0]


def test_request_cancel_durante_o_scan_termina_como_cancelado(qapp, tmp_path):
    """request_cancel e chamado direto, sem passar pela fila de eventos.

    Nao da para ser um @Slot: durante o scan o loop de eventos da thread do
    worker esta parado dentro de analyze_all, entao um slot enfileirado so
    rodaria depois do scan terminar -- justamente o que se quer interromper.
    Aqui o cancelamento sai do proprio sinal de progresso, que e o mesmo
    caminho de chamada direta que o clique no botao usa.
    """
    from tests.test_viewmodel import ExtratorFalso
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    for i in range(4):
        sinal = np.full(100, (i + 1) / 10.0, dtype=np.float32)
        sf.write(config.inbox / f"n{i}_0.{i}.wav", sinal, 22050)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    worker = ServiceWorker(servico)

    fim = []
    progresso = []
    worker.scan_finished.connect(fim.append)
    worker.scan_progress.connect(lambda feitas, total, nome: progresso.append(nome))
    worker.scan_progress.connect(lambda *_: worker.request_cancel())

    worker.scan()

    assert fim == [True]
    assert len(progresso) == 1  # parou na proxima checagem, nao no fim do lote
    assert servico.failures() == []


def test_scan_seguinte_rearma_o_flag_de_cancelamento(qapp, tmp_path):
    # scan() faz clear() no inicio: um cancelamento nao pode envenenar todos
    # os scans seguintes.
    from tests.test_viewmodel import ExtratorFalso
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    for i in range(3):
        sinal = np.full(100, (i + 1) / 10.0, dtype=np.float32)
        sf.write(config.inbox / f"n{i}_0.{i}.wav", sinal, 22050)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    worker = ServiceWorker(servico)
    worker.request_cancel()

    fim = []
    worker.scan_finished.connect(fim.append)

    worker.scan()

    # O primeiro scan e o que prova: o flag estava setado antes dele, e o
    # clear() no inicio de scan() e a unica coisa entre isso e um scan que
    # aborta na primeira checagem.
    assert fim == [False]


def test_compute_peaks_computa_e_emite_peaks_ready_sem_refresh(qapp, tmp_path):
    import numpy as np
    import soundfile as sf

    from tests.test_viewmodel import ExtratorFalso
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    # Audio de verdade: compute_bands roda ffmpeg + librosa, entao um arquivo
    # de bytes falsos falharia por decode, nao por logica.
    t = np.linspace(0, 12.0, int(22050 * 12), endpoint=False)
    sinal = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(config.inbox / "real_0.5.wav", sinal, 22050)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()
    sha1 = servico._inbox[0].sha1
    caminho = servico._inbox[0].path

    worker = ServiceWorker(servico)
    estados = []
    worker.states_changed.connect(lambda r, b, m: estados.append(r))
    prontos = []
    worker.peaks_ready.connect(lambda sha1, caminho: prontos.append((sha1, caminho)))

    worker.compute_peaks(sha1, str(caminho))

    assert servico.peaks_for(sha1) is not None
    # Sem refresh completo: um computo em segundo plano nao pode resetar a
    # selecao da tabela da Biblioteca nem o playhead da onda da Revisao a
    # cada linha que aparece no scroll.
    assert estados == []
    assert len(prontos) == 1
    assert prontos[0][0] == sha1
    assert prontos[0][1] == str(servico.peaks_for(sha1))


def test_compute_peaks_de_arquivo_ruim_nao_emite_error(qapp, tmp_path):
    # Ficar sem onda colorida nao e um erro que mereca a status bar: a track
    # continua classificavel e o fallback mono ja aparece.
    config = _config(tmp_path)
    servico = _servico(config)
    ref = servico._labeled[0]

    worker = ServiceWorker(servico)
    erros = []
    worker.error.connect(erros.append)

    worker.compute_peaks(ref.sha1, str(ref.path))

    assert erros == []


def test_compute_peaks_de_sha1_ja_computada_nao_recomputa(qapp, tmp_path):
    import numpy as np

    config = _config(tmp_path)
    servico = _servico(config)
    ref = servico._labeled[0]
    servico.peaks.put(ref.sha1, np.zeros((8, 3), dtype=np.float16))

    import trackclassifier.service as modulo

    chamadas = {"n": 0}
    original = modulo.compute_bands

    def _espiao(caminho, buckets=None):
        chamadas["n"] += 1
        return original(caminho)

    modulo.compute_bands = _espiao
    try:
        ServiceWorker(servico).compute_peaks(ref.sha1, str(ref.path))
    finally:
        modulo.compute_bands = original

    assert chamadas["n"] == 0


def test_reload_config_troca_o_servico_e_reemite_estado(qapp, tmp_path):
    """Salvar a configuracao precisa recriar o TrackService: mudou pasta ou
    data_dir, mudaram o cache e o modelo. Recriar DENTRO da thread do worker
    e o que mantem a regra de uma so thread dona do servico."""
    from tests.test_viewmodel import ExtratorFalso, _config
    from trackclassifier.service import TrackService
    from trackclassifier.ui.worker import ServiceWorker

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    primeiro = _config(tmp_path / "a")
    segundo = _config(tmp_path / "b")
    worker = ServiceWorker(TrackService(primeiro, extractor=ExtratorFalso(), max_workers=1))

    recebidos = []
    worker.states_changed.connect(lambda *estados: recebidos.append(estados))

    worker.reload_config(segundo)

    assert recebidos != []
    assert worker._service.config.inbox == segundo.inbox


def test_reload_config_com_falha_na_construcao_preserva_o_servico_antigo(
    qapp, tmp_path, monkeypatch
):
    """TrackService(config) e resiliente por design a pasta ausente, cache
    corrompido ou model.joblib ilegivel -- cada camada absorve o proprio erro
    (ver CLAUDE.md, "erros sao contidos por design"). Nao existe um Config
    real e simples que reproduza uma falha de construcao; o jeito de exercitar
    o ramo except de reload_config sem reescrever essa resiliencia e forcar a
    falha no ponto exato que o slot chama, igual ao que
    test_compute_peaks_de_sha1_ja_computada_nao_recomputa ja faz com
    compute_bands. O que importa provar: o servico ANTIGO sobrevive intacto,
    porque self._service so e reatribuido depois que TrackService(config) ja
    teria retornado com sucesso."""
    from tests.test_viewmodel import ExtratorFalso, _config
    from trackclassifier.service import TrackService
    from trackclassifier.ui.worker import ServiceWorker

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    original = _config(tmp_path / "a")
    quebrada = _config(tmp_path / "b")
    servico_original = TrackService(original, extractor=ExtratorFalso(), max_workers=1)
    worker = ServiceWorker(servico_original)

    def _construtor_que_quebra(*args, **kwargs):
        raise RuntimeError("config quebrada de proposito")

    monkeypatch.setattr("trackclassifier.ui.worker.TrackService", _construtor_que_quebra)

    erros = []
    worker.error.connect(erros.append)
    recebidos = []
    worker.states_changed.connect(lambda *estados: recebidos.append(estados))

    worker.reload_config(quebrada)

    assert len(erros) == 1
    assert "config quebrada de proposito" in erros[0]
    # Nem refresh() roda: o return dentro do except impede states_changed de
    # sair com um estado que nao corresponde a nenhum servico coerente.
    assert recebidos == []
    assert worker._service is servico_original
