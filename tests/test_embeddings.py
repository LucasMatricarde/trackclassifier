import numpy as np

from trackclassifier.embeddings import (
    EMBEDDING_DIM,
    EmbeddingCache,
    aggregate_embeddings,
    deterministic_clips,
)


def test_amostra_cinco_trechos_deterministicos_de_9_6_segundos():
    waveform = np.arange(100 * 16_000, dtype=np.float32)

    clips = deterministic_clips(waveform, sample_rate=16_000)

    assert clips.shape == (5, 153_600)
    assert [int(clip[0] / 16_000) for clip in clips] == [5, 25, 45, 65, 85]


def test_track_curta_e_preenchida_sem_mudar_o_numero_de_amostras():
    waveform = np.ones(16_000, dtype=np.float32)

    clips = deterministic_clips(waveform, sample_rate=16_000)

    assert clips.shape == (5, 153_600)
    assert np.all(clips[:, :16_000] == 1.0)
    assert np.all(clips[:, 16_000:] == 0.0)


def test_agregacao_concatena_media_e_desvio_padrao():
    embeddings = np.stack(
        [np.full(EMBEDDING_DIM, valor, dtype=np.float32) for valor in range(5)]
    )

    vetor = aggregate_embeddings(embeddings)

    assert vetor.shape == (EMBEDDING_DIM * 2,)
    assert np.allclose(vetor[:EMBEDDING_DIM], 2.0)
    assert np.allclose(vetor[EMBEDDING_DIM:], np.std(np.arange(5)))


def test_cache_invalida_por_pesos_e_versao_de_extracao(tmp_path):
    path = tmp_path / "embeddings.parquet"
    vetor = np.arange(EMBEDDING_DIM * 2, dtype=np.float32)
    cache = EmbeddingCache(path)
    cache.put("abc", weights_sha256="pesos-a", extraction_version="v1", vector=vetor)
    cache.save()

    reaberto = EmbeddingCache(path)
    assert np.array_equal(reaberto.get("abc", "pesos-a", "v1"), vetor)
    assert reaberto.get("abc", "pesos-b", "v1") is None
    assert reaberto.get("abc", "pesos-a", "v2") is None
