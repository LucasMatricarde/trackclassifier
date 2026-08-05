import tomllib
from dataclasses import dataclass
from pathlib import Path

from .labels import Label


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    folders: dict[Label, Path]
    inbox: Path
    data_dir: Path
    retrain_every: int
    min_examples: int


_KEY_TO_LABEL = {"up": Label.UP, "neutral": Label.NEUTRAL, "down": Label.DOWN}


def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Arquivo de configuracao nao encontrado: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    folders_raw = raw.get("folders", {})
    folders: dict[Label, Path] = {}
    for key, label in _KEY_TO_LABEL.items():
        if key not in folders_raw:
            raise ConfigError(f"Chave obrigatoria ausente em [folders]: {key}")
        folder = Path(folders_raw[key]).expanduser()
        if not folder.is_dir():
            raise ConfigError(f"Pasta configurada em [folders].{key} nao existe: {folder}")
        folders[label] = folder

    if "inbox" not in folders_raw:
        raise ConfigError("Chave obrigatoria ausente em [folders]: inbox")
    inbox = Path(folders_raw["inbox"]).expanduser()
    if not inbox.is_dir():
        raise ConfigError(f"Pasta configurada em [folders].inbox nao existe: {inbox}")

    data_dir = Path(raw.get("paths", {}).get("data_dir", ".trackclassifier")).expanduser()
    if not data_dir.is_absolute():
        data_dir = path.parent / data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    model_raw = raw.get("model", {})
    return Config(
        folders=folders,
        inbox=inbox,
        data_dir=data_dir,
        retrain_every=int(model_raw.get("retrain_every", 10)),
        min_examples=int(model_raw.get("min_examples", 15)),
    )
