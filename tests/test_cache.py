import numpy as np

from trackclassifier.cache import AnalysisCache, file_sha1
from trackclassifier.features import TrackAnalysis


def _analise(valor=1.0):
    return TrackAnalysis(
        vector=np.full(44, valor, dtype=np.float64),
        energy_curve=[0.1, 0.4, 0.2],
        peak_offset_s=5.0,
        bpm=128.0,
        duration_s=300.0,
    )


def test_sha1_e_estavel_e_sensivel_ao_conteudo(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"conteudo")
    b.write_bytes(b"conteudo")

    assert file_sha1(a) == file_sha1(b)

    b.write_bytes(b"outro conteudo")
    assert file_sha1(a) != file_sha1(b)


def test_get_retorna_none_para_chave_ausente(tmp_path):
    cache = AnalysisCache(tmp_path / "cache.parquet")

    assert cache.get("inexistente") is None


def test_grava_e_le_analise(tmp_path):
    cache = AnalysisCache(tmp_path / "cache.parquet")
    cache.put("abc", "track.mp3", "handcrafted-v1", _analise(2.5))

    recuperada = cache.get("abc")

    assert recuperada is not None
    assert np.allclose(recuperada.vector, 2.5)
    assert recuperada.energy_curve == [0.1, 0.4, 0.2]
    assert recuperada.peak_offset_s == 5.0
    assert recuperada.bpm == 128.0
    assert recuperada.duration_s == 300.0


def test_persiste_entre_instancias(tmp_path):
    caminho = tmp_path / "cache.parquet"
    primeira = AnalysisCache(caminho)
    primeira.put("abc", "track.mp3", "handcrafted-v1", _analise(3.0))
    primeira.save()

    segunda = AnalysisCache(caminho)

    assert len(segunda) == 1
    assert np.allclose(segunda.get("abc").vector, 3.0)


def test_put_sobrescreve_a_mesma_chave(tmp_path):
    cache = AnalysisCache(tmp_path / "cache.parquet")
    cache.put("abc", "track.mp3", "handcrafted-v1", _analise(1.0))
    cache.put("abc", "track.mp3", "handcrafted-v1", _analise(9.0))

    assert len(cache) == 1
    assert np.allclose(cache.get("abc").vector, 9.0)


def test_get_e_miss_quando_extractor_nao_bate(tmp_path):
    cache = AnalysisCache(tmp_path / "cache.parquet")
    cache.put("abc", "track.mp3", "handcrafted-v1", _analise(2.5))

    assert cache.get("abc", "handcrafted-v2") is None


def test_get_e_hit_quando_extractor_bate_ou_nao_e_informado(tmp_path):
    cache = AnalysisCache(tmp_path / "cache.parquet")
    cache.put("abc", "track.mp3", "handcrafted-v1", _analise(2.5))

    com_extractor = cache.get("abc", "handcrafted-v1")
    sem_extractor = cache.get("abc")

    assert com_extractor is not None
    assert np.allclose(com_extractor.vector, 2.5)
    assert sem_extractor is not None
    assert np.allclose(sem_extractor.vector, 2.5)


def test_parquet_corrompido_nao_derruba_a_construcao(tmp_path):
    caminho = tmp_path / "cache.parquet"
    caminho.write_bytes(b"isto nao e um parquet valido")

    cache = AnalysisCache(caminho)

    assert len(cache) == 0
    assert cache.get("qualquer") is None


def test_save_e_atomico_e_nao_deixa_tmp_para_tras(tmp_path):
    caminho = tmp_path / "cache.parquet"
    cache = AnalysisCache(caminho)
    cache.put("abc", "track.mp3", "handcrafted-v1", _analise(2.5))

    cache.save()

    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    assert not tmp.exists()
    assert caminho.is_file()
    assert len(AnalysisCache(caminho)) == 1
