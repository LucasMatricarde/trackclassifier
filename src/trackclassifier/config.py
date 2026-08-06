import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

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


#: Nome da subpasta criada para cada rotulo no modo "criar a estrutura".
#: Vem do vocabulario que o app ja usa na tela e nos atalhos 1/2/3 -- nao
#: inventamos jargao novo so para o disco.
NOMES_DE_PASTA: Final = {"up": "+1", "neutral": "neutra", "down": "-1"}

_RETRAIN_PADRAO: Final = 10
_MIN_EXEMPLOS_PADRAO: Final = 15


def read_raw(path: Path) -> dict:
    """Le o TOML sem validar nada. {} quando ausente ou ilegivel.

    Existe por causa do caso "config existe mas uma pasta sumiu":
    load_config levanta ConfigError e nao devolve nada aproveitavel, entao o
    dialogo de configuracao nao teria com que se preencher e o usuario
    redigitaria os quatro caminhos por causa de um que mudou. Nao substitui
    load_config em lugar nenhum -- nao valida, nao expande, nao cria pasta.
    """
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (tomllib.TOMLDecodeError, OSError):
        # Config corrompido nao pode derrubar justamente a tela que serve
        # para consertar config.
        return {}


@dataclass(frozen=True)
class SettingsDraft:
    """O que o formulario tem digitado, ainda sem garantia de ser valido.

    Strings, nao Path: e o texto cru do campo, que pode estar vazio ou
    apontar para algo inexistente enquanto o usuario digita.
    """

    inbox: str
    up: str
    neutral: str
    down: str
    data_dir: str
    retrain_every: int
    min_examples: int
    #: True no modo "criar a estrutura": up/neutral/down sao derivados de
    #: `root` e ainda nao existem no disco.
    create_under_root: bool
    root: str

    @classmethod
    def from_raw(cls, raw: dict) -> "SettingsDraft":
        pastas = raw.get("folders", {})
        modelo = raw.get("model", {})
        caminhos = raw.get("paths", {})
        return cls(
            inbox=str(pastas.get("inbox", "")),
            up=str(pastas.get("up", "")),
            neutral=str(pastas.get("neutral", "")),
            down=str(pastas.get("down", "")),
            data_dir=str(caminhos.get("data_dir", "")),
            retrain_every=int(modelo.get("retrain_every", _RETRAIN_PADRAO)),
            min_examples=int(modelo.get("min_examples", _MIN_EXEMPLOS_PADRAO)),
            create_under_root=False,
            root="",
        )
