from dataclasses import dataclass
from pathlib import Path

from .audio_io import SUPPORTED_SUFFIXES
from .cache import file_sha1
from .config import Config
from .labels import Label


@dataclass(frozen=True)
class TrackRef:
    path: Path
    label: Label | None
    sha1: str


def _arquivos_de_audio(raiz: Path) -> list[Path]:
    encontrados = [
        caminho
        for caminho in raiz.rglob("*")
        if caminho.is_file()
        and not caminho.name.startswith(".")
        and caminho.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(encontrados, key=lambda caminho: str(caminho).lower())


def scan_labeled(config: Config) -> list[TrackRef]:
    refs: list[TrackRef] = []
    for rotulo, pasta in config.folders.items():
        for caminho in _arquivos_de_audio(pasta):
            refs.append(TrackRef(path=caminho, label=rotulo, sha1=file_sha1(caminho)))
    return sorted(refs, key=lambda ref: str(ref.path).lower())


def _dentro_de_pasta_rotulada(caminho: Path, pastas_rotuladas: list[Path]) -> bool:
    resolvido = caminho.resolve()
    return any(
        resolvido == pasta or pasta in resolvido.parents for pasta in pastas_rotuladas
    )


def scan_inbox(config: Config) -> list[TrackRef]:
    pastas_rotuladas = [pasta.resolve() for pasta in config.folders.values()]
    return [
        TrackRef(path=caminho, label=None, sha1=file_sha1(caminho))
        for caminho in _arquivos_de_audio(config.inbox)
        if not _dentro_de_pasta_rotulada(caminho, pastas_rotuladas)
    ]
