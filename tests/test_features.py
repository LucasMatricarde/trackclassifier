import numpy as np
import pytest
import soundfile as sf

from trackclassifier.audio_io import ANALYSIS_SR
from trackclassifier.features import (
    FEATURE_NAMES,
    HandcraftedExtractor,
    TrackAnalysis,
    TrackTooShortError,
)


def _escreve_wav(caminho, sinal, sr=ANALYSIS_SR):
    sf.write(caminho, sinal.astype(np.float32), sr)
    return caminho


def _clicks(bpm, duracao_s, sr=ANALYSIS_SR):
    import librosa

    tempos = np.arange(0, duracao_s, 60.0 / bpm)
    return librosa.clicks(times=tempos, sr=sr, length=int(sr * duracao_s))


def _track_com_pico(duracao_s=60.0, inicio_pico=30.0, sr=ANALYSIS_SR):
    gerador = np.random.default_rng(seed=7)
    sinal = 0.05 * gerador.standard_normal(int(sr * duracao_s))
    a = int(sr * inicio_pico)
    b = int(sr * (inicio_pico + 10.0))
    sinal[a:b] *= 12.0
    return sinal


def test_nomes_de_features_sao_44_e_unicos():
    assert len(FEATURE_NAMES) == 44
    assert len(set(FEATURE_NAMES)) == 44
    assert FEATURE_NAMES[0] == "rms_median"
    assert FEATURE_NAMES[-4:] == ["bpm", "lufs", "dynamic_range_db", "duration_s"]


def test_extrai_vetor_com_dimensao_correta(tmp_path):
    caminho = _escreve_wav(tmp_path / "t.wav", _track_com_pico())

    analise = HandcraftedExtractor().extract(caminho)

    assert isinstance(analise, TrackAnalysis)
    assert analise.vector.shape == (44,)
    assert np.all(np.isfinite(analise.vector))


def test_curva_de_energia_acompanha_as_janelas(tmp_path):
    caminho = _escreve_wav(tmp_path / "t.wav", _track_com_pico())

    analise = HandcraftedExtractor().extract(caminho)

    assert len(analise.energy_curve) >= 5
    assert all(np.isfinite(v) for v in analise.energy_curve)


def test_offset_do_pico_aponta_para_o_trecho_mais_energetico(tmp_path):
    caminho = _escreve_wav(tmp_path / "t.wav", _track_com_pico(inicio_pico=30.0))

    analise = HandcraftedExtractor().extract(caminho)

    assert 28.0 <= analise.peak_offset_s <= 40.0


def test_detecta_bpm_de_um_trem_de_cliques(tmp_path):
    caminho = _escreve_wav(tmp_path / "click.wav", _clicks(128, 30.0))

    analise = HandcraftedExtractor().extract(caminho)

    assert analise.bpm == pytest.approx(128, rel=0.05)


def test_reporta_duracao(tmp_path):
    caminho = _escreve_wav(tmp_path / "t.wav", _track_com_pico(duracao_s=45.0))

    analise = HandcraftedExtractor().extract(caminho)

    assert analise.duration_s == pytest.approx(45.0, abs=1.0)


def test_track_curta_demais_e_rejeitada(tmp_path):
    gerador = np.random.default_rng(seed=1)
    curta = 0.2 * gerador.standard_normal(int(ANALYSIS_SR * 6.0))
    caminho = _escreve_wav(tmp_path / "curta.wav", curta)

    with pytest.raises(TrackTooShortError):
        HandcraftedExtractor().extract(caminho)


def test_track_de_15_segundos_usa_janela_reduzida_e_funciona(tmp_path):
    gerador = np.random.default_rng(seed=2)
    curta = 0.2 * gerador.standard_normal(int(ANALYSIS_SR * 15.0))
    caminho = _escreve_wav(tmp_path / "media.wav", curta)

    analise = HandcraftedExtractor().extract(caminho)

    assert analise.vector.shape == (44,)
    assert len(analise.energy_curve) >= 5


def test_extrator_declara_nome_de_versao():
    assert HandcraftedExtractor().name == "handcrafted-v1"
