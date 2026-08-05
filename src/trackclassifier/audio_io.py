import shutil
import subprocess
from pathlib import Path

import numpy as np

ANALYSIS_SR = 22050

SUPPORTED_SUFFIXES = {".mp3", ".wav", ".aiff", ".aif", ".flac", ".m4a", ".ogg"}
BROWSER_NATIVE_SUFFIXES = {".mp3", ".wav", ".m4a", ".ogg"}


class AudioDecodeError(Exception):
    pass


def _require_ffmpeg(binary: str) -> str:
    caminho = shutil.which(binary)
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
    proc = subprocess.run(comando, capture_output=True)
    if proc.returncode != 0:
        detalhe = proc.stderr.decode("utf-8", errors="replace").strip()
        raise AudioDecodeError(f"Falha ao decodificar {path.name}: {detalhe}")

    y = np.frombuffer(proc.stdout, dtype=np.float32)
    if y.size == 0:
        raise AudioDecodeError(f"Arquivo sem audio decodificavel: {path.name}")
    return np.ascontiguousarray(y)


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
    proc = subprocess.run(comando, capture_output=True)
    if proc.returncode != 0:
        raise AudioDecodeError(f"Falha ao medir duracao de {path.name}")
    try:
        return float(proc.stdout.decode().strip())
    except ValueError as exc:
        raise AudioDecodeError(f"Duracao invalida para {path.name}") from exc


def needs_transcode(path: Path) -> bool:
    return Path(path).suffix.lower() not in BROWSER_NATIVE_SUFFIXES
