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
