import numpy as np
import pytest
import soundfile as sf

from trackclassifier.config import Config
from trackclassifier.features import TrackAnalysis
from trackclassifier.labels import Label
from trackclassifier.service import FailedItem, QueueItem, TrackService


class ExtratorFalso:
    """Deriva o vetor do nome do arquivo, para tornar o teste deterministico."""

    name = "falso-v1"

    def __init__(self, falhar_em: set[str] | None = None):
        self.falhar_em = falhar_em or set()

    def extract(self, path):
        if path.name in self.falhar_em:
            raise ValueError(f"falha proposital em {path.name}")
        energia = float(path.stem.split("_")[-1])
        vetor = np.zeros(44, dtype=np.float64)
        vetor[0] = energia
        return TrackAnalysis(
            vector=vetor,
            energy_curve=[energia] * 6,
            peak_offset_s=12.0,
            bpm=128.0,
            duration_s=300.0,
        )


def _config(tmp_path) -> Config:
    pastas = {}
    for chave, rotulo in (("up", Label.UP), ("neutral", Label.NEUTRAL), ("down", Label.DOWN)):
        destino = tmp_path / chave
        destino.mkdir()
        pastas[rotulo] = destino
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    return Config(folders=pastas, inbox=inbox, data_dir=data, retrain_every=2, min_examples=1)


def _povoa(config, n_por_classe=6):
    for rotulo, energia in ((Label.DOWN, 0.0), (Label.NEUTRAL, 0.5), (Label.UP, 1.0)):
        for i in range(n_por_classe):
            valor = energia + i * 0.001
            caminho = config.folders[rotulo] / f"t{i}_{valor:.3f}.mp3"
            caminho.write_bytes(f"{rotulo.value}{i}".encode())


def _servico(config, falhar_em=None) -> TrackService:
    servico = TrackService(config, extractor=ExtratorFalso(falhar_em), max_workers=1)
    servico.analyze_all()
    return servico


def test_treina_e_reporta_metricas(tmp_path):
    config = _config(tmp_path)
    _povoa(config)

    metricas = _servico(config).train()

    assert metricas.n_examples == 18
    assert metricas.accuracy > 0.8


def test_fila_traz_apenas_a_inbox_com_predicao(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.98.mp3").write_bytes(b"nova")

    servico = _servico(config)
    servico.train()
    fila = servico.queue()

    assert len(fila) == 1
    item = fila[0]
    assert isinstance(item, QueueItem)
    assert item.filename == "nova_0.98.mp3"
    assert item.label == Label.UP
    assert item.bpm == 128.0
    assert item.energy_curve == [0.98] * 6
    assert item.peak_offset_s == 12.0


def test_fila_ordena_por_confianca_crescente(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    for nome in ("clara_0.99.mp3", "duvidosa_0.34.mp3", "outra_0.02.mp3"):
        (config.inbox / nome).write_bytes(nome.encode())

    servico = _servico(config)
    servico.train()
    confiancas = [item.confidence for item in servico.queue()]

    assert confiancas == sorted(confiancas)


def test_falhas_de_analise_nao_derrubam_a_fila(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "boa_0.9.mp3").write_bytes(b"a")
    (config.inbox / "ruim_0.5.mp3").write_bytes(b"b")

    servico = TrackService(
        config, extractor=ExtratorFalso(falhar_em={"ruim_0.5.mp3"}), max_workers=1
    )
    servico.analyze_all()
    servico.train()

    assert [item.filename for item in servico.queue()] == ["boa_0.9.mp3"]
    falhas = servico.failures()
    assert len(falhas) == 1
    assert isinstance(falhas[0], FailedItem)
    assert falhas[0].filename == "ruim_0.5.mp3"


def test_decide_move_o_arquivo_para_a_pasta_do_rotulo(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    origem = config.inbox / "nova_0.98.mp3"
    origem.write_bytes(b"nova")

    servico = _servico(config)
    servico.train()
    sha1 = servico.queue()[0].sha1
    servico.decide(sha1, Label.DOWN)

    assert not origem.exists()
    assert (config.folders[Label.DOWN] / "nova_0.98.mp3").is_file()
    assert servico.queue() == []


def test_retreina_ao_atingir_o_limite_de_decisoes(tmp_path):
    config = _config(tmp_path)  # retrain_every = 2
    _povoa(config)
    for nome in ("a_0.9.mp3", "b_0.1.mp3"):
        (config.inbox / nome).write_bytes(nome.encode())

    servico = _servico(config)
    servico.train()
    shas = [item.sha1 for item in servico.queue()]

    assert servico.decide(shas[0], Label.UP) is False
    assert servico.decide(shas[1], Label.DOWN) is True


def test_aprovacao_em_bloco_move_apenas_os_confiantes(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    for nome in ("clara_0.99.mp3", "duvidosa_0.34.mp3"):
        (config.inbox / nome).write_bytes(nome.encode())

    servico = _servico(config)
    servico.train()
    limiar = sorted(item.confidence for item in servico.queue())[-1]

    movidas = servico.bulk_approve(min_confidence=limiar)

    assert movidas == 1
    assert len(servico.queue()) == 1


def test_path_for_devolve_o_caminho_do_arquivo(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.9.mp3").write_bytes(b"nova")

    servico = _servico(config)
    servico.train()
    item = servico.queue()[0]

    assert servico.path_for(item.sha1) == config.inbox / "nova_0.9.mp3"


def test_modelo_corrompido_nao_derruba_a_construcao_do_servico(tmp_path):
    config = _config(tmp_path)
    config.data_dir.mkdir(exist_ok=True)
    (config.data_dir / "model.joblib").write_bytes(b"isto nao e um joblib valido")

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)

    assert servico.model.is_fitted is False


def test_cache_e_salvo_periodicamente_durante_um_scan_grande(tmp_path, monkeypatch):
    config = _config(tmp_path)
    _povoa(config)
    for i in range(15):
        (config.inbox / f"nova{i}_0.{i:02d}.mp3").write_bytes(f"nova{i}".encode())

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)

    chamadas = []
    original_save = servico.cache.save

    def _save_espiao():
        chamadas.append(1)
        original_save()

    monkeypatch.setattr(servico.cache, "save", _save_espiao)

    servico.analyze_all()

    assert len(chamadas) > 1


def test_desfazer_devolve_a_track_para_a_fila(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.5.mp3").write_bytes(b"nova_0.5.mp3")

    servico = _servico(config)
    servico.train()

    antes = [item.sha1 for item in servico.queue()]
    assert len(antes) == 1
    sha1 = antes[0]

    servico.decide(sha1, Label.UP)
    assert servico.queue() == []

    assert servico.undo_last() is True

    depois = [item.sha1 for item in servico.queue()]
    assert depois == antes
    assert (config.inbox / "nova_0.5.mp3").is_file()
    assert not list(config.folders[Label.UP].glob("nova_0.5.mp3"))


def test_desfazer_sem_decisao_anterior_devolve_false(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    servico = _servico(config)

    assert servico.undo_last() is False


def test_desfazer_so_guarda_um_nivel(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    for nome in ("a_0.2.mp3", "b_0.8.mp3"):
        (config.inbox / nome).write_bytes(nome.encode())

    servico = _servico(config)
    servico.train()

    for item in list(servico.queue()):
        servico.decide(item.sha1, Label.UP)

    assert servico.undo_last() is True
    # A segunda chamada nao tem mais o que desfazer: a pilha e de um nivel.
    assert servico.undo_last() is False


def test_falha_inesperada_no_move_mantem_o_item_na_fila(tmp_path, monkeypatch):
    config = _config(tmp_path)
    _povoa(config)
    origem = config.inbox / "nova_0.98.mp3"
    origem.write_bytes(b"nova")

    servico = _servico(config)
    servico.train()
    sha1 = servico.queue()[0].sha1

    def _explode(*_args, **_kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr("trackclassifier.service.move_to_folder", _explode)

    with pytest.raises(OSError):
        servico.decide(sha1, Label.DOWN)

    assert origem.is_file()
    assert [item.sha1 for item in servico.queue()] == [sha1]


def test_arquivo_removido_por_fora_some_da_fila(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    alvo = config.inbox / "nova_0.9.mp3"
    alvo.write_bytes(b"nova")

    servico = _servico(config)
    servico.train()
    sha1 = servico.queue()[0].sha1
    alvo.unlink()

    assert servico.decide(sha1, Label.UP) is False
    assert servico.queue() == []


def test_max_workers_default_e_limitado_mesmo_com_muitos_nucleos(tmp_path, monkeypatch):
    monkeypatch.setattr("trackclassifier.service.os.cpu_count", lambda: 64)
    config = _config(tmp_path)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=None)

    assert servico._max_workers <= 8


def test_um_unico_pendente_nao_aciona_o_pool_mesmo_com_max_workers_alto(tmp_path, monkeypatch):
    config = _config(tmp_path)
    (config.inbox / "unica_0.5.mp3").write_bytes(b"unica")

    class _PoolSentinela:
        def __init__(self, *args, **kwargs):
            raise AssertionError("pool nao deveria ser criado para um unico pendente")

    # Se o gate `total > 1` fosse removido (ou quebrado de qualquer forma),
    # analyze_all tentaria instanciar ProcessPoolExecutor aqui, e o
    # AssertionError do sentinela faria este teste falhar com esse erro
    # especifico -- prova positiva de que o gate importa. A versao anterior
    # deste teste alegava provar o mesmo assumindo que ExtratorFalso nao
    # sobreviveria a um spawn real (por suposta perda do sys.path/pythonpath
    # no processo filho no macOS); essa premissa e falsa -- `spawn` copia
    # sys.path para o filho via multiprocessing.spawn.get_preparation_data(),
    # e combinado com `pythonpath = ["src", "."]` em pyproject.toml e
    # tests/__init__.py, ExtratorFalso despicklaria normalmente. Ou seja, o
    # teste antigo passaria mesmo que o gate `total > 1` fosse apagado --
    # so provava `len(cache) == 1`, que e verdade em qualquer um dos dois
    # caminhos (pool ou sequencial).
    monkeypatch.setattr("trackclassifier.service.ProcessPoolExecutor", _PoolSentinela)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=4)
    servico.analyze_all()

    assert len(servico.cache) == 1


def _escreve_wav_curto(caminho, duracao_s=15.0, sr=22050, seed=0):
    gerador = np.random.default_rng(seed)
    sinal = (0.2 * gerador.standard_normal(int(sr * duracao_s))).astype(np.float32)
    sf.write(caminho, sinal, sr)
    return caminho


def test_pool_de_verdade_processa_multiplos_arquivos_em_paralelo(tmp_path):
    from trackclassifier.features import HandcraftedExtractor

    config = _config(tmp_path)
    for rotulo, seed in ((Label.DOWN, 1), (Label.NEUTRAL, 2), (Label.UP, 3)):
        _escreve_wav_curto(config.folders[rotulo] / f"r_{rotulo.value}.wav", seed=seed)
    _escreve_wav_curto(config.inbox / "nova1.wav", seed=10)
    _escreve_wav_curto(config.inbox / "nova2.wav", seed=11)

    servico = TrackService(config, extractor=HandcraftedExtractor(), max_workers=2)
    servico.analyze_all()

    assert len(servico.cache) == 5
    assert servico.failures() == []
    assert len(servico._labeled) == 3
    assert len(servico._inbox) == 2


def test_worker_morto_vira_falha_contida_e_nao_derruba_o_scan(tmp_path, monkeypatch):
    config = _config(tmp_path)
    mortos = {"morto0_0.0.mp3", "morto1_0.1.mp3"}
    vivos = {"vivo0_0.5.mp3", "vivo1_0.6.mp3"}
    for nome in mortos | vivos:
        (config.inbox / nome).write_bytes(nome.encode())

    class _FuturoMorto:
        def result(self):
            raise RuntimeError("processo worker morreu")

    class _FuturoVivo:
        def __init__(self, valor):
            self._valor = valor

        def result(self):
            return self._valor

    class _ExecutorFalso:
        def __init__(self, max_workers=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def submit(self, fn, extractor, path):
            if path.name in mortos:
                return _FuturoMorto()
            # Worker "sobrevivente": executa a extracao de verdade aqui mesmo,
            # no processo de teste, sem passar por spawn algum -- o ponto nao
            # e testar multiprocessing de verdade (isso e o outro teste), e
            # sim provar que o loop de as_completed em service.py continua
            # coletando e processando os demais futuros depois que um deles
            # estoura, em vez de abortar o lote inteiro na primeira morte.
            return _FuturoVivo(fn(extractor, path))

    # Troca o pool de verdade por um cujos futuros ora estouram na coleta do
    # resultado (worker morto: segfault/OOM/BrokenProcessPool), ora devolvem
    # um resultado valido, simulando um lote misto onde só alguns workers
    # morrem. Como nenhum processo real e criado, ExtratorFalso segue seguro
    # aqui.
    monkeypatch.setattr("trackclassifier.service.ProcessPoolExecutor", _ExecutorFalso)
    monkeypatch.setattr("trackclassifier.service.as_completed", list)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=2)
    servico.analyze_all()

    falhas = {falha.filename: falha for falha in servico.failures()}
    assert set(falhas) == mortos
    assert all("worker falhou" in falha.reason for falha in falhas.values())

    # As tracks cujo worker sobreviveu nao podem ser arrastadas pela falha
    # das outras: precisam ter sido extraidas, cacheadas e postas na fila.
    assert len(servico.cache) == len(vivos)
    assert {ref.path.name for ref in servico._inbox} == vivos


def test_falha_na_construcao_do_pool_vira_falhas_contidas_e_nao_derruba_o_scan(
    tmp_path, monkeypatch
):
    config = _config(tmp_path)
    pendentes = {"a_0.1.mp3", "b_0.2.mp3", "c_0.3.mp3"}
    for nome in pendentes:
        (config.inbox / nome).write_bytes(nome.encode())

    class _ExecutorQuebrado:
        def __init__(self, max_workers=None):
            pass

        def __enter__(self):
            # Simula OSError na construcao/entrada do pool (exaustao de fd ou
            # semaforo do SO) -- acontece antes de qualquer future existir,
            # entao o try/except por-future em torno de futuro.result() nunca
            # teria chance de capturar isto.
            raise OSError("nao foi possivel alocar recursos para o pool")

        def __exit__(self, *exc):
            return False

    # Nao precisa nem definir submit(): __enter__ ja estoura antes de chegar
    # la, provando que a falha e contida mesmo quando o pool morre antes do
    # primeiro submit.
    monkeypatch.setattr("trackclassifier.service.ProcessPoolExecutor", _ExecutorQuebrado)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=2)
    servico.analyze_all()  # nao pode propagar a excecao do pool

    falhas = {falha.filename: falha for falha in servico.failures()}
    assert set(falhas) == pendentes
    assert all("pool de execucao falhou" in falha.reason for falha in falhas.values())
    assert len(servico.cache) == 0
    assert servico._inbox == []


def test_save_periodico_soma_as_duas_fases_do_scan(tmp_path, monkeypatch):
    config = _config(tmp_path)
    for rotulo, energia in ((Label.DOWN, 0.0), (Label.NEUTRAL, 0.5), (Label.UP, 1.0)):
        for i in range(2):
            (config.folders[rotulo] / f"r{i}_{energia}.mp3").write_bytes(
                f"{rotulo.value}{i}".encode()
            )
    for i in range(6):
        (config.inbox / f"n{i}_0.{i:02d}.mp3").write_bytes(f"n{i}".encode())

    # 6 rotuladas + 6 na inbox = 12 pendentes no total. Nenhuma das duas fases
    # sozinha cruza o limiar de 10 do save periodico -- so o contador
    # unificado sobre o lote combinado deve disparar o save.
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)

    chamadas = []
    original_save = servico.cache.save

    def _save_espiao():
        chamadas.append(1)
        original_save()

    monkeypatch.setattr(servico.cache, "save", _save_espiao)

    servico.analyze_all()

    assert len(chamadas) > 1
