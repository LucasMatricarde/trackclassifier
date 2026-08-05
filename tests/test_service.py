import numpy as np
import pytest

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

    servico = TrackService(config, extractor=ExtratorFalso(falhar_em={"ruim_0.5.mp3"}), max_workers=1)
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


def test_um_unico_pendente_nao_aciona_o_pool_mesmo_com_max_workers_alto(tmp_path):
    config = _config(tmp_path)
    (config.inbox / "unica_0.5.mp3").write_bytes(b"unica")

    # ExtratorFalso nao e importavel num processo filho (spawn). Se o pool
    # fosse usado aqui, esta chamada falharia com erro de pickle/import.
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=4)
    servico.analyze_all()

    assert len(servico.cache) == 1


def test_save_periodico_soma_as_duas_fases_do_scan(tmp_path, monkeypatch):
    config = _config(tmp_path)
    for rotulo in (Label.DOWN, Label.NEUTRAL, Label.UP):
        for i in range(2):
            (config.folders[rotulo] / f"r{i}_{rotulo.value}.mp3").write_bytes(
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
