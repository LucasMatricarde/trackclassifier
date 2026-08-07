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
    # n_examples passou a sair do balanco, e nao de metrics_: sem treino
    # nao ha metrica, mas ha exemplos rotulados, e a aba Modelo mostra
    # quantos. Era 0 aqui enquanto o unico consumidor era a linha de
    # texto que so aparecia depois do treino.
    assert estado.n_examples == 9


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

    assert any(nome == "quebrada_x.wav" for nome, _motivo, _categoria in estado.failures)


def test_model_state_leva_a_categoria_da_falha(tmp_path):
    config = _config(tmp_path)
    (config.inbox / "quebrada_x.wav").write_bytes(b"nao e audio")
    servico = _servico(config)

    estado = viewmodel.model_state(servico)

    (falha,) = [linha for linha in estado.failures if linha[0] == "quebrada_x.wav"]
    assert len(falha) == 3
    assert falha[2] == servico.failures()[0].category


def test_model_state_nao_treinado_traz_balanco_real(tmp_path):
    config = _config(tmp_path)
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()

    estado = viewmodel.model_state(servico)

    # Metricas ausentes e balanco presente: nao treinado e o estado normal
    # do inicio, nao um erro, e o balanco e o que diz o que rotular agora.
    assert estado.accuracy is None
    assert estado.class_counts == servico.class_counts()
    assert estado.n_examples == sum(estado.class_counts)


def test_model_state_bloqueia_treino_com_motivo_quando_falta_classe(tmp_path):
    config = _config(tmp_path)
    sf.write(config.folders[Label.NEUTRAL] / "so_neutra_0.5.wav", np.zeros(100), 22050)
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()

    estado = viewmodel.model_state(servico)

    assert estado.train_blocked_reason is not None
    # O motivo nomeia as classes que faltam com o vocabulario do dominio,
    # nunca as chaves da config ("up"/"down").
    assert "-1" in estado.train_blocked_reason
    assert "+1" in estado.train_blocked_reason
    assert "up" not in estado.train_blocked_reason


def test_model_state_com_as_tres_classes_libera_o_treino(tmp_path):
    estado = viewmodel.model_state(_servico(_config(tmp_path)))

    assert estado.train_blocked_reason is None


def test_model_state_traz_o_contador_de_retreino(tmp_path):
    servico = _servico(_config(tmp_path))

    estado = viewmodel.model_state(servico)

    assert estado.decisions_since_train == servico.decisions_since_train
    assert estado.retrain_every == servico.config.retrain_every


def test_model_state_traz_o_detalhe_tecnico(tmp_path):
    servico = _servico(_config(tmp_path))
    servico.train()

    estado = viewmodel.model_state(servico)

    assert estado.extractor_name == servico.extractor.name
    assert estado.alpha == servico.model.alpha_
    assert estado.thresholds == servico.model.thresholds_


def test_model_state_sem_treino_nao_expoe_alpha_default(tmp_path):
    config = _config(tmp_path)
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()

    estado = viewmodel.model_state(servico)

    # alpha_ e thresholds_ tem valor default no TrackModel desde o
    # __init__. Expo-los como se fossem resultado de treino seria mentira.
    assert estado.alpha is None
    assert estado.thresholds is None
    assert estado.extractor_name == servico.extractor.name


def test_track_row_traz_as_tags_do_servico(tmp_path):
    from mutagen.flac import FLAC

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "r9_0.9.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Glue"]
    arquivo["artist"] = ["Bicep"]
    arquivo["genre"] = ["Techno"]
    arquivo.save()

    servico = _servico(config)

    linha = next(
        linha for linha in viewmodel.library_state(servico).rows if linha.filename.endswith(".flac")
    )
    assert linha.title == "Glue"
    assert linha.artist == "Bicep"
    assert linha.genre == "Techno"


def test_display_title_cai_para_o_nome_do_arquivo_sem_tag(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    linha = viewmodel.library_state(servico).rows[0]

    assert linha.title is None
    assert linha.display_title == linha.filename


def test_display_title_usa_a_tag_quando_existe(tmp_path):
    from trackclassifier.ui.viewmodel import TrackRow

    linha = TrackRow(
        sha1="abc",
        filename="01 - faixa.flac",
        label=None,
        predicted=None,
        score=None,
        confidence=None,
        bpm=128.0,
        duration_s=300.0,
        energy_curve=(),
        peak_offset_s=0.0,
        path_hint="/tmp/01 - faixa.flac",
        title="Glue",
        artist="Bicep",
        genre="Techno",
        cover_path=None,
    )

    assert linha.display_title == "Glue"


def test_row_da_fila_tambem_traz_as_tags(tmp_path):
    from mutagen.flac import FLAC

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.7.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Opal"]
    arquivo.save()

    servico = _servico(config)
    servico.train()

    estado = viewmodel.review_state(servico)
    assert estado.current is not None
    assert estado.current.title == "Opal"


def test_track_row_traz_o_caminho_dos_buckets_quando_existem(tmp_path):
    import numpy as np

    config = _config(tmp_path)
    servico = _servico(config)

    ref = servico._labeled[0]
    servico.peaks.put(ref.sha1, np.zeros((8, 3), dtype=np.float16))

    linha = next(
        linha for linha in viewmodel.library_state(servico).rows if linha.sha1 == ref.sha1
    )
    assert linha.peaks_path is not None
    assert linha.peaks_path.endswith(f"{ref.sha1}.npy")


def test_track_row_sem_buckets_tem_peaks_path_none(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    linha = viewmodel.library_state(servico).rows[0]

    assert linha.peaks_path is None


def test_row_da_fila_tambem_traz_o_caminho_dos_buckets(tmp_path):
    import numpy as np

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    sha1 = servico.queue()[0].sha1
    servico.peaks.put(sha1, np.zeros((8, 3), dtype=np.float16))

    estado = viewmodel.review_state(servico)
    assert estado.current is not None
    assert estado.current.peaks_path is not None


def test_track_row_traz_a_key_do_servico(tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.keys import Key, Mode

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "r9_0.9.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["initialkey"] = ["8A"]
    arquivo.save()

    servico = _servico(config)

    linha = next(
        linha
        for linha in viewmodel.library_state(servico).rows
        if linha.filename.endswith(".flac")
    )
    assert linha.key == Key(9, Mode.MINOR)


def test_track_row_sem_key_fica_none(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    assert viewmodel.library_state(servico).rows[0].key is None


def test_row_da_fila_tambem_traz_a_key(tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.keys import Key, Mode

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.7.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["initialkey"] = ["5A"]
    arquivo.save()

    servico = _servico(config)
    servico.train()

    estado = viewmodel.review_state(servico)
    assert estado.current is not None
    assert estado.current.key == Key(0, Mode.MINOR)


def test_viewmodel_nao_importa_qt():
    import pathlib

    fonte = pathlib.Path(viewmodel.__file__).read_text(encoding="utf-8")
    assert "PySide6" not in fonte
    assert "QtCore" not in fonte
