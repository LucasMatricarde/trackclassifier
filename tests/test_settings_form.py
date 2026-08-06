"""O formulario de configuracao. Roda offscreen (conftest), sem dialogo nativo.

O picker de pasta e injetado: QFileDialog.getExistingDirectory abre uma
janela modal de verdade e trava a suite. Injetar o callable e o que permite
exercitar o clique no botao "Escolher" de verdade, pelo caminho real do
widget, em vez de so chamar set_draft.
"""

import pytest

from trackclassifier.config import SettingsDraft
from trackclassifier.ui.settings_form import SettingsForm


@pytest.fixture
def form(qapp, tmp_path):
    escolhidas = []

    def escolher(titulo, atual):
        return escolhidas.pop(0) if escolhidas else ""

    widget = SettingsForm(escolher_pasta=escolher)
    widget._escolhidas_do_teste = escolhidas
    return widget


def _draft_cheio(tmp_path):
    for nome in ("inbox", "up", "neutral", "down"):
        (tmp_path / nome).mkdir()
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


def test_round_trip_de_draft(form, tmp_path):
    original = _draft_cheio(tmp_path)

    form.set_draft(original)

    assert form.draft() == original


def test_formulario_vazio_e_invalido(form):
    form.set_draft(SettingsDraft.from_raw({}))

    assert form.is_valid() is False


def test_formulario_completo_e_valido(form, tmp_path):
    form.set_draft(_draft_cheio(tmp_path))

    assert form.is_valid() is True


def test_modo_raiz_esconde_os_tres_pickers(form, tmp_path):
    raiz = tmp_path / "acervo"
    raiz.mkdir()
    (tmp_path / "inbox").mkdir()

    form.set_draft(
        SettingsDraft(
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

    assert form.is_valid() is True
    assert form.campo_visivel("up") is False
    assert form.campo_visivel("root") is True


def test_show_errors_marca_o_campo_culpado(form, tmp_path):
    from trackclassifier.config import SettingsError

    form.set_draft(_draft_cheio(tmp_path))

    form.show_errors([SettingsError("up", "Esta pasta nao existe.")])

    assert form.erro_do_campo("up") == "Esta pasta nao existe."
    assert form.erro_do_campo("inbox") == ""


def test_show_errors_limpa_a_marcacao_anterior(form, tmp_path):
    from trackclassifier.config import SettingsError

    form.set_draft(_draft_cheio(tmp_path))
    form.show_errors([SettingsError("up", "Esta pasta nao existe.")])

    form.show_errors([])

    assert form.erro_do_campo("up") == ""


def test_botao_escolher_preenche_o_campo(form, tmp_path):
    """Exercita o caminho real do botao, nao so set_draft."""
    destino = tmp_path / "escolhida"
    destino.mkdir()
    form._escolhidas_do_teste.append(str(destino))

    form.escolher_para_o_teste("inbox")

    assert form.draft().inbox == str(destino)


def test_validity_changed_dispara_ao_completar(form, tmp_path):
    recebidos = []
    form.validity_changed.connect(recebidos.append)

    form.set_draft(_draft_cheio(tmp_path))

    assert recebidos[-1] is True
