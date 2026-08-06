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

    def rename(self, origem: Path, destino: Path) -> None:
        """Reaponta a entrada de origem para destino, sem reler o arquivo.

        A chave aqui e o caminho, e decidir/reclassificar/desfazer sempre move
        o arquivo entre pastas. Sem isto, cada track decidida virava cache-miss
        garantido no scan seguinte: o conteudo nao mudou em nada, mas o sha1
        era recalculado lendo o arquivo inteiro de novo.

        O mtime/size vem de um stat NOVO do destino, nao do registro antigo:
        shutil.move usa os.rename dentro do mesmo filesystem (preserva) mas
        copy2 entre filesystems diferentes, e nem todo par de filesystem
        preserva o mtime com fidelidade total. Um stat custa uma syscall e
        elimina a duvida -- guardar um mtime errado aqui geraria um miss
        silencioso depois, que e exatamente o bug que este metodo existe para
        matar.
        """
        registro = self._linhas.pop(str(Path(origem)), None)
        if registro is None:
            return

        destino = Path(destino)
        try:
            info = destino.stat()
        except OSError:
            # Destino sumiu entre o move e esta chamada. Ficar sem entrada e
            # o desfecho seguro: o proximo scan recalcula e acerta. Gravar
            # mtime/size de um arquivo inexistente, nao.
            self._sujo = True
            return

        self._linhas[str(destino)] = {
            "mtime": info.st_mtime,
            "size": info.st_size,
            "sha1": registro["sha1"],
        }
        self._sujo = True

    def save(self) -> None:
        if not self._sujo:
            return
        # Rede de seguranca para o caminho antigo que rename() nao cobriu --
        # arquivo removido por fora, movido por outra ferramenta, pasta
        # renomeada na mao. Sem a poda o JSON cresceria pra sempre com lixo
        # de arquivos que nao existem mais.
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
