"""O viewmodel nao importa Qt -- estes testes rodam sem QApplication."""

import numpy as np
import pytest
import soundfile as sf

from trackclassifier.config import Config
from trackclassifier.features import TrackAnalysis
from trackclassifier.labels import Label
from trackclassifier.service import TrackService
from trackclassifier.ui import viewmodel


class ExtratorFalso:
    name = "falso-v1"

    def extract(self, path):
        energia = float(path.stem.split("_")[-1])
        # O vetor precisa ter o mesmo tamanho de FEATURE_NAMES (features.py) --
        # cache.put faz zip(strict=True) entre os dois. 4 era o tamanho antigo;
        # segue o mesmo padrao de tests/test_service.py de repetir a energia.
        return TrackAnalysis(
            vector=np.array([energia] * 44, dtype=np.float64),
            energy_curve=[energia, energia * 2, energia],
            peak_offset_s=1.0,
            bpm=120.0 + energia,
            duration_s=180.0,
        )


def _config(tmp_path) -> Config:
    pastas = {}
    for rotulo, nome in ((Label.UP, "up"), (Label.NEUTRAL, "neutral"), (Label.DOWN, "down")):
        pasta = tmp_path / nome
        pasta.mkdir()
        pastas[rotulo] = pasta
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    dados = tmp_path / "data"
    dados.mkdir()
    return Config(
        folders=pastas, inbox=inbox, data_dir=dados, retrain_every=10, min_examples=2
    )


def _servico(config) -> TrackService:
    for rotulo, base in ((Label.DOWN, 0.1), (Label.NEUTRAL, 0.5), (Label.UP, 0.9)):
        for i in range(3):
            nome = f"r{i}_{base}.wav"
            sf.write(config.folders[rotulo] / nome, np.zeros(100), 22050)
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()
    return servico


def test_format_duration_usa_minutos_e_segundos():
    assert viewmodel.format_duration(0) == "0:00"
    assert viewmodel.format_duration(65) == "1:05"
    assert viewmodel.format_duration(3599) == "59:59"


def test_review_state_vazio_quando_a_inbox_esta_vazia(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    estado = viewmodel.review_state(servico)

    assert estado.current is None
    assert estado.upcoming == ()
    assert estado.remaining == 0


def test_review_state_traz_a_atual_e_ate_tres_proximas(tmp_path):
    config = _config(tmp_path)
    for i in range(5):
        sf.write(config.inbox / f"n{i}_0.{i}.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    estado = viewmodel.review_state(servico)

    assert estado.current is not None
    assert estado.remaining == 5
    assert len(estado.upcoming) == 3
    # A fila do servico ja vem ordenada por confianca crescente; o viewmodel
    # nao reordena -- so fatia.
    fila = servico.queue()
    assert estado.current.sha1 == fila[0].sha1
    assert [linha.sha1 for linha in estado.upcoming] == [item.sha1 for item in fila[1:4]]


def test_track_row_carrega_os_dados_de_apresentacao(tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    linha = viewmodel.review_state(servico).current

    assert linha.filename == "nova_0.7.wav"
    assert linha.bpm == pytest.approx(120.7)
    assert linha.duration_s == pytest.approx(180.0)
    assert linha.energy_curve == (0.7, 1.4, 0.7)
    assert linha.peak_offset_s == pytest.approx(1.0)
    assert linha.predicted in {"-1", "neutra", "+1"}
    assert 0.0 <= linha.confidence <= 1.0
    assert linha.label is None
    assert linha.path_hint.endswith("nova_0.7.wav")


def test_library_state_traz_as_rotuladas_com_o_rotulo(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    estado = viewmodel.library_state(servico)

    assert len(estado.rows) == 9
    assert {linha.label for linha in estado.rows} == {"-1", "neutra", "+1"}
    assert all(linha.predicted is None for linha in estado.rows)


def test_model_state_antes_do_treino_nao_tem_metricas(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    estado = viewmodel.model_state(servico)

    assert estado.accuracy is None
    assert estado.confusion is None
    assert estado.n_examples == 0


def test_model_state_depois_do_treino_traz_as_metricas(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    estado = viewmodel.model_state(servico)

    assert 0.0 <= estado.accuracy <= 1.0
    assert len(estado.confusion) == 3
    assert estado.n_examples == 9


def test_model_state_expoe_as_falhas(tmp_path):
    config = _config(tmp_path)
    (config.inbox / "quebrada_x.wav").write_bytes(b"nao e audio")
    servico = _servico(config)

    estado = viewmodel.model_state(servico)

    assert any(nome == "quebrada_x.wav" for nome, _motivo in estado.failures)


def test_viewmodel_nao_importa_qt():
    import pathlib

    fonte = pathlib.Path(viewmodel.__file__).read_text(encoding="utf-8")
    assert "PySide6" not in fonte
    assert "QtCore" not in fonte
