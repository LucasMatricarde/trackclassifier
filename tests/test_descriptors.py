import numpy as np
import pytest

from trackclassifier.audio_io import ANALYSIS_SR
from trackclassifier.descriptors import DESCRIPTOR_NAMES, describe_window

DURACAO = 4.0


def _tempo(sr=ANALYSIS_SR):
    return np.linspace(0, DURACAO, int(sr * DURACAO), endpoint=False)


def _seno(freq, sr=ANALYSIS_SR):
    return (0.5 * np.sin(2 * np.pi * freq * _tempo(sr))).astype(np.float32)


def _ruido_branco(sr=ANALYSIS_SR):
    gerador = np.random.default_rng(seed=42)
    return (0.5 * gerador.standard_normal(int(sr * DURACAO))).astype(np.float32)


def _silencio(sr=ANALYSIS_SR):
    return np.zeros(int(sr * DURACAO), dtype=np.float32)


def test_retorna_exatamente_os_descritores_esperados():
    resultado = describe_window(_seno(440), ANALYSIS_SR)

    assert list(resultado.keys()) == DESCRIPTOR_NAMES
    assert len(DESCRIPTOR_NAMES) == 10
    assert all(isinstance(v, float) for v in resultado.values())


def test_todos_os_valores_sao_finitos_mesmo_em_silencio():
    resultado = describe_window(_silencio(), ANALYSIS_SR)

    assert all(np.isfinite(v) for v in resultado.values())
    assert resultado["rms"] == pytest.approx(0.0, abs=1e-9)


def test_rms_cresce_com_amplitude():
    fraco = describe_window(_seno(440) * 0.1, ANALYSIS_SR)
    forte = describe_window(_seno(440), ANALYSIS_SR)

    assert forte["rms"] > fraco["rms"] * 5


def test_ruido_branco_e_mais_brilhante_que_seno_grave():
    grave = describe_window(_seno(100), ANALYSIS_SR)
    ruido = describe_window(_ruido_branco(), ANALYSIS_SR)

    assert ruido["spectral_centroid"] > grave["spectral_centroid"]
    assert ruido["high_band_ratio"] > grave["high_band_ratio"]
    assert ruido["zero_crossing_rate"] > grave["zero_crossing_rate"]


def test_seno_grave_concentra_energia_na_banda_baixa():
    grave = describe_window(_seno(100), ANALYSIS_SR)
    agudo = describe_window(_seno(6000), ANALYSIS_SR)

    assert grave["low_band_ratio"] > 0.5
    assert agudo["low_band_ratio"] < grave["low_band_ratio"]


def test_razoes_de_banda_ficam_entre_zero_e_um():
    resultado = describe_window(_ruido_branco(), ANALYSIS_SR)

    for chave in ("low_band_ratio", "high_band_ratio", "percussive_ratio"):
        assert 0.0 <= resultado[chave] <= 1.0


# --- describe_slice: os mesmos invariantes, pelo caminho da v2 ------------


def _spectra(sinal, sr=ANALYSIS_SR):
    from trackclassifier.spectral import compute_spectra

    return compute_spectra(sinal.astype(np.float32), sr)


def _slice_completo(sinal, sr=ANALYSIS_SR):
    from trackclassifier.descriptors import describe_slice

    espectros = _spectra(sinal, sr)
    return describe_slice(espectros, 0, espectros.n_frames, 0, len(sinal))


def test_slice_retorna_exatamente_os_descritores_esperados():
    resultado = _slice_completo(_seno(440))

    assert list(resultado.keys()) == DESCRIPTOR_NAMES
    assert all(isinstance(v, float) for v in resultado.values())


def test_slice_e_finito_mesmo_em_silencio():
    # Silencio absoluto e o caso que quebra tudo que divide: total_energy zera,
    # o HPSS opera sobre uma matriz de zeros, e a envoltoria de onset nao tem
    # pico nenhum. Os _EPS dos denominadores existem para este teste.
    resultado = _slice_completo(_silencio())

    assert all(np.isfinite(v) for v in resultado.values())
    assert resultado["rms"] == pytest.approx(0.0, abs=1e-9)


def test_slice_mantem_razoes_de_banda_entre_zero_e_um():
    resultado = _slice_completo(_ruido_branco())

    for chave in ("low_band_ratio", "high_band_ratio", "percussive_ratio"):
        assert 0.0 <= resultado[chave] <= 1.0


def test_slice_concorda_com_describe_window_nos_descritores_espectrais():
    # A prova de que a agregacao por frames e a mesma conta: media de medias
    # sobre os mesmos frames. So percussive_ratio e onset_rate ficam de fora,
    # que sao justamente os dois que mudaram de metodo.
    sinal = _ruido_branco()
    janela = describe_window(sinal, ANALYSIS_SR)
    fatia = _slice_completo(sinal)

    for chave in (
        "rms",
        "spectral_centroid",
        "spectral_rolloff",
        "spectral_bandwidth",
        "low_band_ratio",
        "high_band_ratio",
        "zero_crossing_rate",
    ):
        assert fatia[chave] == pytest.approx(janela[chave], rel=0.01), chave


def test_slice_de_janela_minima_nao_estoura():
    # frame_bounds garante ao menos um frame; sem isso a fatia vazia viraria
    # NaN em toda media e contaminaria o vetor inteiro pelo _stats.
    from trackclassifier.descriptors import describe_slice

    sinal = _ruido_branco()
    espectros = _spectra(sinal)
    resultado = describe_slice(espectros, 0, 1, 0, 256)

    assert all(np.isfinite(v) for v in resultado.values())
