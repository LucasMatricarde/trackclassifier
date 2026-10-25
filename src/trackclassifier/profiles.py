"""Operacoes sobre os perfis de um Config: criar, renomear, duplicar, excluir.

Funcoes puras (Config entra, Config sai), sem disco e sem servico: quem chama
(serve.py) persiste com save_config e entrega o resultado ao TrackService.
Assim a regra -- nome unico, "Padrao" nao sai, excluir o ativo passa para o
proximo -- fica testavel sem subir nada.

A chave em Config.profiles e o ID: slug do nome na criacao e imutavel depois.
Renomear so troca `Profile.name`, entao TrackRef.profile, _UltimaDecisao.profile
e o resto do estado em memoria (que guardam o id) nao precisam ser re-chaveados.
"""

import re
import unicodedata
from dataclasses import replace

from .config import PERFIL_PADRAO_ID, Config, Profile
from .labels import Label

NOME_MAXIMO = 60


class ProfileError(ValueError):
    """Violacao de regra de perfil; a mensagem vai direto para a tela."""


def slug(nome: str) -> str:
    """'Set Trance' -> 'set-trance'. ASCII, para o id viver bem em TOML e URL."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    limpo = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
    return limpo or "perfil"


def novo_id(nome: str, existentes) -> str:
    """Slug do nome, com sufixo -2, -3... quando o id ja existe."""
    base = slug(nome)
    candidato, n = base, 2
    while candidato in existentes:
        candidato = f"{base}-{n}"
        n += 1
    return candidato


def nome_de(key: str, profile: Profile) -> str:
    return profile.name or key


def validar_nome(nome: str, config: Config, ignorar_id: str | None = None) -> str:
    """Devolve o nome limpo ou levanta ProfileError (vazio, longo, repetido).

    A comparacao ignora caixa e espacos repetidos: "Padrao" e " padrao " sao
    o mesmo nome. E o que o dropdown e a pill da Revisao (que trocam por
    nome) precisam para nunca ficarem ambiguos.
    """
    limpo = " ".join(nome.split())
    if not limpo:
        raise ProfileError("Informe um nome para o perfil.")
    if len(limpo) > NOME_MAXIMO:
        raise ProfileError(f"O nome do perfil aceita até {NOME_MAXIMO} caracteres.")
    chave = limpo.casefold()
    for key, profile in config.profiles.items():
        if key != ignorar_id and nome_de(key, profile).casefold() == chave:
            raise ProfileError("Já existe um perfil com esse nome.")
    return limpo


def resolver(config: Config, ref: str) -> str | None:
    """Id a partir de um id OU de um nome (a pill da Revisao troca por nome)."""
    if ref in config.profiles:
        return ref
    alvo = ref.strip().casefold()
    for key, profile in config.profiles.items():
        if nome_de(key, profile).casefold() == alvo:
            return key
    return None


def _exige(config: Config, key: str) -> Profile:
    if key not in config.profiles:
        raise KeyError(f"Perfil desconhecido: {key}")
    return config.profiles[key]


def criar(config: Config, nome: str, copiar_pastas: bool) -> tuple[Config, str]:
    """Perfil novo, que vira o ativo. Devolve (config, id do novo).

    Modelo e organizacao partem dos do perfil ativo (ponto de partida mais
    util que os defaults). Sem `copiar_pastas` nasce INCOMPLETO: nao ha pasta
    sensata para inventar, e o config segue carregando.
    """
    nome = validar_nome(nome, config)
    base = config.profile
    key = novo_id(nome, config.profiles)
    perfil = replace(
        base,
        name=nome,
        inbox=base.inbox if copiar_pastas else None,
        folders=dict(base.folders) if copiar_pastas else {},
    )
    perfis = dict(config.profiles)
    perfis[key] = perfil
    return replace(config, profiles=perfis, active_profile=key), key


def renomear(config: Config, key: str, nome: str) -> Config:
    _exige(config, key)
    nome = validar_nome(nome, config, ignorar_id=key)
    return config.with_profile(key, name=nome)


def duplicar(config: Config, key: str) -> tuple[Config, str]:
    """Copia completa (pastas inclusive), SEM ativar. Devolve (config, id)."""
    original = _exige(config, key)
    base = f"{nome_de(key, original)} (cópia)"
    nome, n = base, 2
    while True:
        try:
            nome = validar_nome(nome, config)
            break
        except ProfileError:
            nome = f"{base} {n}"
            n += 1
    novo = novo_id(nome, config.profiles)
    perfis = dict(config.profiles)
    perfis[novo] = replace(original, name=nome, folders=dict(original.folders))
    return replace(config, profiles=perfis), novo


def excluir(config: Config, key: str) -> Config:
    """Remove o perfil. Excluir o ativo passa para o proximo da lista (ou o
    anterior, se era o ultimo). O "Padrao" e o ultimo perfil nao saem."""
    _exige(config, key)
    if key == PERFIL_PADRAO_ID:
        raise ProfileError("O perfil Padrão não pode ser excluído.")
    if len(config.profiles) <= 1:
        raise ProfileError("O único perfil não pode ser excluído.")
    chaves = list(config.profiles)
    indice = chaves.index(key)
    perfis = {k: p for k, p in config.profiles.items() if k != key}
    ativo = config.active_profile
    if ativo == key:
        restantes = list(perfis)
        ativo = restantes[min(indice, len(restantes) - 1)]
    return replace(config, profiles=perfis, active_profile=ativo)


def ativar(config: Config, key: str) -> Config:
    _exige(config, key)
    return replace(config, active_profile=key)


def para_json(config: Config) -> dict:
    """Formato de /api/profiles. `all` (so ids) mantem o consumidor antigo."""
    return {
        "active": config.active_profile,
        "all": list(config.profiles),
        "profiles": [_perfil_json(key, p) for key, p in config.profiles.items()],
    }


def _perfil_json(key: str, p: Profile) -> dict:
    def pasta(label: Label) -> str:
        caminho = p.folders.get(label)
        return str(caminho) if caminho is not None else ""

    return {
        "id": key,
        "name": nome_de(key, p),
        "inputDir": str(p.inbox) if p.inbox is not None else "",
        "destDirs": {
            "-1": pasta(Label.DOWN),
            "neutra": pasta(Label.NEUTRAL),
            "+1": pasta(Label.UP),
        },
        "orgToggles": {
            "create": p.create_under_root,
            "move": p.auto_move_enabled,
            "copy": p.keep_copy,
        },
        "model": {"retrainEvery": p.retrain_every, "minPerClass": p.min_examples},
        "complete": p.complete,
    }
