import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w

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


def _resolve_dir(folders_raw: dict, key: str) -> Path:
    if key not in folders_raw:
        raise ConfigError(f"Chave obrigatoria ausente em [folders]: {key}")
    folder = Path(folders_raw[key]).expanduser()
    if not folder.is_dir():
        raise ConfigError(f"Pasta configurada em [folders].{key} nao existe: {folder}")
    return folder


def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Arquivo de configuracao nao encontrado: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    folders_raw = raw.get("folders", {})
    folders: dict[Label, Path] = {}
    for key, label in _KEY_TO_LABEL.items():
        folders[label] = _resolve_dir(folders_raw, key)

    inbox = _resolve_dir(folders_raw, "inbox")

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


def save_config(path: Path, config: Config) -> None:
    """Grava o Config como TOML, criando o diretorio-pai se faltar.

    Usa tomli_w em vez de montar a string a mao: um caminho com aspas ou
    apostrofo -- "DJ's Tracks" e comum num acervo real -- exige escape de
    string basica TOML, e o erro nao aparece na gravacao, so na leitura
    seguinte, com o caminho silenciosamente errado.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dados = {
        "folders": {
            "up": str(config.folders[Label.UP]),
            "neutral": str(config.folders[Label.NEUTRAL]),
            "down": str(config.folders[Label.DOWN]),
            "inbox": str(config.inbox),
        },
        "model": {
            "retrain_every": config.retrain_every,
            "min_examples": config.min_examples,
        },
        "paths": {"data_dir": str(config.data_dir)},
    }
    with path.open("wb") as handle:
        tomli_w.dump(dados, handle)
