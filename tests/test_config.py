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


def test_apply_draft_cria_as_tres_subpastas_na_raiz(tmp_path):
    from trackclassifier.config import apply_draft

    (tmp_path / "inbox").mkdir()
    raiz = tmp_path / "acervo"
    raiz.mkdir()

    config = apply_draft(
        _draft(tmp_path, create_under_root=True, root=str(raiz), up="", neutral="", down="")
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
        _draft(tmp_path, create_under_root=True, root=str(raiz), up="", neutral="", down="")
    )

    assert config.folders[Label.UP] == raiz / "+1"


def test_apply_draft_usa_as_pastas_informadas_fora_do_modo_raiz(tmp_path):
    from trackclassifier.config import apply_draft

    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()

    config = apply_draft(_draft(tmp_path))

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
        )
    )

    assert config.inbox == tmp_path / "inbox"
