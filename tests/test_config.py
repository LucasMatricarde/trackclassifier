import pytest

from trackclassifier.config import Config, ConfigError, load_config
from trackclassifier.labels import Label


def _write_config(tmp_path, folders_exist=True, extra=""):
    for name in ("up", "neutral", "down", "inbox"):
        if folders_exist:
            (tmp_path / name).mkdir()
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        f"""
[folders]
up = "{tmp_path / 'up'}"
neutral = "{tmp_path / 'neutral'}"
down = "{tmp_path / 'down'}"
inbox = "{tmp_path / 'inbox'}"

[model]
retrain_every = 10
min_examples = 15

[paths]
data_dir = "{tmp_path / 'data'}"
{extra}
""",
        encoding="utf-8",
    )
    return cfg


def test_carrega_configuracao_valida(tmp_path):
    config = load_config(_write_config(tmp_path))

    assert isinstance(config, Config)
    assert config.folders[Label.UP] == tmp_path / "up"
    assert config.folders[Label.NEUTRAL] == tmp_path / "neutral"
    assert config.folders[Label.DOWN] == tmp_path / "down"
    assert config.inbox == tmp_path / "inbox"
    assert config.retrain_every == 10
    assert config.min_examples == 15


def test_cria_data_dir_se_nao_existir(tmp_path):
    config = load_config(_write_config(tmp_path))

    assert config.data_dir.is_dir()


def test_erro_quando_pasta_rotulada_nao_existe(tmp_path):
    cfg = _write_config(tmp_path, folders_exist=False)

    with pytest.raises(ConfigError) as exc:
        load_config(cfg)

    assert "up" in str(exc.value)


def test_erro_quando_arquivo_de_config_nao_existe(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "inexistente.toml")


def test_save_config_faz_round_trip_com_apostrofo_e_acento(tmp_path):
    """O motivo de usar tomli-w em vez de serializar a mao.

    Uma pasta chamada "DJ's Tracks" ou "Musicas Novas" quebra um escape
    caseiro em silencio -- o TOML sai sintaticamente valido e com o caminho
    errado dentro.
    """
    from trackclassifier.config import save_config

    pastas = {}
    for rotulo, nome in (
        (Label.UP, "DJ's Tracks +1"),
        (Label.NEUTRAL, "Musicas"),
        (Label.DOWN, 'Aspas " no meio'),
    ):
        pasta = tmp_path / nome
        pasta.mkdir()
        pastas[rotulo] = pasta
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    dados = tmp_path / "data"
    dados.mkdir()

    original = Config(
        folders=pastas, inbox=inbox, data_dir=dados, retrain_every=7, min_examples=3
    )
    destino = tmp_path / "config.toml"
    save_config(destino, original)

    recarregado = load_config(destino)

    assert recarregado.folders == original.folders
    assert recarregado.inbox == original.inbox
    assert recarregado.data_dir == original.data_dir
    assert recarregado.retrain_every == 7
    assert recarregado.min_examples == 3


def test_save_config_cria_o_diretorio_pai(tmp_path):
    """Empacotado o destino e ~/.trackclassifier/config.toml, e a pasta
    pode nao existir na primeira gravacao."""
    from trackclassifier.config import save_config

    pastas = {}
    for rotulo, nome in ((Label.UP, "up"), (Label.NEUTRAL, "neutral"), (Label.DOWN, "down")):
        pasta = tmp_path / nome
        pasta.mkdir()
        pastas[rotulo] = pasta
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    dados = tmp_path / "data"
    dados.mkdir()

    destino = tmp_path / "sem" / "pai" / "config.toml"
    save_config(
        destino,
        Config(folders=pastas, inbox=inbox, data_dir=dados, retrain_every=10, min_examples=15),
    )

    assert destino.is_file()


def test_read_raw_devolve_dicionario_vazio_quando_o_arquivo_nao_existe(tmp_path):
    from trackclassifier.config import read_raw

    assert read_raw(tmp_path / "inexistente.toml") == {}


def test_read_raw_devolve_dicionario_vazio_quando_o_toml_e_invalido(tmp_path):
    """Config corrompido nao pode derrubar o dialogo que existe justamente
    para consertar config."""
    from trackclassifier.config import read_raw

    quebrado = tmp_path / "config.toml"
    quebrado.write_text("[folders\nup = ", encoding="utf-8")

    assert read_raw(quebrado) == {}


def test_read_raw_nao_valida_pastas_inexistentes(tmp_path):
    """A diferenca para load_config: read_raw entrega o que esta escrito,
    mesmo apontando para pasta que sumiu -- e o que preenche o formulario."""
    from trackclassifier.config import read_raw

    cfg = _write_config(tmp_path, folders_exist=False)

    raw = read_raw(cfg)

    assert raw["folders"]["up"] == str(tmp_path / "up")


def test_draft_from_raw_le_um_config_completo(tmp_path):
    from trackclassifier.config import SettingsDraft, read_raw

    cfg = _write_config(tmp_path)

    draft = SettingsDraft.from_raw(read_raw(cfg))

    assert draft.up == str(tmp_path / "up")
    assert draft.inbox == str(tmp_path / "inbox")
    assert draft.retrain_every == 10
    assert draft.min_examples == 15
    assert draft.create_under_root is False
    assert draft.root == ""


def test_draft_from_raw_aceita_dicionario_vazio():
    """Primeiro uso: nao ha nada em disco, e o formulario abre em branco."""
    from trackclassifier.config import SettingsDraft

    draft = SettingsDraft.from_raw({})

    assert draft.up == ""
    assert draft.inbox == ""
    assert draft.retrain_every == 10
    assert draft.min_examples == 15


def test_draft_from_raw_com_retrain_every_nao_numerico_cai_no_padrao():
    """Achado da revisao final: um TOML mexido a mao com
    retrain_every = "dez" e sintaticamente valido (read_raw devolve o dict
    normalmente) mas int() estoura ValueError -- e from_raw roda dentro de
    FirstRunDialog.__init__/SettingsTab.__init__, sem try/except em volta.
    O padrao amortece isso do mesmo jeito que a chave ausente."""
    from trackclassifier.config import SettingsDraft

    draft = SettingsDraft.from_raw({"model": {"retrain_every": "dez"}})

    assert draft.retrain_every == 10
    assert draft.min_examples == 15


def test_draft_from_raw_com_folders_no_tipo_errado_cai_no_padrao():
    """`folders = "oops"` (string em vez de tabela) faria o .get() original
    estourar AttributeError -- mesma classe de bug do teste acima, so que na
    borda da tabela em vez de num campo numerico."""
    from trackclassifier.config import SettingsDraft

    draft = SettingsDraft.from_raw({"folders": "oops"})

    assert draft.up == ""
    assert draft.inbox == ""
    assert draft.neutral == ""
    assert draft.down == ""


def _draft(tmp_path, **overrides):
    from trackclassifier.config import SettingsDraft

    base = {
        "inbox": str(tmp_path / "inbox"),
        "up": str(tmp_path / "up"),
        "neutral": str(tmp_path / "neutral"),
        "down": str(tmp_path / "down"),
        "data_dir": str(tmp_path / "data"),
        "retrain_every": 10,
        "min_examples": 15,
        "create_under_root": False,
        "root": "",
    }
    base.update(overrides)
    return SettingsDraft(**base)


def test_validate_aceita_quatro_pastas_existentes_e_distintas(tmp_path):
    from trackclassifier.config import validate_settings

    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    assert validate_settings(_draft(tmp_path)) == []


def test_validate_acusa_campo_vazio(tmp_path):
    from trackclassifier.config import validate_settings

    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    erros = validate_settings(_draft(tmp_path, up=""))

    assert [e.field for e in erros] == ["up"]


def test_validate_acusa_pasta_inexistente(tmp_path):
    from trackclassifier.config import validate_settings

    for nome in ("inbox", "neutral", "down"):
        (tmp_path / nome).mkdir()

    erros = validate_settings(_draft(tmp_path))

    assert [e.field for e in erros] == ["up"]


def test_validate_acusa_pastas_repetidas(tmp_path):
    """inbox igual a neutral faria apply mover o arquivo para dentro da
    propria pasta, e o O_CREAT|O_EXCL de _destino_livre responderia criando
    um duplicado com nome novo, sem erro nenhum. Falha silenciosa vira
    validacao."""
    from trackclassifier.config import validate_settings

    for nome in ("up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    erros = validate_settings(_draft(tmp_path, inbox=str(tmp_path / "neutral")))

    assert erros != []
    assert any("mesma pasta" in e.message for e in erros)


def test_validate_pastas_repetidas_usa_o_nome_exibido_nao_a_chave_interna(tmp_path):
    """Achado da revisao final: a mensagem usava a chave interna crua
    ("neutral") em vez do vocabulario que a tela usa ("neutra") -- essa
    mensagem aparece direto em FirstRunDialog, SettingsTab e SettingsForm."""
    from trackclassifier.config import validate_settings

    for nome in ("up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    erros = validate_settings(_draft(tmp_path, inbox=str(tmp_path / "neutral")))

    mensagens = [e.message for e in erros if e.field == "inbox"]
    assert mensagens
    assert any("neutra" in m for m in mensagens)
    assert not any("'neutral'" in m for m in mensagens)


def test_validate_no_modo_raiz_nao_exige_que_as_subpastas_existam(tmp_path):
    from trackclassifier.config import validate_settings

    (tmp_path / "inbox").mkdir()
    raiz = tmp_path / "acervo"
    raiz.mkdir()

    erros = validate_settings(
        _draft(tmp_path, create_under_root=True, root=str(raiz), up="", neutral="", down="")
    )

    assert erros == []


def test_validate_no_modo_raiz_exige_a_raiz(tmp_path):
    from trackclassifier.config import validate_settings

    (tmp_path / "inbox").mkdir()

    erros = validate_settings(
        _draft(
            tmp_path,
            create_under_root=True,
            root=str(tmp_path / "nao_existe"),
            up="",
            neutral="",
            down="",
        )
    )

    assert [e.field for e in erros] == ["root"]


def test_validate_no_modo_raiz_acusa_inbox_dentro_da_raiz(tmp_path):
    """A inbox dentro da raiz colidiria com uma das subpastas criadas ou
    faria o scan enxergar as tracks ja classificadas como pendentes."""
    from trackclassifier.config import validate_settings

    raiz = tmp_path / "acervo"
    raiz.mkdir()
    dentro = raiz / "+1"
    dentro.mkdir()

    erros = validate_settings(
        _draft(
            tmp_path,
            create_under_root=True,
            root=str(raiz),
            inbox=str(dentro),
            up="",
            neutral="",
            down="",
        )
    )

    assert erros != []


def test_validate_nao_cria_pasta_nenhuma(tmp_path):
    """Validar roda a cada tecla digitada; criar pasta a cada tecla nao."""
    from trackclassifier.config import validate_settings

    (tmp_path / "inbox").mkdir()
    raiz = tmp_path / "acervo"
    raiz.mkdir()

    validate_settings(
        _draft(tmp_path, create_under_root=True, root=str(raiz), up="", neutral="", down="")
    )

    assert list(raiz.iterdir()) == []


def _caminho_config(tmp_path):
    # apply_draft nao precisa que o arquivo exista -- so do caminho, para
    # resolver um data_dir relativo/vazio contra o PAI dele, do mesmo jeito
    # que load_config faria ao reler esse mesmo arquivo depois.
    return tmp_path / "config.toml"


def test_apply_draft_cria_as_tres_subpastas_na_raiz(tmp_path):
    from trackclassifier.config import apply_draft

    (tmp_path / "inbox").mkdir()
    raiz = tmp_path / "acervo"
    raiz.mkdir()

    config = apply_draft(
        _draft(tmp_path, create_under_root=True, root=str(raiz), up="", neutral="", down=""),
        _caminho_config(tmp_path),
    )

    assert config.folders[Label.UP] == raiz / "+1"
    assert config.folders[Label.NEUTRAL] == raiz / "neutra"
    assert config.folders[Label.DOWN] == raiz / "-1"
    assert all(pasta.is_dir() for pasta in config.folders.values())


def test_apply_draft_reaproveita_subpasta_que_ja_existe(tmp_path):
    """Reabrir a configuracao no modo raiz nao pode falhar por a pasta ja
    ter sido criada da vez anterior."""
    from trackclassifier.config import apply_draft

    (tmp_path / "inbox").mkdir()
    raiz = tmp_path / "acervo"
    (raiz / "+1").mkdir(parents=True)

    config = apply_draft(
        _draft(tmp_path, create_under_root=True, root=str(raiz), up="", neutral="", down=""),
        _caminho_config(tmp_path),
    )

    assert config.folders[Label.UP] == raiz / "+1"


def test_apply_draft_usa_as_pastas_informadas_fora_do_modo_raiz(tmp_path):
    from trackclassifier.config import apply_draft

    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    config = apply_draft(_draft(tmp_path), _caminho_config(tmp_path))

    assert config.folders[Label.UP] == tmp_path / "up"
    assert config.inbox == tmp_path / "inbox"
    assert config.data_dir.is_dir()


def test_apply_draft_expande_til(tmp_path, monkeypatch):
    from trackclassifier.config import apply_draft

    monkeypatch.setenv("HOME", str(tmp_path))
    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    config = apply_draft(
        _draft(
            tmp_path,
            inbox="~/inbox",
            up="~/up",
            neutral="~/neutral",
            down="~/down",
            data_dir="~/data",
        ),
        _caminho_config(tmp_path),
    )

    assert config.inbox == tmp_path / "inbox"


def test_apply_draft_com_data_dir_vazio_resolve_igual_a_load_config(tmp_path):
    """Achado Critical da revisao final.

    Antes desta correcao, data_dir vazio virava ".trackclassifier" relativo
    ao CWD do processo -- num app aberto pelo Finder isso e "/", que estoura
    PermissionError dentro do confirmar()/salvar() do dialogo, e mesmo
    quando o cwd e gravavel a pasta criada nao e a que load_config acha ao
    reler o mesmo arquivo (que resolve relativo ao PAI do arquivo de
    config, nao ao cwd). O round-trip apply_draft -> save_config ->
    load_config precisa concordar sobre onde fica a pasta.
    """
    from trackclassifier.config import apply_draft, load_config, save_config

    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()
    destino = _caminho_config(tmp_path)

    config = apply_draft(_draft(tmp_path, data_dir=""), destino)

    assert config.data_dir == destino.parent / ".trackclassifier"
    assert config.data_dir.is_dir()

    save_config(destino, config)
    recarregado = load_config(destino)

    assert recarregado.data_dir == config.data_dir


def test_apply_draft_com_config_path_em_subpasta_resolve_data_dir_la(tmp_path):
    """O mesmo caso do teste acima, mas com o arquivo de config guardado
    numa subpasta (o caso real: ~/.trackclassifier/config.toml num app
    empacotado) -- prova que a resolucao usa o PAI do arquivo, nao tmp_path
    nem o cwd do processo de teste."""
    from trackclassifier.config import apply_draft, load_config, save_config

    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()
    pasta_config = tmp_path / "config_em_outro_lugar"
    pasta_config.mkdir()
    destino = pasta_config / "config.toml"

    config = apply_draft(_draft(tmp_path, data_dir=""), destino)

    assert config.data_dir == pasta_config / ".trackclassifier"

    save_config(destino, config)
    assert load_config(destino).data_dir == config.data_dir
