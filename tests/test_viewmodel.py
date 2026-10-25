"""O viewmodel nao importa toolkit de UI -- estes testes rodam com pytest puro."""

import numpy as np
import pytest
import soundfile as sf

from trackclassifier import viewmodel
from trackclassifier.config import Config
from trackclassifier.features import TrackAnalysis
from trackclassifier.labels import LABEL_ORDER, Label
from trackclassifier.service import TrackService

#: Ordem estavel dos rotulos (-1, neutra, +1), a mesma de class_counts.
_LABELS_EM_ORDEM = tuple(rotulo.value for rotulo in LABEL_ORDER)


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
    return Config.from_folders(
        folders=pastas, inbox=inbox, data_dir=dados, retrain_every=10, min_examples=2
    )


def _servico(config, trash=None) -> TrackService:
    for rotulo, base in ((Label.DOWN, 0.1), (Label.NEUTRAL, 0.5), (Label.UP, 0.9)):
        for i in range(3):
            nome = f"r{i}_{base}.wav"
            sf.write(config.folders[rotulo] / nome, np.zeros(100), 22050)
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1, trash=trash)
    servico.analyze_all()
    return servico


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


def test_library_state_traz_contagem_por_classe_e_o_total(tmp_path):
    """As contagens dos chips de classe: tres posicoes, ordem de LABEL_ORDER.

    Uma track a mais em +1 de proposito: com o acervo simetrico (3/3/3),
    trocar a ordem de LABEL_ORDER ou ler a posicao errada do tuple passaria
    despercebido.
    """
    config = _config(tmp_path)
    sf.write(config.folders[Label.UP] / "extra_0.9.wav", np.zeros(100), 22050)
    servico = _servico(config)

    estado = viewmodel.library_state(servico)

    assert estado.total == len(estado.rows) == 10
    assert dict(zip(_LABELS_EM_ORDEM, estado.class_counts, strict=True)) == {
        "-1": 3,
        "neutra": 3,
        "+1": 4,
    }


def test_library_state_vazio_mantem_as_tres_posicoes_em_zero(tmp_path):
    """(0, 0, 0) e nao (): chip em zero e informacao ("falta esta classe"),
    chip ausente e layout pulando de largura quando o acervo enche."""
    config = _config(tmp_path)
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)

    estado = viewmodel.library_state(servico)

    assert estado.rows == ()
    assert estado.total == 0
    assert estado.class_counts == (0, 0, 0)


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
    arquivo["album"] = ["Glue (Deluxe)"]
    arquivo.save()

    servico = _servico(config)

    linha = next(
        linha for linha in viewmodel.library_state(servico).rows if linha.filename.endswith(".flac")
    )
    assert linha.title == "Glue"
    assert linha.artist == "Bicep"
    assert linha.genre == "Techno"
    # Album entrou na rodada de fidelidade da Biblioteca: e o quarto campo da
    # busca ("titulo, artista, album ou arquivo"). O PresentationCache ja o
    # lia desde a v0.2 -- faltava o TrackRow carregar.
    assert linha.album == "Glue (Deluxe)"


def test_display_title_cai_para_o_nome_do_arquivo_sem_tag(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    linha = viewmodel.library_state(servico).rows[0]

    assert linha.title is None
    assert linha.display_title == linha.filename


def test_display_title_usa_a_tag_quando_existe(tmp_path):
    from trackclassifier.viewmodel import TrackRow

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


def test_texto_de_atualizacao_avisa_do_recomputo_de_features():
    from trackclassifier.updates import Release
    from trackclassifier.viewmodel import texto_de_atualizacao

    release = Release(
        version="0.3.0",
        url_zip="",
        url_sha256="",
        notas="Corrige o scan.",
        recomputa=frozenset({"features"}),
    )

    texto = texto_de_atualizacao(release, versao_atual="0.2.0", n_tracks=4200)

    assert "0.2.0" in texto
    assert "0.3.0" in texto
    assert "4200" in texto
    assert "recalcula" in texto
    assert "Corrige o scan." in texto


def test_texto_de_atualizacao_sem_recomputo_nao_assusta():
    from trackclassifier.updates import Release
    from trackclassifier.viewmodel import texto_de_atualizacao

    release = Release(
        version="0.3.0", url_zip="", url_sha256="", notas="", recomputa=frozenset()
    )

    texto = texto_de_atualizacao(release, versao_atual="0.2.0", n_tracks=4200)

    assert "recalcula" not in texto
    assert "4200" not in texto


def test_texto_de_atualizacao_diz_que_as_classificacoes_ficam():
    """A pergunta que o usuario faz antes de clicar em Atualizar."""
    from trackclassifier.updates import Release
    from trackclassifier.viewmodel import texto_de_atualizacao

    release = Release(
        version="0.3.0", url_zip="", url_sha256="", notas="", recomputa=frozenset()
    )

    texto = texto_de_atualizacao(release, versao_atual="0.2.0", n_tracks=10)

    assert "classificacoes" in texto


def _linha_para_derivacao(**campos) -> object:
    """TrackRow minimo por keyword: os testes de derivacao so olham genero e
    key, mas o dataclass exige o resto."""
    from trackclassifier import viewmodel

    base = {
        "sha1": "sha-derivacao",
        "filename": "derivacao.wav",
        "label": None,
        "predicted": None,
        "score": None,
        "confidence": None,
        "bpm": 120.0,
        "duration_s": 180.0,
        "energy_curve": (0.1,),
        "peak_offset_s": 1.0,
        "path_hint": "/fake/derivacao.wav",
    }
    base.update(campos)
    return viewmodel.TrackRow(**base)


def test_os_generos_do_acervo_saem_ordenados_sem_repeticao_e_sem_vazio():
    """O filtro de Genero mostra o acervo, nao uma lista escrita no codigo: so
    o que existe, uma vez cada, em ordem -- e tag ausente nao e um genero
    chamado "" (senao o filtro teria uma opcao vazia e sem nome)."""
    from trackclassifier import viewmodel

    linhas = (
        _linha_para_derivacao(genre="Techno"),
        _linha_para_derivacao(genre="House"),
        _linha_para_derivacao(genre="House"),
        _linha_para_derivacao(genre=None),
        _linha_para_derivacao(genre=""),
    )
    assert viewmodel._generos_do_acervo(linhas) == ("House", "Techno")


def test_as_keys_saem_em_ordem_de_roda_e_nao_alfabetica():
    """Ordem de roda: 12A e vizinha de 1A. Como texto, "12A" viria antes de
    "2A" -- o contrario do que a coluna Key serve para fazer."""
    from trackclassifier import viewmodel

    assert viewmodel._keys_em_ordem_de_roda(("12A", "2A", "2B", "1A", "10A", "2A")) == (
        "1A",
        "2A",
        "2B",
        "10A",
        "12A",
    )
