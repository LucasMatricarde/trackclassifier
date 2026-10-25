import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

import tomli_w

from .labels import Label


class ConfigError(Exception):
    pass


_RETRAIN_PADRAO: Final = 10
_MIN_EXEMPLOS_PADRAO: Final = 15

#: Id e nome do perfil que a migracao cria a partir do config antigo. O id e
#: o que o torna imexivel (nao se exclui): o nome pode ser renomeado.
PERFIL_PADRAO_ID: Final = "default"
PERFIL_PADRAO_NOME: Final = "Padrão"


@dataclass(frozen=True)
class Profile:
    """Um fluxo de trabalho: pastas, organizacao e parametros do modelo.

    So data_dir/cache/capas ficam fora (sao do app, em Config). `inbox` None e
    `folders` vazio = perfil INCOMPLETO: nasce assim quando se cria um perfil
    sem copiar as pastas. Nao e invalido -- o scan e a fila o ignoram e o
    erro de pasta aparece na validacao quando a pessoa o abre na Configuracao.
    """

    inbox: Path | None
    folders: dict[Label, Path]
    #: Nome de exibicao (a chave em Config.profiles e o id, imutavel). Vazio
    #: cai no proprio id (ver display_name): configs e testes antigos nao
    #: tinham nome.
    name: str = ""
    retrain_every: int = _RETRAIN_PADRAO
    min_examples: int = _MIN_EXEMPLOS_PADRAO
    #: Os tres toggles da secao Organizacao sao so persistidos por perfil: o
    #: decide continua sempre movendo (ligar isso e outra mudanca).
    auto_move_enabled: bool = False
    create_under_root: bool = False
    keep_copy: bool = False

    @property
    def complete(self) -> bool:
        return self.inbox is not None and all(
            label in self.folders for label in _KEY_TO_LABEL.values()
        )


@dataclass(frozen=True)
class Config:
    profiles: dict[str, Profile]
    active_profile: str
    data_dir: Path

    @property
    def profile(self) -> Profile:
        return self.profiles[self.active_profile]

    @property
    def folders(self) -> dict[Label, Path]:
        return self.profile.folders

    @property
    def inbox(self) -> Path | None:
        return self.profile.inbox

    # Modelo e organizacao sao do PERFIL ativo: o servico le `config.retrain_every`
    # sem saber de perfis, e trocar de perfil troca a cadencia junto.
    @property
    def retrain_every(self) -> int:
        return self.profile.retrain_every

    @property
    def min_examples(self) -> int:
        return self.profile.min_examples

    @property
    def auto_move_enabled(self) -> bool:
        return self.profile.auto_move_enabled

    @property
    def create_under_root(self) -> bool:
        return self.profile.create_under_root

    @property
    def keep_copy(self) -> bool:
        return self.profile.keep_copy

    def with_profile(self, key: str, **mudancas) -> "Config":
        """Copia com o perfil `key` alterado (Config e frozen)."""
        perfis = dict(self.profiles)
        perfis[key] = replace(perfis[key], **mudancas)
        return replace(self, profiles=perfis)

    def with_active_settings(self, **mudancas) -> "Config":
        return self.with_profile(self.active_profile, **mudancas)

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
        perfil = Profile(
            inbox=inbox,
            folders=folders,
            name=PERFIL_PADRAO_NOME,
            retrain_every=retrain_every,
            min_examples=min_examples,
            auto_move_enabled=auto_move_enabled,
            create_under_root=create_under_root,
        )
        return cls(
            profiles={PERFIL_PADRAO_ID: perfil},
            active_profile=PERFIL_PADRAO_ID,
            data_dir=data_dir,
        )


_KEY_TO_LABEL = {"up": Label.UP, "neutral": Label.NEUTRAL, "down": Label.DOWN}


def _resolve_dir(folders_raw: dict, key: str) -> Path:
    if key not in folders_raw:
        raise ConfigError(f"Chave obrigatoria ausente: {key}")
    folder = Path(folders_raw[key]).expanduser()
    if not folder.is_dir():
        raise ConfigError(f"Pasta configurada nao existe: {folder}")
    return folder


_CHAVES_DE_PASTA = ("inbox", "up", "neutral", "down")


def _ajustes_do_perfil(profile_raw: dict, raw: dict) -> dict:
    """Modelo e organizacao de um perfil, com heranca do [model] global.

    O formato antigo guardava retrain_every/min_examples/auto_move_enabled/
    create_under_root num [model] unico. Perfil sem a propria tabela herda
    esses valores (e a migracao: o config de hoje vira o perfil "Padrao" sem
    perder nada); com a tabela propria, ela manda chave a chave.
    """
    global_modelo = _tabela(raw, "model")
    modelo = _tabela(profile_raw, "model")
    org = _tabela(profile_raw, "organization")
    return {
        "retrain_every": _grampeado(
            _inteiro(
                modelo.get("retrain_every", global_modelo.get("retrain_every")),
                _RETRAIN_PADRAO,
            )
        ),
        "min_examples": _grampeado(
            _inteiro(
                modelo.get("min_examples", global_modelo.get("min_examples")),
                _MIN_EXEMPLOS_PADRAO,
            )
        ),
        "create_under_root": bool(
            org.get("create", global_modelo.get("create_under_root", False))
        ),
        "auto_move_enabled": bool(org.get("move", global_modelo.get("auto_move_enabled", False))),
        "keep_copy": bool(org.get("copy", False)),
    }


def _nome_do_perfil(key: str, profile_raw: dict) -> str:
    nome = str(profile_raw.get("name", "")).strip()
    if nome:
        return nome
    return PERFIL_PADRAO_NOME if key == PERFIL_PADRAO_ID else key


def _pastas_vazias(pastas: dict) -> bool:
    return not any(str(pastas.get(chave, "")).strip() for chave in _CHAVES_DE_PASTA)


def _profile_from_raw(
    key: str, profile_raw: dict, raw: dict, permite_incompleto: bool = True
) -> Profile:
    pastas = _tabela(profile_raw, "folders")
    ajustes = _ajustes_do_perfil(profile_raw, raw)
    nome = _nome_do_perfil(key, profile_raw)
    if permite_incompleto and _pastas_vazias(pastas):
        # Perfil incompleto (criado sem copiar pastas): carrega, nao e erro.
        return Profile(inbox=None, folders={}, name=nome, **ajustes)
    folders: dict[Label, Path] = {}
    for chave, label in _KEY_TO_LABEL.items():
        folders[label] = _resolve_dir(pastas, chave)
    inbox = _resolve_dir(pastas, "inbox")
    return Profile(inbox=inbox, folders=folders, name=nome, **ajustes)


def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Arquivo de configuracao nao encontrado: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    perfis_raw = _tabela(raw, "profiles")
    if perfis_raw:
        profiles = {
            key: _profile_from_raw(key, _tabela(perfis_raw, key), raw) for key in perfis_raw
        }
        active_profile = raw.get("active_profile", PERFIL_PADRAO_ID)
        if active_profile not in profiles:
            active_profile = next(iter(profiles))
    else:
        # Migracao: o config antigo ([folders] + [model] globais) vira o
        # perfil "Padrao". So le -- a proxima gravacao ja sai no formato novo.
        # Sem perfis E sem pastas e o config quebrado de sempre: nao ha
        # perfil incompleto aqui, entao a chave que falta e reportada.
        profiles = {
            PERFIL_PADRAO_ID: _profile_from_raw(
                PERFIL_PADRAO_ID,
                {"folders": raw.get("folders", {})},
                raw,
                permite_incompleto=False,
            )
        }
        active_profile = PERFIL_PADRAO_ID

    data_dir = Path(raw.get("paths", {}).get("data_dir", ".trackclassifier")).expanduser()
    if not data_dir.is_absolute():
        data_dir = path.parent / data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    return Config(profiles=profiles, active_profile=active_profile, data_dir=data_dir)


def _profile_para_toml(profile: Profile, key: str) -> dict:
    pastas = {}
    if profile.complete:
        # inbox dentro de folders, nao no nivel do perfil: e onde
        # _profile_from_raw (e o formato legado [folders]) procura.
        # Gravar no nivel do perfil quebrava o round-trip com
        # "Chave obrigatoria ausente: inbox".
        pastas = {
            "inbox": str(profile.inbox),
            "up": str(profile.folders[Label.UP]),
            "neutral": str(profile.folders[Label.NEUTRAL]),
            "down": str(profile.folders[Label.DOWN]),
        }
    return {
        "name": profile.name or key,
        "folders": pastas,
        "model": {
            "retrain_every": profile.retrain_every,
            "min_examples": profile.min_examples,
        },
        "organization": {
            "create": profile.create_under_root,
            "move": profile.auto_move_enabled,
            "copy": profile.keep_copy,
        },
    }


def save_config(path: Path, config: Config) -> None:
    """Grava o Config como TOML, criando o diretorio-pai se faltar.

    Usa tomli_w em vez de montar a string a mao: um caminho com aspas ou
    apostrofo -- "DJ's Tracks" e comum num acervo real -- exige escape de
    string basica TOML, e o erro nao aparece na gravacao, so na leitura
    seguinte, com o caminho silenciosamente errado.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ativo = config.profile
    dados = {
        "active_profile": config.active_profile,
        "profiles": {key: _profile_para_toml(p, key) for key, p in config.profiles.items()},
        # Espelho do perfil ativo no [model] global do formato antigo: quem
        # le o arquivo com uma versao anterior do app segue vendo valores
        # coerentes, e a leitura nova so o usa para perfil sem tabela propria.
        "model": {
            "retrain_every": ativo.retrain_every,
            "min_examples": ativo.min_examples,
            "auto_move_enabled": ativo.auto_move_enabled,
            "create_under_root": ativo.create_under_root,
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
    #: Chave (id) do perfil em Config.profiles.
    name: str = PERFIL_PADRAO_ID
    #: Toggles "Criar pastas automaticamente" e "Manter uma copia" do perfil
    #: (mesmo nome do `Profile.create_under_root`).
    create_under_root: bool = False
    keep_copy: bool = False
    #: Nome de exibicao; vazio cai na chave.
    display_name: str = ""

    @classmethod
    def from_raw(cls, raw: dict) -> "SettingsDraft":
        perfis = _tabela(raw, "profiles")
        if perfis:
            nome = raw.get("active_profile", next(iter(perfis)))
            return _draft_do_perfil(nome, _tabela(perfis, nome), raw)
        return _draft_do_perfil(
            PERFIL_PADRAO_ID,
            {"folders": _tabela(raw, "folders"), "organization": _tabela(raw, "organization")},
            raw,
        )


def _draft_do_perfil(key: str, profile_raw: dict, raw: dict) -> SettingsDraft:
    pastas = _tabela(profile_raw, "folders")
    caminhos = _tabela(raw, "paths")
    ajustes = _ajustes_do_perfil(profile_raw, raw)
    return SettingsDraft(
        inbox=str(pastas.get("inbox", "")),
        up=str(pastas.get("up", "")),
        neutral=str(pastas.get("neutral", "")),
        down=str(pastas.get("down", "")),
        data_dir=str(caminhos.get("data_dir", "")),
        retrain_every=ajustes["retrain_every"],
        min_examples=ajustes["min_examples"],
        auto_move_enabled=ajustes["auto_move_enabled"],
        name=key,
        create_under_root=ajustes["create_under_root"],
        keep_copy=ajustes["keep_copy"],
        display_name=_nome_do_perfil(key, profile_raw),
    )


def drafts_from_raw(raw: dict) -> dict[str, SettingsDraft]:
    """Cria um SettingsDraft por perfil a partir do TOML cru.

    Migrado automaticamente: arquivo antigo com [folders] vira um unico
    perfil "default" (nome "Padrao"). Modelo e organizacao saem de CADA
    perfil, com heranca do [model] global para perfil sem tabela propria.
    """
    perfis = _tabela(raw, "profiles")
    if perfis:
        return {key: _draft_do_perfil(key, _tabela(perfis, key), raw) for key in perfis}
    return {PERFIL_PADRAO_ID: SettingsDraft.from_raw(raw)}


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
    """
    profiles: dict[str, Profile] = {}
    for name, draft in drafts.items():
        ajustes = {
            "name": draft.display_name or name,
            "retrain_every": draft.retrain_every,
            "min_examples": draft.min_examples,
            "auto_move_enabled": draft.auto_move_enabled,
            "create_under_root": draft.create_under_root,
            "keep_copy": draft.keep_copy,
        }
        textos = (draft.inbox, draft.up, draft.neutral, draft.down)
        if not any(t.strip() for t in textos):
            # Perfil incompleto: path "" viraria "." (o cwd) -- nunca o
            # materialize como pasta.
            profiles[name] = Profile(inbox=None, folders={}, **ajustes)
            continue
        if not all(t.strip() for t in textos):
            raise ConfigError(f"Perfil {draft.display_name or name}: faltam pastas.")
        pastas = _caminhos_do_draft(draft)
        profiles[name] = Profile(
            inbox=pastas["inbox"],
            folders={
                Label.UP: pastas["up"],
                Label.NEUTRAL: pastas["neutral"],
                Label.DOWN: pastas["down"],
            },
            **ajustes,
        )

    ref = drafts[active_profile]
    data_dir = Path(ref.data_dir or ".trackclassifier").expanduser()
    if not data_dir.is_absolute():
        data_dir = Path(config_path).parent / data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    return Config(profiles=profiles, active_profile=active_profile, data_dir=data_dir)
