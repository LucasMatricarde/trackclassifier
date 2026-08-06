"""A 4a aba: mesmo formulario do primeiro uso, mais Salvar."""

from trackclassifier.config import SettingsDraft, load_config
from trackclassifier.ui.settings_tab import SettingsTab


def _pastas(tmp_path):
    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()


def _draft(tmp_path):
    return SettingsDraft(
        inbox=str(tmp_path / "inbox"),
        up=str(tmp_path / "up"),
        neutral=str(tmp_path / "neutral"),
        down=str(tmp_path / "down"),
        data_dir=str(tmp_path / "data"),
        retrain_every=10,
        min_examples=15,
        create_under_root=False,
        root="",
    )


def test_salvar_grava_e_emite_o_config(qapp, tmp_path):
    _pastas(tmp_path)
    caminho = tmp_path / "config.toml"
    aba = SettingsTab(caminho)
    aba.form.set_draft(_draft(tmp_path))

    emitidos = []
    aba.config_saved.connect(emitidos.append)

    aba.salvar()

    assert caminho.is_file()
    assert load_config(caminho).inbox == tmp_path / "inbox"
    assert len(emitidos) == 1


def test_salvar_invalido_nao_grava_e_marca_o_campo(qapp, tmp_path):
    caminho = tmp_path / "config.toml"
    aba = SettingsTab(caminho)

    aba.salvar()

    assert not caminho.exists()
    assert aba.form.erro_do_campo("inbox") != ""


def test_salvar_desabilitado_durante_scan(qapp, tmp_path):
    """Durante um scan o worker esta preso em analyze_all e um slot
    enfileirado so rodaria no fim -- o botao dizer isso e melhor que a
    configuracao aplicar sozinha dez minutos depois."""
    _pastas(tmp_path)
    aba = SettingsTab(tmp_path / "config.toml")
    aba.form.set_draft(_draft(tmp_path))
    assert aba.botao_habilitado() is True

    aba.set_scanning(True)

    assert aba.botao_habilitado() is False

    aba.set_scanning(False)

    assert aba.botao_habilitado() is True
