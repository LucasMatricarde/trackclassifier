import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from trackclassifier import audio_io
from trackclassifier.audio_io import (
    ANALYSIS_SR,
    AudioDecodeError,
    _dica_de_instalacao,
    _ffmpeg_embutido,
    _nome_no_bundle,
    _require_ffmpeg,
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


def test_nome_no_bundle_ganha_exe_no_windows():
    assert _nome_no_bundle("ffmpeg", windows=True) == "ffmpeg.exe"
    assert _nome_no_bundle("ffprobe", windows=True) == "ffprobe.exe"


def test_nome_no_bundle_fica_cru_fora_do_windows():
    assert _nome_no_bundle("ffmpeg", windows=False) == "ffmpeg"


def test_ffmpeg_embutido_acha_o_exe_do_bundle_do_windows(tmp_path, monkeypatch):
    """O PyInstaller preserva o nome do arquivo, e no Windows ele tem .exe.

    Procurar "ffmpeg" cru ali nao acha nada e a busca cai no PATH -- que e
    exatamente a dependencia que o binario embutido existe para remover.
    """
    (tmp_path / "ffmpeg.exe").write_bytes(b"")
    monkeypatch.setattr(audio_io.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert _ffmpeg_embutido("ffmpeg", windows=True) == str(tmp_path / "ffmpeg.exe")


def test_ffmpeg_embutido_e_none_fora_do_pacote(monkeypatch):
    monkeypatch.delattr(audio_io.sys, "_MEIPASS", raising=False)

    assert _ffmpeg_embutido("ffmpeg") is None


def test_dica_de_instalacao_e_a_da_plataforma():
    assert "brew" in _dica_de_instalacao("darwin")
    assert "winget" in _dica_de_instalacao("win32")
    assert "apt" in _dica_de_instalacao("linux")


def test_mensagem_de_ffmpeg_ausente_mantem_o_prefixo_que_agrupa(monkeypatch):
    """A dica muda com a plataforma; o prefixo da mensagem, nao.

    service._CATEGORIAS casa por prefixo -- se a dica entrasse na frente, a
    aba Modelo voltaria a mostrar um grupo por arquivo.
    """
    monkeypatch.delattr(audio_io.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(audio_io.shutil, "which", lambda _nome: None)

    with pytest.raises(AudioDecodeError) as erro:
        _require_ffmpeg("ffmpeg")

    assert str(erro.value).startswith("ffmpeg nao encontrado no PATH")


def test_identifica_formatos_que_precisam_de_transcodificacao():
    assert needs_transcode(Path("a.flac")) is True
    assert needs_transcode(Path("a.aiff")) is True
    assert needs_transcode(Path("a.AIF")) is True
    assert needs_transcode(Path("a.mp3")) is False
    assert needs_transcode(Path("a.wav")) is False
