import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import tomli_w

from .labels import Label


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Profile:
    inbox: Path
    folders: dict[Label, Path]


@dataclass(frozen=True)
class Config:
    profiles: dict[str, Profile]
    active_profile: str
    data_dir: Path
    retrain_every: int
    min_examples: int
    auto_move_enabled: bool = False
    #: Persistido para o toggle "Criar pastas automaticamente" da web
    #: sobreviver ao apply. No SettingsDraft o mesmo nome e um MODO de
    #: formulario (raiz vs pastas explicitas), sempre False ao reler o TOML;
    #: aqui e so uma preferencia do modelo, sem efeito no modo raiz.
    create_under_root: bool = False

    @property
    def folders(self) -> dict[Label, Path]:
        return self.profiles[self.active_profile].folders

    @property
    def inbox(self) -> Path:
        return self.profiles[self.active_profile].inbox

    @classmethod
    def from_folders(
        cls,
        folders: dict[Label, Path],
        inbox: Path,
        data_dir: Path,
        retrain_every: int,
        min_examples: int,
        auto_move_enabled: bool = False,
        create_under_root: bool = False,
    ) -> "Config":
        """Construtor de compatibilidade para codigo antigo que ainda passa
        folders/inbox diretamente."""
        perfil = Profile(inbox=inbox, folders=folders)
        return cls(
            profiles={"default": perfil},
            active_profile="default",
            data_dir=data_dir,
            retrain_every=retrain_every,
            min_examples=min_examples,
            auto_move_enabled=auto_move_enabled,
            create_under_root=create_under_root,
        )


_KEY_TO_LABEL = {"up": Label.UP, "neutral": Label.NEUTRAL, "down": Label.DOWN}


def _resolve_dir(folders_raw: dict, key: str) -> Path:
    if key not in folders_raw:
        raise ConfigError(f"Chave obrigatoria ausente: {key}")
    folder = Path(folders_raw[key]).expanduser()
    if not folder.is_dir():
        raise ConfigError(f"Pasta configurada nao existe: {folder}")
    return folder


def _profile_from_raw(name: str, profile_raw: dict) -> Profile:
    pastas = _tabela(profile_raw, "folders")
    folders: dict[Label, Path] = {}
    for key, label in _KEY_TO_LABEL.items():
        folders[label] = _resolve_dir(pastas, key)
    inbox = _resolve_dir(pastas, "inbox")
    return Profile(inbox=inbox, folders=folders)


def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Arquivo de configuracao nao encontrado: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    perfis_raw = _tabela(raw, "profiles")
    if perfis_raw:
        profiles = {name: _profile_from_raw(name, p) for name, p in perfis_raw.items()}
        active_profile = raw.get("active_profile", "default")
        if active_profile not in profiles:
            active_profile = next(iter(profiles))
    else:
        folders_raw = raw.get("folders", {})
        folders: dict[Label, Path] = {}
        for key, label in _KEY_TO_LABEL.items():
            folders[label] = _resolve_dir(folders_raw, key)
        inbox = _resolve_dir(folders_raw, "inbox")
        profiles = {"default": Profile(inbox=inbox, folders=folders)}
        active_profile = "default"

    data_dir = Path(raw.get("paths", {}).get("data_dir", ".trackclassifier")).expanduser()
    if not data_dir.is_absolute():
        data_dir = path.parent / data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    model_raw = raw.get("model", {})
    return Config(
        profiles=profiles,
        active_profile=active_profile,
        data_dir=data_dir,
        retrain_every=_grampeado(int(model_raw.get("retrain_every", _RETRAIN_PADRAO))),
        min_examples=_grampeado(int(model_raw.get("min_examples", _MIN_EXEMPLOS_PADRAO))),
        auto_move_enabled=bool(model_raw.get("auto_move_enabled", False)),
        create_under_root=bool(model_raw.get("create_under_root", False)),
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
        "active_profile": config.active_profile,
        "profiles": {
            name: {
                # inbox dentro de folders, nao no nivel do perfil: e onde
                # _profile_from_raw (e o formato legado [folders]) procura.
                # Gravar no nivel do perfil quebrava o round-trip com
                # "Chave obrigatoria ausente: inbox".
                "folders": {
                    "inbox": str(profile.inbox),
                    "up": str(profile.folders[Label.UP]),
                    "neutral": str(profile.folders[Label.NEUTRAL]),
                    "down": str(profile.folders[Label.DOWN]),
                },
            }
            for name, profile in config.profiles.items()
        },
        "model": {
            "retrain_every": config.retrain_every,
            "min_examples": config.min_examples,
            "auto_move_enabled": config.auto_move_enabled,
            "create_under_root": config.create_under_root,
        },
        "paths": {"data_dir": str(config.data_dir)},
    }
    with path.open("wb") as handle:
        tomli_w.dump(dados, handle)


#: Nome exibido na tela para cada chave interna de campo -- usado para a
#: mensagem de "mesma pasta" em validate_settings nao vazar vocabulario
#: interno (up/neutral/down/inbox/data_dir) que nenhuma tela usa. Os rotulos
#: de up/neutral/down sao os mesmos da tela e dos atalhos 1/2/3.
NOMES_DE_EXIBICAO: Final = {
    "up": "+1",
    "neutral": "neutra",
    "down": "-1",
    "inbox": "entrada",
    "data_dir": "dados do app",
}

_RETRAIN_PADRAO: Final = 10
_MIN_EXEMPLOS_PADRAO: Final = 15

#: Faixa aceita pelos dois campos numericos da secao Modelo, aplicada na
#: fonte (load_config e SettingsDraft.from_raw) pra nao existirem duas fontes
#: da verdade sobre o limite. O minimo NAO e
#: livre: service._conta_decisao soma 1 a cada decisao e retreina quando o
#: contador bate retrain_every; com retrain_every <= 0 essa comparacao vale
#: SEMPRE, entao o modelo (RidgeCV + LeaveOneOut) reajusta a cada decisao
#: em vez de a cada N. min_examples <= 0 e mais brando -- so desliga o
#: aviso de baixa confianca em model.py -- mas nao ha razao pra abrir a
#: porta so pra um dos dois.
MODELO_MINIMO: Final = 1
MODELO_MAXIMO: Final = 1000


def _grampeado(numero: int) -> int:
    """Prende numero em [MODELO_MINIMO, MODELO_MAXIMO].

    Sem isto um config.toml editado a mao com retrain_every = 0 atravessava
    SettingsDraft/Config inteiro e fazia o modelo retreinar a cada decisao.
    A faixa vale na fonte, nos dois pontos de entrada (load_config e
    SettingsDraft.from_raw), antes de qualquer tela.
    """
    return max(MODELO_MINIMO, min(MODELO_MAXIMO, numero))


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
    #: Toggle "Mover arquivos apos classificacao". Persistido em
    #: [model.auto_move_enabled]; sem le-lo aqui o apply gravava False no
    #: TOML a cada salvamento, desligando o comportamento em silencio.
    auto_move_enabled: bool = False
    name: str = "default"

    @classmethod
    def from_raw(cls, raw: dict) -> "SettingsDraft":
        perfis = _tabela(raw, "profiles")
        modelo = _tabela(raw, "model")
        caminhos = _tabela(raw, "paths")
        if perfis:
            nome = raw.get("active_profile", next(iter(perfis)))
            pastas = _tabela(perfis.get(nome, {}), "folders")
            name = nome
        else:
            pastas = _tabela(raw, "folders")
            name = "default"
        return cls(
            inbox=str(pastas.get("inbox", "")),
            up=str(pastas.get("up", "")),
            neutral=str(pastas.get("neutral", "")),
            down=str(pastas.get("down", "")),
            data_dir=str(caminhos.get("data_dir", "")),
            retrain_every=_grampeado(_inteiro(modelo.get("retrain_every"), _RETRAIN_PADRAO)),
            min_examples=_grampeado(_inteiro(modelo.get("min_examples"), _MIN_EXEMPLOS_PADRAO)),
            auto_move_enabled=bool(modelo.get("auto_move_enabled", False)),
            name=name,
        )


def drafts_from_raw(raw: dict) -> dict[str, SettingsDraft]:
    """Cria um SettingsDraft por perfil a partir do TOML cru.

    Migrado automaticamente: arquivo antigo com [folders] vira um unico
    perfil "default".
    """
    perfis = _tabela(raw, "profiles")
    if perfis:
        modelo = _tabela(raw, "model")
        caminhos = _tabela(raw, "paths")
        drafts: dict[str, SettingsDraft] = {}
        for name, profile_raw in perfis.items():
            pastas = _tabela(profile_raw, "folders")
            drafts[name] = SettingsDraft(
                inbox=str(pastas.get("inbox", "")),
                up=str(pastas.get("up", "")),
                neutral=str(pastas.get("neutral", "")),
                down=str(pastas.get("down", "")),
                data_dir=str(caminhos.get("data_dir", "")),
                retrain_every=_grampeado(_inteiro(modelo.get("retrain_every"), _RETRAIN_PADRAO)),
                min_examples=_grampeado(_inteiro(modelo.get("min_examples"), _MIN_EXEMPLOS_PADRAO)),
                auto_move_enabled=bool(modelo.get("auto_move_enabled", False)),
                name=name,
            )
        return drafts
    return {"default": SettingsDraft.from_raw(raw)}


@dataclass(frozen=True)
class SettingsError:
    """Erro amarrado a um campo do formulario, nao a uma caixa modal.

    `field` e uma das chaves: inbox, up, neutral, down, data_dir.
    """

    field: str
    message: str


def _caminhos_do_draft(draft: SettingsDraft) -> dict[str, Path]:
    """Os quatro destinos finais, ja resolvidos."""
    return {
        "up": Path(draft.up).expanduser(),
        "neutral": Path(draft.neutral).expanduser(),
        "down": Path(draft.down).expanduser(),
        "inbox": Path(draft.inbox).expanduser(),
    }


def validate_settings(draft: SettingsDraft) -> list[SettingsError]:
    """Valida sem tocar no disco alem de perguntar se um caminho existe.

    Quem cria pasta e apply_all_drafts, chamada so depois disto passar. A
    separacao e o que permite validar a cada tecla digitada no formulario
    sem criar uma pasta a cada tecla digitada.
    """
    erros: list[SettingsError] = []

    if not draft.inbox.strip():
        erros.append(SettingsError("inbox", "Escolha a pasta de entrada."))
    elif not Path(draft.inbox).expanduser().is_dir():
        erros.append(SettingsError("inbox", "Esta pasta nao existe."))

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
            # usuario ve sao "+1"/"neutra"/"-1"/"entrada". Vazar a chave
            # interna aqui apareceria na tela de Configuracao, que mostra
            # esta mensagem como veio.
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


def apply_all_drafts(
    drafts: dict[str, SettingsDraft],
    active_profile: str,
    config_path: Path,
    create_under_root: bool = False,
) -> Config:
    """Materializa todos os rascunhos e devolve o Config multi-perfil.

    So deve ser chamada depois de validate_settings devolver lista vazia para
    o perfil ativo.

    `config_path` e o arquivo para onde o Config resultante sera gravado
    (save_config, chamada logo em seguida) e resolve um data_dir vazio ou
    relativo contra o PAI dele, do MESMO jeito que load_config faria ao reler
    esse arquivo. Sem isto o default virava relativo ao cwd do processo: um
    app aberto pelo Finder tem cwd "/", entao criar ".trackclassifier" ali
    estoura PermissionError -- e mesmo com cwd gravavel, o round-trip
    apply_all_drafts -> save_config -> load_config discordaria de onde fica
    a pasta.

    `create_under_root` e o toggle "Criar pastas automaticamente" persistido
    pela web em [model.create_under_root]: preferencia do modelo. Nao vem do
    draft, que nao carrega esse campo.
    """
    profiles: dict[str, Profile] = {}
    for name, draft in drafts.items():
        pastas = _caminhos_do_draft(draft)
        profiles[name] = Profile(
            inbox=pastas["inbox"],
            folders={
                Label.UP: pastas["up"],
                Label.NEUTRAL: pastas["neutral"],
                Label.DOWN: pastas["down"],
            },
        )

    ref = drafts[active_profile]
    data_dir = Path(ref.data_dir or ".trackclassifier").expanduser()
    if not data_dir.is_absolute():
        data_dir = Path(config_path).parent / data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        profiles=profiles,
        active_profile=active_profile,
        data_dir=data_dir,
        retrain_every=ref.retrain_every,
        min_examples=ref.min_examples,
        auto_move_enabled=ref.auto_move_enabled,
        create_under_root=create_under_root,
    )
