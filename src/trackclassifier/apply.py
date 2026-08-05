import shutil
from pathlib import Path


class FileVanishedError(Exception):
    pass


def _destino_livre(dest_dir: Path, nome: str) -> Path:
    candidato = dest_dir / nome
    if not candidato.exists():
        return candidato

    base = Path(nome).stem
    sufixo = Path(nome).suffix
    contador = 1
    while True:
        candidato = dest_dir / f"{base} ({contador}){sufixo}"
        if not candidato.exists():
            return candidato
        contador += 1


def move_to_folder(src: Path, dest_dir: Path) -> Path:
    src = Path(src)
    if not src.is_file():
        raise FileVanishedError(f"Arquivo nao existe mais: {src}")

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    destino = _destino_livre(dest_dir, src.name)
    shutil.move(str(src), str(destino))
    return destino
