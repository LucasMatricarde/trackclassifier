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


def test_desfazer_de_arquivo_removido_por_fora_devolve_false(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.5.mp3").write_bytes(b"nova_0.5.mp3")

    servico = _servico(config)
    servico.train()
    sha1 = servico.queue()[0].sha1

    servico.decide(sha1, Label.UP)
    destino = config.folders[Label.UP] / "nova_0.5.mp3"
    assert destino.is_file()

    # Alguem apagou o arquivo rotulado por fora (Finder, outro processo)
    # entre a decisao e o Cmd+Z.
    destino.unlink()

    assert servico.undo_last() is False
    # Nao ha o que restaurar: a track nao pode reaparecer na fila.
    assert servico.queue() == []
    assert [ref.sha1 for ref in servico._inbox] == []
    # A decisao ja foi consumida por essa tentativa -- nao e reprocessavel.
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


def test_reclassificar_move_a_track_para_a_pasta_do_novo_rotulo(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    servico = _servico(config)

    alvo = next(ref for ref in servico._labeled if ref.label is Label.DOWN)
    nome = alvo.path.name

    servico.reclassify(alvo.sha1, Label.UP)

    assert not (config.folders[Label.DOWN] / nome).exists()
    assert (config.folders[Label.UP] / nome).is_file()
    atual = next(ref for ref in servico._labeled if ref.sha1 == alvo.sha1)
    assert atual.label is Label.UP


def test_reclassificar_conta_como_decisao_e_retreina(tmp_path):
    # retrain_every=2 em _config: a segunda reclassificacao tem que treinar.
    config = _config(tmp_path)
    _povoa(config)
    servico = _servico(config)
    servico.train()

    alvos = [ref for ref in servico._labeled if ref.label is Label.DOWN][:2]

    assert servico.reclassify(alvos[0].sha1, Label.NEUTRAL) is False
    assert servico.reclassify(alvos[1].sha1, Label.NEUTRAL) is True


def test_reclassificar_para_o_mesmo_rotulo_e_no_op(tmp_path):
    # Mover para a pasta onde ja esta so criaria "nome (1).mp3" via
    # _destino_livre -- duplicando a track no acervo.
    config = _config(tmp_path)
    _povoa(config)
    servico = _servico(config)

    alvo = next(ref for ref in servico._labeled if ref.label is Label.DOWN)
    nome = alvo.path.name

    assert servico.reclassify(alvo.sha1, Label.DOWN) is False

    assert (config.folders[Label.DOWN] / nome).is_file()
    assert len(list(config.folders[Label.DOWN].glob("*.mp3"))) == 6


def test_reclassificar_sha1_desconhecida_levanta_key_error(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    servico = _servico(config)

    with pytest.raises(KeyError):
        servico.reclassify("nao-existe", Label.UP)


def test_reclassificar_de_track_da_inbox_levanta_key_error(tmp_path):
    # A inbox tem decide(); reclassify e so para o que ja esta rotulado.
    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.5.mp3").write_bytes(b"nova_0.5.mp3")
    servico = _servico(config)
    servico.train()

    sha1 = servico.queue()[0].sha1

    with pytest.raises(KeyError):
        servico.reclassify(sha1, Label.UP)


def test_desfazer_reclassificacao_volta_para_a_biblioteca_nao_para_a_fila(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    servico = _servico(config)
    servico.train()

    alvo = next(ref for ref in servico._labeled if ref.label is Label.DOWN)
    nome = alvo.path.name
    servico.reclassify(alvo.sha1, Label.UP)

    assert servico.undo_last() is True

    assert (config.folders[Label.DOWN] / nome).is_file()
    assert not (config.folders[Label.UP] / nome).exists()
    atual = next(ref for ref in servico._labeled if ref.sha1 == alvo.sha1)
    assert atual.label is Label.DOWN
    # A track nunca esteve na inbox: desfazer nao pode injeta-la na fila.
    assert all(ref.sha1 != alvo.sha1 for ref in servico._inbox)


def test_decidir_reaponta_o_sha1_cache_em_vez_de_reler_no_proximo_scan(tmp_path):
    # A track decidida muda de pasta; a chave do Sha1Cache e o caminho. Sem
    # reapontar, o scan seguinte relia o arquivo inteiro so por causa disso.
    from trackclassifier import library

    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.5.mp3").write_bytes(b"nova_0.5.mp3")

    servico = _servico(config)
    servico.train()
    sha1 = servico.queue()[0].sha1
    servico.decide(sha1, Label.UP)

    leituras = {"n": 0}
    original = library.file_sha1

    def _espiao(caminho):
        leituras["n"] += 1
        return original(caminho)

    library.file_sha1 = _espiao
    try:
        servico.analyze_all()
    finally:
        library.file_sha1 = original

    assert leituras["n"] == 0


def test_cancelar_interrompe_o_scan_sem_marcar_pendentes_como_falha(tmp_path):
    # Cancelar nao e falhar: o que nao foi extraido continua pendente para o
    # proximo scan. Marcar como FailedItem poluiria a aba Modelo com "erros"
    # que o proprio usuario pediu.
    config = _config(tmp_path)
    _povoa(config)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    processadas = []

    cancelado = servico.analyze_all(
        on_progress=lambda feitas, total, nome: processadas.append(nome),
        should_cancel=lambda: len(processadas) >= 3,
    )

    assert cancelado is True
    assert len(processadas) == 3
    assert servico.failures() == []
    assert len(servico.cache) == 3


def test_scan_apos_cancelamento_retoma_de_onde_parou(tmp_path):
    config = _config(tmp_path)
    _povoa(config)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    processadas = []
    servico.analyze_all(
        on_progress=lambda feitas, total, nome: processadas.append(nome),
        should_cancel=lambda: len(processadas) >= 3,
    )

    # O cache ja salvo e preservado: o segundo scan so extrai as 15 restantes.
    restantes = []
    cancelado = servico.analyze_all(
        on_progress=lambda feitas, total, nome: restantes.append(nome)
    )

    assert cancelado is False
    assert len(restantes) == 15
    assert len(servico.cache) == 18


def test_cancelar_no_pool_descarta_os_futuros_ainda_nao_iniciados(tmp_path, monkeypatch):
    # Todos os futuros ja foram submetidos antes do loop, entao parar de
    # submeter nao existe -- o que corta o trabalho restante e o
    # shutdown(cancel_futures=True).
    config = _config(tmp_path)
    _povoa(config)

    shutdowns = []

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
            return _FuturoVivo(fn(extractor, path))

        def shutdown(self, wait=True, cancel_futures=False):
            shutdowns.append(cancel_futures)

    monkeypatch.setattr("trackclassifier.service.ProcessPoolExecutor", _ExecutorFalso)
    monkeypatch.setattr("trackclassifier.service.as_completed", list)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=2)
    processadas = []
    cancelado = servico.analyze_all(
        on_progress=lambda feitas, total, nome: processadas.append(nome),
        should_cancel=lambda: len(processadas) >= 2,
    )

    assert cancelado is True
    assert len(processadas) == 2
    assert servico.failures() == []
    assert shutdowns == [True]


def test_scan_preenche_tags_de_quem_ainda_nao_tem(tmp_path):
    from mutagen.flac import FLAC

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.5.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Glue"]
    arquivo["artist"] = ["Bicep"]
    arquivo.save()

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()

    sha1 = servico._inbox[0].sha1
    registro = servico.presentation_for(sha1)
    assert registro is not None
    assert registro.title == "Glue"
    assert registro.artist == "Bicep"


def test_track_sem_tag_fica_com_registro_vazio_e_nao_e_relida(tmp_path):
    # Gravar um registro vazio e o que impede reler as tags do arquivo a cada
    # scan de uma biblioteca inteira sem metadado.
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()

    sha1 = servico._labeled[0].sha1
    registro = servico.presentation_for(sha1)
    assert registro is not None
    assert registro.title is None

    leituras = {"n": 0}
    import trackclassifier.service as modulo

    original = modulo.read_tags

    def _espiao(caminho):
        leituras["n"] += 1
        return original(caminho)

    modulo.read_tags = _espiao
    try:
        servico.analyze_all()
    finally:
        modulo.read_tags = original

    assert leituras["n"] == 0


def test_falha_ao_ler_tag_nao_entra_em_failures(tmp_path):
    # A track continua classificavel sem metadado; poluir a aba Modelo com
    # "erro" por causa de capa faltando esconderia as falhas que importam.
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)

    import trackclassifier.service as modulo

    original = modulo.read_tags

    def _explode(caminho):
        raise OSError("disco resolveu sumir")

    modulo.read_tags = _explode
    try:
        servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
        servico.analyze_all()
    finally:
        modulo.read_tags = original

    assert servico.failures() == []


def test_cancelar_o_scan_interrompe_tambem_a_passada_de_apresentacao(tmp_path):
    config = _config(tmp_path)
    _povoa(config)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    # Cache de ML ja quente: o unico trabalho restante e a apresentacao.
    servico.analyze_all()
    servico.presentation._linhas.clear()

    lidas = []
    import trackclassifier.service as modulo

    original = modulo.read_tags

    def _conta(caminho):
        lidas.append(caminho)
        return original(caminho)

    modulo.read_tags = _conta
    try:
        cancelado = servico.analyze_all(should_cancel=lambda: len(lidas) >= 2)
    finally:
        modulo.read_tags = original

    assert cancelado is True
    assert len(lidas) == 2


def test_cover_path_for_devolve_o_arquivo_da_capa(tmp_path):
    from mutagen.flac import FLAC, Picture

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.5.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    imagem = Picture()
    imagem.type = 3
    imagem.mime = "image/jpeg"
    imagem.data = b"\xff\xd8\xff\xe0capa"
    arquivo.add_picture(imagem)
    arquivo.save()

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()

    sha1 = servico._inbox[0].sha1
    capa = servico.cover_path_for(sha1)
    assert capa is not None
    assert capa.read_bytes() == b"\xff\xd8\xff\xe0capa"


def _com_audio_real(config, nome="real_0.500.wav"):
    """Grava um .wav DECODIFICAVEL numa pasta rotulada e devolve o caminho.

    `_povoa` grava `b"-10"` em arquivos `.mp3` -- suficiente para o
    ExtratorFalso (que le o vetor do NOME do arquivo, sem tocar no conteudo),
    mas o ffmpeg nao decodifica nada disso. `compute_bands` decodifica de
    verdade, entao todo teste do caminho de SUCESSO precisa de audio real.
    O nome segue o padrao `<algo>_<energia>.wav` porque o ExtratorFalso faz
    `float(stem.split("_")[-1])`.
    """
    from trackclassifier.labels import Label

    sr = 22050
    t = np.linspace(0, 12.0, int(sr * 12), endpoint=False)
    sinal = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    caminho = config.folders[Label.UP] / nome
    sf.write(caminho, sinal, sr)
    return caminho


def test_ensure_peaks_computa_e_grava_na_primeira_chamada(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    alvo = _com_audio_real(config)
    servico = _servico(config)

    ref = next(r for r in servico._labeled if r.path.name == alvo.name)
    caminho = servico.ensure_peaks(ref.sha1, ref.path)

    assert caminho is not None
    assert caminho.is_file()
    assert servico.peaks_for(ref.sha1) == caminho


def test_ensure_peaks_nao_recomputa_o_que_ja_existe(tmp_path):
    import trackclassifier.service as modulo

    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    alvo = _com_audio_real(config)
    servico = _servico(config)
    ref = next(r for r in servico._labeled if r.path.name == alvo.name)
    assert servico.ensure_peaks(ref.sha1, ref.path) is not None

    chamadas = {"n": 0}
    original = modulo.compute_bands

    def _espiao(caminho, buckets=None):
        chamadas["n"] += 1
        return original(caminho)

    modulo.compute_bands = _espiao
    try:
        servico.ensure_peaks(ref.sha1, ref.path)
    finally:
        modulo.compute_bands = original

    assert chamadas["n"] == 0


def test_ensure_peaks_de_arquivo_ilegivel_devolve_none_sem_estourar(tmp_path):
    # _povoa grava bytes que nao sao audio de verdade -- o ffmpeg falha, e
    # isso NAO pode derrubar a janela nem entrar em failures(): a track
    # continua classificavel, so fica sem onda colorida.
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    servico = _servico(config)
    ref = servico._labeled[0]

    assert servico.ensure_peaks(ref.sha1, ref.path) is None
    assert servico.failures() == []


def test_peaks_for_sem_computo_previo_devolve_none(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    servico = _servico(config)

    assert servico.peaks_for(servico._labeled[0].sha1) is None


def test_scan_nao_computa_buckets(tmp_path):
    # Os buckets sao preguicosos por design: o scan ja custa 5-15s por track
    # so com as features, e somar a STFT completa da onda a isso dobraria o
    # tempo de um scan grande para dado que talvez nunca apareca na tela.
    import trackclassifier.service as modulo

    config = _config(tmp_path)
    _povoa(config, n_por_classe=2)

    chamadas = {"n": 0}
    original = modulo.compute_bands

    def _espiao(caminho, buckets=None):
        chamadas["n"] += 1
        return original(caminho)

    modulo.compute_bands = _espiao
    try:
        TrackService(config, extractor=ExtratorFalso(), max_workers=1).analyze_all()
    finally:
        modulo.compute_bands = original

    assert chamadas["n"] == 0
