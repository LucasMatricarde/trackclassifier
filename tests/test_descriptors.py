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
