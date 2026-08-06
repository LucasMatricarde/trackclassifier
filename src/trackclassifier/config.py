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

#: Nome exibido na tela para cada chave interna de campo -- usado para a
#: mensagem de "mesma pasta" em validate_settings nao vazar vocabulario
#: interno (up/neutral/down/inbox/root/data_dir) que nenhuma tela usa.
#: up/neutral/down reaproveitam NOMES_DE_PASTA; os outros tres nao tinham
#: correspondente ali porque NOMES_DE_PASTA e sobre nome de subpasta no
#: disco, nao sobre rotulo de campo na tela.
NOMES_DE_EXIBICAO: Final = {
    **NOMES_DE_PASTA,
    "inbox": "entrada",
    "root": "raiz",
    "data_dir": "dados do app",
}

_RETRAIN_PADRAO: Final = 10
_MIN_EXEMPLOS_PADRAO: Final = 15


def _tabela(raw: dict, chave: str) -> dict:
    """dict em raw[chave], ou {} se a chave esta ausente ou do tipo errado.

    Um TOML sintaticamente valido mas com `folders = "oops"` (string em vez
    de tabela) faria o .get() seguinte estourar AttributeError -- read_raw
    so protege contra TOML ilegivel, nao contra TOML valido com o tipo
    errado num campo.
    """
    valor = raw.get(chave, {})
    return valor if isinstance(valor, dict) else {}


def _inteiro(valor, padrao: int) -> int:
    """int(valor), com fallback pro padrao quando o valor nao converte.

    Cobre um TOML editado a mao com `retrain_every = "dez"`: sintaticamente
    valido, mas int() estoura ValueError -- e essa excecao rodaria dentro de
    FirstRunDialog.__init__/SettingsTab.__init__ (via SettingsDraft.from_raw),
    que nao tem try/except em volta, derrubando justamente a tela que existe
    para consertar um config quebrado.
    """
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


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
        pastas = _tabela(raw, "folders")
        modelo = _tabela(raw, "model")
        caminhos = _tabela(raw, "paths")
        return cls(
            inbox=str(pastas.get("inbox", "")),
            up=str(pastas.get("up", "")),
            neutral=str(pastas.get("neutral", "")),
            down=str(pastas.get("down", "")),
            data_dir=str(caminhos.get("data_dir", "")),
            retrain_every=_inteiro(modelo.get("retrain_every"), _RETRAIN_PADRAO),
            min_examples=_inteiro(modelo.get("min_examples"), _MIN_EXEMPLOS_PADRAO),
            create_under_root=False,
            root="",
        )


@dataclass(frozen=True)
class SettingsError:
    """Erro amarrado a um campo do formulario, nao a uma caixa modal.

    `field` e uma das chaves: inbox, up, neutral, down, root, data_dir.
    """

    field: str
    message: str


def _subpastas_da_raiz(root: str) -> dict[str, Path]:
    raiz = Path(root).expanduser()
    return {chave: raiz / nome for chave, nome in NOMES_DE_PASTA.items()}


def _caminhos_do_draft(draft: SettingsDraft) -> dict[str, Path]:
    """Os quatro destinos finais, ja resolvidos, nos dois modos."""
    if draft.create_under_root:
        pastas = _subpastas_da_raiz(draft.root)
    else:
        pastas = {
            "up": Path(draft.up).expanduser(),
            "neutral": Path(draft.neutral).expanduser(),
            "down": Path(draft.down).expanduser(),
        }
    pastas["inbox"] = Path(draft.inbox).expanduser()
    return pastas


def validate_settings(draft: SettingsDraft) -> list[SettingsError]:
    """Valida sem tocar no disco alem de perguntar se um caminho existe.

    Quem cria pasta e apply_draft, chamada so depois disto passar. A
    separacao e o que permite validar a cada tecla digitada no formulario
    sem criar uma pasta a cada tecla digitada.
    """
    erros: list[SettingsError] = []

    if not draft.inbox.strip():
        erros.append(SettingsError("inbox", "Escolha a pasta de entrada."))
    elif not Path(draft.inbox).expanduser().is_dir():
        erros.append(SettingsError("inbox", "Esta pasta nao existe."))

    if draft.create_under_root:
        if not draft.root.strip():
            erros.append(SettingsError("root", "Escolha onde criar a estrutura."))
        elif not Path(draft.root).expanduser().is_dir():
            erros.append(SettingsError("root", "Esta pasta nao existe."))
    else:
        for chave, valor in (("up", draft.up), ("neutral", draft.neutral), ("down", draft.down)):
            if not valor.strip():
                erros.append(SettingsError(chave, "Escolha a pasta de destino."))
            elif not Path(valor).expanduser().is_dir():
                erros.append(SettingsError(chave, "Esta pasta nao existe."))

    if erros:
        # Sem os quatro caminhos resolvidos, checar repeticao produziria
        # ruido em cima de erro que o usuario ja esta vendo.
        return erros

    # Duas chaves apontando para a mesma pasta e falha silenciosa, nao
    # ruidosa: decidir "neutra" com inbox == neutral manda apply mover o
    # arquivo para dentro da propria pasta, e o os.open(O_CREAT|O_EXCL) de
    # _destino_livre responde reservando um nome novo -- o usuario ganha uma
    # copia duplicada e nenhuma mensagem.
    vistos: dict[Path, str] = {}
    for chave, caminho in _caminhos_do_draft(draft).items():
        resolvido = caminho.resolve()
        anterior = vistos.get(resolvido)
        if anterior is not None:
            # NOMES_DE_EXIBICAO, nao a chave crua: "up"/"neutral"/"down"/
            # "inbox" nao aparecem em nenhuma tela -- os rotulos que o
            # usuario ve sao "+1"/"neutra"/"-1"/"entrada" (NOMES_DE_PASTA e
            # _TITULOS em settings_form.py). Vazar a chave interna aqui
            # apareceria em tres telas (FirstRunDialog, SettingsTab,
            # SettingsForm), todas mostrando esta mensagem.
            erros.append(
                SettingsError(
                    chave,
                    f"Esta e a mesma pasta de '{NOMES_DE_EXIBICAO[anterior]}'. "
                    "Use pastas distintas.",
                )
            )
        else:
            vistos[resolvido] = chave

    return erros


def apply_draft(draft: SettingsDraft, config_path: Path) -> Config:
    """Materializa o rascunho: cria as pastas do modo raiz e devolve Config.

    So deve ser chamada depois de validate_settings devolver lista vazia --
    nao revalida.

    `config_path` e o arquivo de configuracao para onde o Config resultante
    sera gravado (save_config, chamada logo em seguida pelos dois lugares
    que chamam esta funcao) -- necessario para resolver um data_dir vazio ou
    relativo do MESMO jeito que load_config faria ao reler esse arquivo.
    Sem isto o default virava relativo ao cwd do processo: um `.app` aberto
    pelo Finder tem cwd "/", entao criar ".trackclassifier" ali estoura
    PermissionError direto dentro do confirmar()/salvar() do dialogo -- e
    mesmo com cwd gravavel, ".trackclassifier" relativo ao cwd nunca e a
    pasta que load_config acha (que resolve relativo ao PAI do arquivo de
    config), entao o proprio round-trip apply_draft -> save_config ->
    load_config discordava de onde ficava a pasta.
    """
    pastas = _caminhos_do_draft(draft)
    if draft.create_under_root:
        for chave in NOMES_DE_PASTA:
            # exist_ok: reabrir a configuracao no modo raiz nao pode falhar
            # so porque a pasta foi criada na vez anterior.
            pastas[chave].mkdir(parents=True, exist_ok=True)

    data_dir = Path(draft.data_dir or ".trackclassifier").expanduser()
    if not data_dir.is_absolute():
        # Mesma regra de load_config: relativo ao PAI do arquivo de config,
        # nao ao cwd do processo.
        data_dir = Path(config_path).parent / data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        folders={
            Label.UP: pastas["up"],
            Label.NEUTRAL: pastas["neutral"],
            Label.DOWN: pastas["down"],
        },
        inbox=pastas["inbox"],
        data_dir=data_dir,
        retrain_every=draft.retrain_every,
        min_examples=draft.min_examples,
    )
