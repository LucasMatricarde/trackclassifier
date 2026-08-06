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
    worker.scan_finished.connect(lambda: fim.append(True))

    worker.scan()

    assert fim == [True]


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
