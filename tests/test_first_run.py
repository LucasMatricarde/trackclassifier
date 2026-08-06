"""Primeiro uso: config ausente ou invalido abre o dialogo, nao um erro."""

from trackclassifier.config import load_config, save_config
from trackclassifier.ui.first_run import FirstRunDialog


def _pastas(tmp_path):
    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()


def test_abre_em_branco_quando_nao_ha_config(qapp, tmp_path):
    dialogo = FirstRunDialog(tmp_path / "config.toml")

    assert dialogo.form.draft().inbox == ""
    assert dialogo.config is None


def test_abre_preenchido_quando_o_config_existe_mas_a_pasta_sumiu(qapp, tmp_path):
    """O caso que hoje e beco sem saida: em vez de mandar editar um TOML, o
    dialogo abre com o que deu para ler."""
    _pastas(tmp_path)
    caminho = tmp_path / "config.toml"
    save_config(caminho, load_config_de_teste(tmp_path, caminho))
    (tmp_path / "up").rmdir()

    dialogo = FirstRunDialog(caminho)

    assert dialogo.form.draft().inbox == str(tmp_path / "inbox")
    assert dialogo.form.draft().up == str(tmp_path / "up")


def load_config_de_teste(tmp_path, caminho):
    from trackclassifier.config import Config
    from trackclassifier.labels import Label

    return Config(
        folders={
            Label.UP: tmp_path / "up",
            Label.NEUTRAL: tmp_path / "neutral",
            Label.DOWN: tmp_path / "down",
        },
        inbox=tmp_path / "inbox",
        data_dir=tmp_path / "data",
        retrain_every=10,
        min_examples=15,
    )


def test_confirmar_grava_o_arquivo_e_expoe_o_config(qapp, tmp_path):
    _pastas(tmp_path)
    caminho = tmp_path / "config.toml"
    dialogo = FirstRunDialog(caminho)
    dialogo.form.set_draft(
        dialogo.form.draft().__class__(
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
    )

    dialogo.confirmar()

    assert caminho.is_file()
    assert dialogo.config is not None
    assert load_config(caminho).inbox == tmp_path / "inbox"


def test_confirmar_no_modo_raiz_cria_as_subpastas(qapp, tmp_path):
    (tmp_path / "inbox").mkdir()
    raiz = tmp_path / "acervo"
    raiz.mkdir()
    caminho = tmp_path / "config.toml"

    dialogo = FirstRunDialog(caminho)
    dialogo.form.set_draft(
        dialogo.form.draft().__class__(
            inbox=str(tmp_path / "inbox"),
            up="",
            neutral="",
            down="",
            data_dir=str(tmp_path / "data"),
            retrain_every=10,
            min_examples=15,
            create_under_root=True,
            root=str(raiz),
        )
    )

    dialogo.confirmar()

    assert (raiz / "+1").is_dir()
    assert (raiz / "neutra").is_dir()
    assert (raiz / "-1").is_dir()


def test_confirmar_com_data_dir_em_branco_nao_estoura(qapp, tmp_path):
    """Achado Critical da revisao final.

    Uma FirstRunDialog.form.set_draft(SettingsDraft.from_raw({})) e
    exatamente o estado real de primeira abertura: campos preenchidos pelo
    usuario, data_dir deixado em branco (ninguem digita isso na primeira
    tela). Antes da correcao, confirmar() estourava PermissionError (ou
    gravava numa pasta errada) porque apply_draft resolvia data_dir vazio
    contra o cwd do processo, nao contra a pasta do arquivo de config.
    """
    _pastas(tmp_path)
    caminho = tmp_path / "config.toml"
    dialogo = FirstRunDialog(caminho)
    rascunho_em_branco = dialogo.form.draft().__class__(
        inbox=str(tmp_path / "inbox"),
        up=str(tmp_path / "up"),
        neutral=str(tmp_path / "neutral"),
        down=str(tmp_path / "down"),
        data_dir="",
        retrain_every=10,
        min_examples=15,
        create_under_root=False,
        root="",
    )
    dialogo.form.set_draft(rascunho_em_branco)

    dialogo.confirmar()

    assert dialogo.config is not None
    assert dialogo.config.data_dir == caminho.parent / ".trackclassifier"
    assert dialogo.config.data_dir.is_dir()
    assert load_config(caminho).data_dir == dialogo.config.data_dir


def test_confirmar_com_formulario_invalido_nao_grava(qapp, tmp_path):
    caminho = tmp_path / "config.toml"
    dialogo = FirstRunDialog(caminho)

    dialogo.confirmar()

    assert not caminho.exists()
    assert dialogo.config is None
    assert dialogo.form.erro_do_campo("inbox") != ""
