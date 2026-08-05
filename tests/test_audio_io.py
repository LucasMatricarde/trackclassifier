import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from trackclassifier.audio_io import (
    ANALYSIS_SR,
    AudioDecodeError,
    decode,
    needs_transcode,
    probe_duration,
)


@pytest.fixture
def wav_estereo(tmp_path) -> Path:
    sr = 44100
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
    tom = 0.5 * np.sin(2 * np.pi * 440 * t)
    estereo = np.stack([tom, tom], axis=1)
    caminho = tmp_path / "tom.wav"
    sf.write(caminho, estereo, sr)
    return caminho


def test_decodifica_para_mono_float32_na_taxa_de_analise(wav_estereo):
    y = decode(wav_estereo)

    assert y.ndim == 1
    assert y.dtype == np.float32
    assert abs(len(y) - ANALYSIS_SR * 2) < ANALYSIS_SR * 0.05


def test_respeita_taxa_de_amostragem_solicitada(wav_estereo):
    y = decode(wav_estereo, sample_rate=8000)

    assert abs(len(y) - 8000 * 2) < 8000 * 0.05


def test_mede_duracao(wav_estereo):
    assert probe_duration(wav_estereo) == pytest.approx(2.0, abs=0.05)


def test_arquivo_corrompido_levanta_erro(tmp_path):
    ruim = tmp_path / "quebrado.mp3"
    ruim.write_bytes(b"isto nao e audio")

    with pytest.raises(AudioDecodeError):
        decode(ruim)


def test_arquivo_inexistente_levanta_erro(tmp_path):
    with pytest.raises(AudioDecodeError):
        decode(tmp_path / "sumiu.wav")


def test_timeout_ao_decodificar_levanta_erro_de_dominio(wav_estereo, monkeypatch):
    def _trava(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120)

    monkeypatch.setattr("trackclassifier.audio_io.subprocess.run", _trava)

    with pytest.raises(AudioDecodeError):
        decode(wav_estereo)


def test_timeout_ao_medir_duracao_levanta_erro_de_dominio(wav_estereo, monkeypatch):
    def _trava(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=120)

    monkeypatch.setattr("trackclassifier.audio_io.subprocess.run", _trava)

    with pytest.raises(AudioDecodeError):
        probe_duration(wav_estereo)


def test_identifica_formatos_que_precisam_de_transcodificacao():
    assert needs_transcode(Path("a.flac")) is True
    assert needs_transcode(Path("a.aiff")) is True
    assert needs_transcode(Path("a.AIF")) is True
    assert needs_transcode(Path("a.mp3")) is False
    assert needs_transcode(Path("a.wav")) is False
