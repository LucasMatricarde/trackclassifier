import json
import os
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


class Sha1Cache:
    """Memoriza o sha1 de cada arquivo por (caminho, mtime, size).

    O sha1 continua sendo a identidade da track -- isto so evita reler o
    arquivo inteiro quando nada nele mudou. A tripla e conservadora de
    proposito: qualquer divergencia em mtime ou tamanho recalcula. Uma
    edicao que preserve os dois e possivel na teoria, mas exigiria
    reescrever o arquivo mantendo byte-count e timestamp, o que nenhuma
    ferramenta de audio faz.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._linhas: dict[str, dict] = {}
        self._sujo = False
        if self.path.is_file():
            try:
                self._linhas = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                # Mesma contencao de cache.py: JSON truncado por interrupcao
                # ou schema antigo vira cache vazio, nunca derruba o comando.
                self._linhas = {}

    def __len__(self) -> int:
        return len(self._linhas)

    def get(self, caminho: Path) -> str:
        caminho = Path(caminho)
        chave = str(caminho)
        info = caminho.stat()
        registro = self._linhas.get(chave)
        if (
            registro is not None
            and registro.get("mtime") == info.st_mtime
            and registro.get("size") == info.st_size
        ):
            return registro["sha1"]

        digest = file_sha1(caminho)
        self._linhas[chave] = {
            "mtime": info.st_mtime,
            "size": info.st_size,
            "sha1": digest,
        }
        self._sujo = True
        return digest

    def save(self) -> None:
        if not self._sujo:
            return
        # Chave e o caminho (nao o sha1): decidir uma track sempre move o
        # arquivo pra outra pasta, entao toda decisao deixa uma entrada
        # orfa aqui -- o caminho antigo nunca mais existe. Isto nao resolve
        # o cache-miss no proximo scan da track decidida (precisaria de
        # reindexacao por sha1, fora do escopo desta correcao), mas evita
        # que o JSON cresca pra sempre com lixo de arquivos que sumiram.
        self._linhas = {
            caminho: registro
            for caminho, registro in self._linhas.items()
            if Path(caminho).is_file()
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._linhas), encoding="utf-8")
        os.replace(tmp, self.path)
        self._sujo = False


def _arquivos_de_audio(raiz: Path) -> list[Path]:
    encontrados = [
        caminho
        for caminho in raiz.rglob("*")
        if caminho.is_file()
        and not caminho.name.startswith(".")
        and caminho.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(encontrados, key=lambda caminho: str(caminho).lower())


def scan_labeled(config: Config, sha1_cache: Sha1Cache | None = None) -> list[TrackRef]:
    calcula = sha1_cache.get if sha1_cache is not None else file_sha1
    refs: list[TrackRef] = []
    for rotulo, pasta in config.folders.items():
        for caminho in _arquivos_de_audio(pasta):
            refs.append(TrackRef(path=caminho, label=rotulo, sha1=calcula(caminho)))
    return sorted(refs, key=lambda ref: str(ref.path).lower())


def _dentro_de_pasta_rotulada(caminho: Path, pastas_rotuladas: list[Path]) -> bool:
    resolvido = caminho.resolve()
    return any(
        resolvido == pasta or pasta in resolvido.parents for pasta in pastas_rotuladas
    )


def scan_inbox(config: Config, sha1_cache: Sha1Cache | None = None) -> list[TrackRef]:
    calcula = sha1_cache.get if sha1_cache is not None else file_sha1
    pastas_rotuladas = [pasta.resolve() for pasta in config.folders.values()]
    return [
        TrackRef(path=caminho, label=None, sha1=calcula(caminho))
        for caminho in _arquivos_de_audio(config.inbox)
        if not _dentro_de_pasta_rotulada(caminho, pastas_rotuladas)
    ]
