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
