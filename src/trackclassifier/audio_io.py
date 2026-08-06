import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ANALYSIS_SR = 22050

# Generoso o suficiente para o transcode/decode de uma track de duracao
# normal, curto o suficiente para falhar rapido num ffmpeg/ffprobe
# realmente travado (arquivo malformado/corrompido) em vez de segurar a
# thread do servidor web para sempre.
SUBPROCESS_TIMEOUT_S = 120

SUPPORTED_SUFFIXES = {".mp3", ".wav", ".aiff", ".aif", ".flac", ".m4a", ".ogg"}
BROWSER_NATIVE_SUFFIXES = {".mp3", ".wav", ".m4a", ".ogg"}


class AudioDecodeError(Exception):
    pass


def _ffmpeg_embutido(binary: str) -> str | None:
    """Binario que veio dentro do .app, quando ha um.

    Um app aberto pelo Finder nao herda o PATH do shell -- nao ve
    /opt/homebrew/bin, entao shutil.which falharia em toda track mesmo com o
    ffmpeg instalado. sys._MEIPASS so existe sob PyInstaller, entao fora do
    pacote esta funcao nao encontra nada e a busca no PATH segue valendo.
    """
    raiz = getattr(sys, "_MEIPASS", None)
    if raiz is None:
        return None
    caminho = Path(raiz) / binary
    return str(caminho) if caminho.is_file() else None


def _require_ffmpeg(binary: str) -> str:
    caminho = _ffmpeg_embutido(binary) or shutil.which(binary)
    if caminho is None:
        raise AudioDecodeError(
            f"{binary} nao encontrado no PATH. Instale com: brew install ffmpeg"
        )
    return caminho


def decode(path: Path, sample_rate: int = ANALYSIS_SR) -> np.ndarray:
    path = Path(path)
    if not path.is_file():
        raise AudioDecodeError(f"Arquivo nao encontrado: {path}")

    comando = [
        _require_ffmpeg("ffmpeg"),
        "-v", "error",
        "-i", str(path),
        "-f", "f32le",
        "-acodec", "pcm_f32le",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-",
    ]
    try:
        proc = subprocess.run(comando, capture_output=True, timeout=SUBPROCESS_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise AudioDecodeError(f"Tempo esgotado ao decodificar {path.name}") from exc
    if proc.returncode != 0:
        detalhe = proc.stderr.decode("utf-8", errors="replace").strip()
        raise AudioDecodeError(f"Falha ao decodificar {path.name}: {detalhe}")

    y = np.frombuffer(proc.stdout, dtype=np.float32)
    if y.size == 0:
        raise AudioDecodeError(f"Arquivo sem audio decodificavel: {path.name}")
    return np.array(y, dtype=np.float32)


def probe_duration(path: Path) -> float:
    path = Path(path)
    if not path.is_file():
        raise AudioDecodeError(f"Arquivo nao encontrado: {path}")

    comando = [
        _require_ffmpeg("ffprobe"),
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        proc = subprocess.run(comando, capture_output=True, timeout=SUBPROCESS_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise AudioDecodeError(f"Tempo esgotado ao medir duracao de {path.name}") from exc
    if proc.returncode != 0:
        raise AudioDecodeError(f"Falha ao medir duracao de {path.name}")
    try:
        return float(proc.stdout.decode().strip())
    except ValueError as exc:
        raise AudioDecodeError(f"Duracao invalida para {path.name}") from exc


def needs_transcode(path: Path) -> bool:
    return Path(path).suffix.lower() not in BROWSER_NATIVE_SUFFIXES
