"""Perfis com configuracoes independentes: operacoes puras (profiles.py),
migracao/ida e volta do config.toml e o efeito no servico.

O CRUD via HTTP fica em test_serve.py; aqui entram as regras que valem sem
servidor (nome unico, "Padrao" nao sai, excluir o ativo passa para o proximo)
e as que so o disco prova (migracao do config antigo, perfil incompleto).
"""

import pytest

from tests.test_service import ExtratorFalso, _config, _povoa
from trackclassifier.config import (
    PERFIL_PADRAO_ID,
    PERFIL_PADRAO_NOME,
    Config,
    ConfigError,
    Profile,
    drafts_from_raw,
    load_config,
    read_raw,
    save_config,
)
from trackclassifier.labels import Label
from trackclassifier.profiles import (
    ProfileError,
    ativar,
    criar,
    duplicar,
    excluir,
    nome_de,
    novo_id,
    para_json,
    renomear,
    resolver,
    slug,
    validar_nome,
)
from trackclassifier.service import TrackService


def _base(tmp_path) -> Config:
    return _config(tmp_path)


# ---------------------------------------------------------------------------
# slug / id / nome
# ---------------------------------------------------------------------------


def test_slug_tira_acento_e_espaco():
    assert slug("Set Trance") == "set-trance"
    assert slug("Produções  2024!") == "producoes-2024"
    assert slug("???") == "perfil"


def test_novo_id_acrescenta_sufixo_quando_repete():
    assert novo_id("Festa", {"festa": 1, "festa-2": 1}) == "festa-3"
    assert novo_id("Festa", {}) == "festa"


@pytest.mark.parametrize("nome", ["", "   ", "\t"])
def test_validar_nome_rejeita_vazio(tmp_path, nome):
    with pytest.raises(ProfileError, match="Informe um nome"):
        validar_nome(nome, _base(tmp_path))


def test_validar_nome_rejeita_repetido_sem_olhar_caixa_nem_espaco_extra(tmp_path):
    config = _base(tmp_path)
    for tentativa in ("padrão", "  PADRÃO ", "Padrão"):
        with pytest.raises(ProfileError, match="Já existe"):
            validar_nome(tentativa, config)


def test_validar_nome_aceita_o_proprio_nome_ao_renomear(tmp_path):
    config = _base(tmp_path)
    assert validar_nome("Padrão", config, ignorar_id=PERFIL_PADRAO_ID) == "Padrão"


def test_validar_nome_rejeita_nome_longo(tmp_path):
    with pytest.raises(ProfileError, match="até 60"):
        validar_nome("x" * 61, _base(tmp_path))


def test_validar_nome_normaliza_espacos(tmp_path):
    assert validar_nome("  Set   Trance ", _base(tmp_path)) == "Set Trance"


# ---------------------------------------------------------------------------
# criar / renomear / duplicar / excluir / ativar
# ---------------------------------------------------------------------------


def test_criar_copiando_pastas_ativa_o_novo_e_herda_modelo_e_organizacao(tmp_path):
    config = _base(tmp_path).with_active_settings(
        retrain_every=7, min_examples=3, keep_copy=True, auto_move_enabled=True
    )

    novo, key = criar(config, "Set Trance", copiar_pastas=True)

    assert key == "set-trance"
    assert novo.active_profile == "set-trance"
    perfil = novo.profiles[key]
    assert perfil.name == "Set Trance"
    assert perfil.inbox == config.inbox
    assert perfil.folders == config.folders
    assert (perfil.retrain_every, perfil.min_examples) == (7, 3)
    assert perfil.keep_copy is True and perfil.auto_move_enabled is True
    # O de origem nao muda.
    assert novo.profiles[PERFIL_PADRAO_ID] == config.profiles[PERFIL_PADRAO_ID]


def test_criar_sem_copiar_pastas_nasce_incompleto_e_ativo(tmp_path):
    config = _base(tmp_path)

    novo, key = criar(config, "Vazio", copiar_pastas=False)

    perfil = novo.profiles[key]
    assert novo.active_profile == key
    assert perfil.inbox is None and perfil.folders == {}
    assert perfil.complete is False
    assert config.profiles[PERFIL_PADRAO_ID].complete is True


def test_criar_com_nome_invalido_nao_altera_o_config(tmp_path):
    config = _base(tmp_path)
    with pytest.raises(ProfileError):
        criar(config, "padrão", copiar_pastas=True)
    assert list(config.profiles) == [PERFIL_PADRAO_ID]


def test_renomear_troca_so_o_nome_e_mantem_o_id(tmp_path):
    config, key = criar(_base(tmp_path), "Festa", True)

    novo = renomear(config, key, "Festa 2024")

    assert list(novo.profiles) == list(config.profiles)
    assert novo.profiles[key].name == "Festa 2024"
    assert novo.active_profile == key


def test_renomear_para_nome_de_outro_perfil_falha(tmp_path):
    config, key = criar(_base(tmp_path), "Festa", True)
    with pytest.raises(ProfileError, match="Já existe"):
        renomear(config, key, "Padrão")


def test_renomear_perfil_desconhecido_levanta_keyerror(tmp_path):
    with pytest.raises(KeyError):
        renomear(_base(tmp_path), "nao-existe", "X")


def test_duplicar_copia_tudo_e_nao_ativa(tmp_path):
    config = _base(tmp_path).with_active_settings(retrain_every=9)

    novo, key = duplicar(config, PERFIL_PADRAO_ID)

    assert novo.active_profile == PERFIL_PADRAO_ID
    copia = novo.profiles[key]
    assert copia.name == "Padrão (cópia)"
    assert copia.folders == config.folders and copia.retrain_every == 9
    # Segunda copia nao colide com a primeira.
    de_novo, key2 = duplicar(novo, PERFIL_PADRAO_ID)
    assert de_novo.profiles[key2].name == "Padrão (cópia) 2"
    assert key2 != key


def test_excluir_padrao_e_recusado(tmp_path):
    config, _ = criar(_base(tmp_path), "Festa", True)
    with pytest.raises(ProfileError, match="Padrão não pode"):
        excluir(config, PERFIL_PADRAO_ID)


def test_excluir_o_ativo_passa_para_o_proximo(tmp_path):
    config, a = criar(_base(tmp_path), "Alfa", True)
    config, b = criar(config, "Beta", True)
    config, c = criar(config, "Gama", True)
    config = ativar(config, b)

    novo = excluir(config, b)

    assert b not in novo.profiles
    assert novo.active_profile == c  # o proximo da lista, nao o primeiro


def test_excluir_o_ultimo_da_lista_ativo_passa_para_o_anterior(tmp_path):
    config, a = criar(_base(tmp_path), "Alfa", True)
    config, b = criar(config, "Beta", True)  # ativo e o ultimo

    novo = excluir(config, b)

    assert novo.active_profile == a


def test_excluir_um_inativo_mantem_o_ativo(tmp_path):
    config, a = criar(_base(tmp_path), "Alfa", True)
    config, b = criar(config, "Beta", True)

    novo = excluir(config, a)

    assert novo.active_profile == b and a not in novo.profiles


def test_excluir_o_unico_perfil_nao_padrao_e_recusado():
    pasta = Profile(inbox=None, folders={}, name="Solto")
    config = Config(profiles={"solto": pasta}, active_profile="solto", data_dir=None)
    with pytest.raises(ProfileError, match="único"):
        excluir(config, "solto")


def test_resolver_aceita_id_e_nome(tmp_path):
    config, key = criar(_base(tmp_path), "Set Techno", True)
    assert resolver(config, key) == key
    assert resolver(config, "set techno") == key
    assert resolver(config, "Padrão") == PERFIL_PADRAO_ID
    assert resolver(config, "inexistente") is None


def test_para_json_tem_o_formato_da_api(tmp_path):
    config = _base(tmp_path).with_active_settings(
        retrain_every=7, min_examples=3, keep_copy=True
    )
    config, key = criar(config, "Vazio", copiar_pastas=False)

    dados = para_json(config)

    assert dados["active"] == key
    assert dados["all"] == [PERFIL_PADRAO_ID, key]
    padrao, vazio = dados["profiles"]
    assert padrao["id"] == PERFIL_PADRAO_ID and padrao["name"] == "Padrão"
    assert padrao["inputDir"] == str(config.profiles[PERFIL_PADRAO_ID].inbox)
    assert set(padrao["destDirs"]) == {"-1", "neutra", "+1"}
    assert padrao["destDirs"]["+1"].endswith("up")
    assert padrao["orgToggles"] == {"create": False, "move": False, "copy": True}
    assert padrao["model"] == {"retrainEvery": 7, "minPerClass": 3}
    assert padrao["complete"] is True
    assert vazio["inputDir"] == "" and vazio["destDirs"] == {"-1": "", "neutra": "", "+1": ""}
    assert vazio["complete"] is False


def test_nome_de_cai_no_id_quando_o_perfil_nao_tem_nome():
    assert nome_de("casa", Profile(inbox=None, folders={})) == "casa"


# ---------------------------------------------------------------------------
# config.toml: migracao e ida e volta
# ---------------------------------------------------------------------------


def _toml_legado(tmp_path, modelo="retrain_every = 12\nmin_examples = 4\n"):
    for nome in ("up", "neutral", "down", "inbox"):
        (tmp_path / nome).mkdir(exist_ok=True)
    caminho = tmp_path / "config.toml"
    caminho.write_text(
        f"""
[folders]
up = "{tmp_path / 'up'}"
neutral = "{tmp_path / 'neutral'}"
down = "{tmp_path / 'down'}"
inbox = "{tmp_path / 'inbox'}"

[model]
{modelo}auto_move_enabled = true
create_under_root = true

[paths]
data_dir = "{tmp_path / 'data'}"
""",
        encoding="utf-8",
    )
    return caminho


def test_migracao_config_antigo_vira_o_perfil_padrao(tmp_path):
    config = load_config(_toml_legado(tmp_path))

    assert list(config.profiles) == [PERFIL_PADRAO_ID]
    assert config.active_profile == PERFIL_PADRAO_ID
    perfil = config.profile
    assert perfil.name == PERFIL_PADRAO_NOME
    assert perfil.inbox == tmp_path / "inbox"
    # O [model] global antigo foi parar no perfil, sem perder nada.
    assert (perfil.retrain_every, perfil.min_examples) == (12, 4)
    assert perfil.auto_move_enabled is True and perfil.create_under_root is True
    assert perfil.keep_copy is False


def test_migracao_nao_reescreve_o_arquivo_ate_a_proxima_gravacao(tmp_path):
    caminho = _toml_legado(tmp_path)
    antes = caminho.read_text(encoding="utf-8")

    config = load_config(caminho)
    assert caminho.read_text(encoding="utf-8") == antes

    save_config(caminho, config)
    gravado = read_raw(caminho)
    assert gravado["profiles"]["default"]["name"] == "Padrão"
    assert gravado["profiles"]["default"]["model"] == {"retrain_every": 12, "min_examples": 4}
    assert "folders" not in {k for k in gravado if k != "profiles"}  # tabela legada some


def test_perfil_com_formato_novo_vai_e_volta_com_modelo_e_organizacao_proprios(tmp_path):
    config = _base(tmp_path)
    config, key = criar(config, "Set Trance", copiar_pastas=True)
    config = config.with_active_settings(
        retrain_every=33, min_examples=21, keep_copy=True, create_under_root=True
    )
    destino = tmp_path / "config.toml"
    save_config(destino, config)

    recarregado = load_config(destino)

    assert recarregado.active_profile == key
    padrao = recarregado.profiles[PERFIL_PADRAO_ID]
    novo = recarregado.profiles[key]
    # Independentes: mexer num nao mexeu no outro.
    assert (padrao.retrain_every, padrao.min_examples) == (2, 1)
    assert (novo.retrain_every, novo.min_examples) == (33, 21)
    assert novo.keep_copy is True and padrao.keep_copy is False
    assert novo.create_under_root is True and padrao.create_under_root is False
    assert novo.name == "Set Trance"
    # E as propriedades do Config leem o perfil ativo.
    assert recarregado.retrain_every == 33


def test_perfil_incompleto_carrega_e_volta_incompleto(tmp_path):
    config, key = criar(_base(tmp_path), "Vazio", copiar_pastas=False)
    destino = tmp_path / "config.toml"
    save_config(destino, config)

    recarregado = load_config(destino)

    assert recarregado.profiles[key].complete is False
    assert recarregado.profiles[PERFIL_PADRAO_ID].complete is True


def test_perfil_com_pasta_preenchida_e_inexistente_continua_sendo_erro(tmp_path):
    config = _base(tmp_path)
    destino = tmp_path / "config.toml"
    save_config(destino, config)
    texto = destino.read_text(encoding="utf-8")
    destino.write_text(
        texto.replace(str(tmp_path / "up"), str(tmp_path / "sumiu")), encoding="utf-8"
    )

    with pytest.raises(ConfigError, match="nao existe"):
        load_config(destino)


def test_herda_o_model_global_so_quando_o_perfil_nao_tem_o_proprio(tmp_path):
    for nome in ("up", "neutral", "down", "inbox"):
        (tmp_path / nome).mkdir()
    pastas = (
        f'inbox = "{tmp_path / "inbox"}"\nup = "{tmp_path / "up"}"\n'
        f'neutral = "{tmp_path / "neutral"}"\ndown = "{tmp_path / "down"}"\n'
    )
    caminho = tmp_path / "config.toml"
    caminho.write_text(
        f"""
active_profile = "a"

[model]
retrain_every = 20
min_examples = 8

[profiles.a.folders]
{pastas}
[profiles.b.folders]
{pastas}
[profiles.b.model]
retrain_every = 3

[paths]
data_dir = "{tmp_path / 'data'}"
""",
        encoding="utf-8",
    )

    config = load_config(caminho)

    assert (config.profiles["a"].retrain_every, config.profiles["a"].min_examples) == (20, 8)
    # b tem a propria cadencia, mas herda o minimo (chave a chave).
    assert (config.profiles["b"].retrain_every, config.profiles["b"].min_examples) == (3, 8)
    assert config.profiles["a"].name == "a"  # sem name no TOML: cai no id


def test_drafts_carregam_modelo_e_organizacao_de_cada_perfil(tmp_path):
    config, key = criar(_base(tmp_path), "Festa", True)
    config = config.with_active_settings(retrain_every=44, keep_copy=True)
    destino = tmp_path / "config.toml"
    save_config(destino, config)

    drafts = drafts_from_raw(read_raw(destino))

    assert drafts[PERFIL_PADRAO_ID].retrain_every == 2
    assert drafts[key].retrain_every == 44
    assert drafts[key].keep_copy is True and drafts[PERFIL_PADRAO_ID].keep_copy is False
    assert drafts[key].display_name == "Festa"


# ---------------------------------------------------------------------------
# Servico
# ---------------------------------------------------------------------------


def _servico(config, **kw) -> TrackService:
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1, **kw)
    servico.analyze_all()
    return servico


def test_retreino_usa_a_cadencia_do_perfil_ativo(tmp_path):
    base = _base(tmp_path)  # retrain_every=2
    _povoa(base)
    config, outro = criar(base, "Lento", copiar_pastas=True)
    config = config.with_active_settings(retrain_every=1000)
    config = ativar(config, PERFIL_PADRAO_ID)
    for nome in ("a_0.9.mp3", "b_0.1.mp3"):
        (base.inbox / nome).write_bytes(nome.encode())
    servico = _servico(config)
    servico.train()
    shas = [item.sha1 for item in servico.queue()]

    # No Padrao a cadencia e 2: a segunda decisao retreina.
    assert servico.decide(shas[0], Label.UP) is False
    assert servico.decide(shas[1], Label.DOWN) is True

    # Trocando para o perfil "Lento", a cadencia passa a ser 1000.
    servico.set_config(ativar(servico.config, outro))
    assert servico.config.retrain_every == 1000
    assert servico._decisions_since_train == 0


def test_set_model_settings_grava_so_no_perfil_ativo(tmp_path):
    config, outro = criar(_base(tmp_path), "Outro", copiar_pastas=True)
    config = ativar(config, PERFIL_PADRAO_ID)
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)

    servico.set_model_settings(retrain_every=9, min_examples=4)

    assert servico.config.profiles[PERFIL_PADRAO_ID].retrain_every == 9
    assert servico.config.profiles[outro].retrain_every == 2  # intocado


def test_set_config_nao_zera_a_fila(tmp_path):
    config = _base(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.9.mp3").write_bytes(b"nova")
    servico = _servico(config)
    servico.train()
    assert len(servico.queue()) == 1

    servico.set_config(renomear(config, PERFIL_PADRAO_ID, "Casa"))

    assert len(servico.queue()) == 1  # o refs guardam o id, que nao mudou


def test_scan_ignora_perfil_incompleto_e_reporta_em_failures(tmp_path):
    base = _base(tmp_path)
    _povoa(base)
    (base.inbox / "nova_0.9.mp3").write_bytes(b"nova")
    config, vazio = criar(base, "Vazio", copiar_pastas=False)

    servico = _servico(config)

    assert [ref.profile for ref in servico._inbox] == [PERFIL_PADRAO_ID]
    assert len(servico._labeled) == 18
    falhas = [f for f in servico.failures() if f.category == "perfil incompleto"]
    assert [f.filename for f in falhas] == ["Vazio"]
    # Ativo e incompleto: a fila fica vazia, sem excecao.
    servico.train()
    assert servico.queue() == []


def test_perfil_copiado_nao_dobra_as_faixas_rotuladas(tmp_path):
    base = _base(tmp_path)
    _povoa(base)
    config, _ = criar(base, "Copia", copiar_pastas=True)

    servico = _servico(config)

    # Mesmas pastas nos dois perfis: cada faixa rotulada entra uma vez so.
    assert len(servico._labeled) == 18
    assert len({ref.sha1 for ref in servico._labeled}) == 18


def test_draft_do_formato_plano_aceita_a_organizacao_da_raiz():
    """Primeiro uso: o front manda o raw plano ([folders] + [organization]
    na raiz). Sem isto o keep_copy se perdia no primeiro apply."""
    raw = {
        "folders": {"inbox": "/i", "up": "/u", "neutral": "/n", "down": "/d"},
        "organization": {"create": True, "move": True, "copy": True},
    }

    drafts = drafts_from_raw(raw)

    assert list(drafts) == [PERFIL_PADRAO_ID]
    d = drafts[PERFIL_PADRAO_ID]
    assert (d.create_under_root, d.auto_move_enabled, d.keep_copy) == (True, True, True)
    assert d.display_name == "Padrão"
