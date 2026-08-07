import os
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


#: Como instalar o ffmpeg, por plataforma. So aparece para quem roda do
#: codigo-fonte: no executavel empacotado os binarios vao dentro dele.
_DICAS_DE_INSTALACAO = {
    "darwin": "brew install ffmpeg",
    "win32": "winget install Gyan.FFmpeg",
}
_DICA_PADRAO = "sudo apt install ffmpeg"


def _dica_de_instalacao(plataforma: str | None = None) -> str:
    if plataforma is None:
        plataforma = sys.platform
    return _DICAS_DE_INSTALACAO.get(plataforma, _DICA_PADRAO)


def _nome_no_bundle(binary: str, windows: bool | None = None) -> str:
    """Nome do arquivo que o PyInstaller copiou para dentro do pacote.

    O spec entrega o caminho que `shutil.which` achou na maquina de build e o
    PyInstaller preserva o nome: no Windows isso e "ffmpeg.exe", nas outras
    plataformas "ffmpeg". Procurar o nome cru no Windows nao acha nada e a
    busca cai no PATH -- justamente a dependencia que o binario embutido
    existe para remover.
    """
    if windows is None:
        windows = os.name == "nt"
    return f"{binary}.exe" if windows else binary


def _ffmpeg_embutido(binary: str, windows: bool | None = None) -> str | None:
    """Binario que veio dentro do pacote, quando ha um.

    Um app aberto pelo Finder (ou pelo Menu Iniciar) nao herda o PATH do
    shell -- nao ve /opt/homebrew/bin, entao shutil.which falharia em toda
    track mesmo com o ffmpeg instalado. sys._MEIPASS so existe sob
    PyInstaller, entao fora do pacote esta funcao nao encontra nada e a busca
    no PATH segue valendo.
    """
    raiz = getattr(sys, "_MEIPASS", None)
    if raiz is None:
        return None
    caminho = Path(raiz) / _nome_no_bundle(binary, windows)
    return str(caminho) if caminho.is_file() else None


def _require_ffmpeg(binary: str) -> str:
    caminho = _ffmpeg_embutido(binary) or shutil.which(binary)
    if caminho is None:
        # O prefixo ate "no PATH" e contrato: service._CATEGORIAS agrupa as
        # falhas do scan casando o inicio da mensagem. So a dica varia.
        raise AudioDecodeError(
            f"{binary} nao encontrado no PATH. Instale com: {_dica_de_instalacao()}"
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
