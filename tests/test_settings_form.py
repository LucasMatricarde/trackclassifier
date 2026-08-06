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


def _rotulo_visivel(form, chave):
    """True quando o QLabel PAREADO ao campo `chave` no QFormLayout esta
    visivel -- nao so o campo. setVisible() no campo sozinho nao esconde o
    rotulo (QFormLayout nao amarra os dois automaticamente), entao um teste
    que so olhasse campo_visivel() nao pegaria o achado da revisao final."""
    from PySide6.QtWidgets import QFormLayout

    layout = form._formulario
    linha, _papel = layout.getWidgetPosition(form._campos[chave])
    item_rotulo = layout.itemAt(linha, QFormLayout.ItemRole.LabelRole)
    return item_rotulo is not None and not item_rotulo.widget().isHidden()


def test_alterna_modo_esconde_a_linha_inteira_nao_so_o_campo(form, tmp_path):
    """Achado Important da revisao final: QFormLayout.setRowVisible precisa
    ser chamado tambem, senao o rotulo ("Criar a estrutura em" no modo
    default; os tres "Destino ..." no modo raiz) fica orfao na tela sem
    campo nenhum do lado."""
    raiz = tmp_path / "acervo"
    raiz.mkdir()

    # Modo default: os campos up/neutral/down (e seus rotulos) visiveis,
    # root (e o dele) escondido.
    assert form.campo_visivel("up") is True
    assert _rotulo_visivel(form, "up") is True
    assert form.campo_visivel("root") is False
    assert _rotulo_visivel(form, "root") is False

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

    # Modo raiz: inverte -- up/neutral/down (e rotulos) escondidos, root (e
    # o dele) visivel.
    for chave in ("up", "neutral", "down"):
        assert form.campo_visivel(chave) is False
        assert _rotulo_visivel(form, chave) is False
    assert form.campo_visivel("root") is True
    assert _rotulo_visivel(form, "root") is True

    form.set_draft(_draft_cheio(tmp_path))

    # Volta ao default: tudo reverte de novo.
    for chave in ("up", "neutral", "down"):
        assert form.campo_visivel(chave) is True
        assert _rotulo_visivel(form, chave) is True
    assert form.campo_visivel("root") is False
    assert _rotulo_visivel(form, "root") is False


def test_validity_changed_dispara_ao_completar(form, tmp_path):
    recebidos = []
    form.validity_changed.connect(recebidos.append)

    form.set_draft(_draft_cheio(tmp_path))

    assert recebidos[-1] is True
