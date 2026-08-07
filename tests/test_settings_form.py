"""O formulario de configuracao. Roda offscreen (conftest), sem dialogo nativo.

O picker de pasta e injetado: QFileDialog.getExistingDirectory abre uma
janela modal de verdade e trava a suite. Injetar o callable e o que permite
exercitar o clique no botao "Escolher" de verdade, pelo caminho real do
widget, em vez de so chamar set_draft.
"""

import pytest
from PySide6.QtCore import QCoreApplication, QDeadlineTimer, QEventLoop

from trackclassifier.config import SettingsDraft
from trackclassifier.ui.settings_form import SettingsForm


def _sem_contagem(caminhos):
    """contar() padrao dos testes deste arquivo: nao bate no disco.

    A maioria dos testes aqui nao quer exercitar counts_worker (ha suite
    propria para isso) nem depende de QThreadPool terminar a tempo -- so
    precisa que _pede_contagem() nao estoure.
    """
    return dict.fromkeys(caminhos, "")


@pytest.fixture
def form(qapp, tmp_path):
    escolhidas = []

    def escolher(titulo, atual):
        return escolhidas.pop(0) if escolhidas else ""

    widget = SettingsForm(escolher_pasta=escolher, contar=_sem_contagem)
    widget._escolhidas_do_teste = escolhidas
    return widget


def _bombeia(timeout_ms=1000, ate=None):
    """Processa o loop de eventos ate `ate()` ser verdadeiro ou o prazo
    estourar. Necessario porque o resultado da contagem atravessa do
    QThreadPool de volta para a thread da GUI por conexao em fila."""
    prazo = QDeadlineTimer(timeout_ms)
    while not prazo.hasExpired() and not (ate and ate()):
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)


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
    """True quando o rotulo do campo `chave` chegaria a tela.

    isVisibleTo(form) em vez de isHidden(): o rotulo agora mora DENTRO do
    _CampoDePasta, entao esconder a linha nao mexe no flag proprio do
    rotulo -- ele some por causa do pai. isVisibleTo responde exatamente a
    pergunta que interessa ("apareceria se o form fosse mostrado?") e
    funciona offscreen, sem show()."""
    return form._campos[chave].rotulo.isVisibleTo(form)


def test_o_rotulo_mora_dentro_da_linha_do_campo(form):
    """O rotulo ser filho do proprio campo e o que torna impossivel a classe
    de bug do QFormLayout: rotulo orfao na tela depois de esconder a linha.
    Se alguem voltar a montar o par label/campo por fora, isto falha."""
    for chave in ("inbox", "root", "up", "neutral", "down", "data_dir"):
        campo = form._campos[chave]
        assert campo.rotulo.parent() is campo


def test_alterna_modo_esconde_a_linha_inteira_nao_so_o_campo(form, tmp_path):
    """A linha inteira -- rotulo, ponto, chip, campo e erro -- some junto.
    Antes o par label/campo era montado pelo QFormLayout e escondiam-se
    separadamente; o rotulo ("Criar a estrutura em" no modo default; os tres
    destinos no modo raiz) ficava orfao na tela sem campo do lado."""
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


def test_rotulos_dos_destinos_usam_o_vocabulario_do_dominio(form):
    """-1/neutra/+1, nunca down/neutral/up: essas chaves nao aparecem em
    nenhuma outra tela do app."""
    assert form._campos["up"].rotulo.text() == "+1"
    assert form._campos["neutral"].rotulo.text() == "neutra"
    assert form._campos["down"].rotulo.text() == "-1"


def test_destinos_tem_ponto_na_cor_da_classe(form):
    """O mesmo laranja/amarelo/azul que o chip da lista e os alvos da
    Revisao usam -- o mapeamento pasta<->classe se explica sozinho."""
    from trackclassifier.ui.tokens import classification_base

    assert form._campos["up"].ponto is not None
    assert (
        f"background: {classification_base('animada')};"
        in form._campos["up"].ponto.styleSheet()
    )
    assert (
        f"background: {classification_base('lento')};"
        in form._campos["down"].ponto.styleSheet()
    )
    # inbox e data_dir nao sao destino de classificacao: sem ponto.
    assert form._campos["inbox"].ponto is None
    assert form._campos["data_dir"].ponto is None


def test_secoes_falam_caixa_alta(form):
    """font.case.label: cabecalho de secao SEMPRE em caixa alta."""
    from trackclassifier.ui.settings_form import _cabecalho

    rotulo = _cabecalho("Entrada")

    assert rotulo.text() == "ENTRADA"


def test_erro_marca_o_campo_com_borda_de_perigo(form, tmp_path):
    from trackclassifier.config import SettingsError

    form.set_draft(_draft_cheio(tmp_path))

    form.show_errors([SettingsError("up", "Esta pasta nao existe.")])

    assert form._campos["up"].campo.property("state") == "invalid"
    assert form._campos["inbox"].campo.property("state") in (None, "")

    form.show_errors([])

    assert form._campos["up"].campo.property("state") in (None, "")


def test_chip_aparece_com_o_resultado_da_contagem(form):
    """set_counts e o metodo que o sinal `pronto` do contador alimenta --
    testado aqui isolado do QThreadPool, que tem suite propria."""
    form.set_counts({"inbox": "3 NOVAS"})

    assert form.chip_do_campo("inbox") == "3 NOVAS"


def test_chip_ausente_quando_a_contagem_ainda_nao_chegou(form):
    """Sem spinner, sem placeholder -- o chip so existe quando ha numero."""
    assert form.chip_do_campo("inbox") == ""


def test_chip_de_pasta_ausente_usa_o_estado_de_perigo(form):
    from trackclassifier.ui.counts import NAO_ENCONTRADA

    form.set_counts({"up": NAO_ENCONTRADA})

    assert form._campos["up"].chip.property("state") == "danger"


def test_digitar_rapido_nao_dispara_uma_contagem_por_tecla(qapp, tmp_path):
    """O debounce de 300ms: seis teclas em sequencia rapida devem virar UMA
    chamada de contagem, nao seis."""
    chamadas = []

    def _contar(caminhos):
        chamadas.append(dict(caminhos))
        return dict.fromkeys(caminhos, "")

    form = SettingsForm(escolher_pasta=lambda *_: "", contar=_contar)
    # A primeira digitacao dispara o timer do construtor tambem
    # (set_draft/_alterna_modo chamam _revalida) -- drena antes de comecar
    # a contar o que o teste quer medir.
    _bombeia(500)
    chamadas.clear()

    campo = form._campos["inbox"]
    for letra in "/tmp/x":
        campo.set_texto(campo.texto() + letra)

    _bombeia(1000, ate=lambda: len(chamadas) >= 1)

    assert len(chamadas) == 1


def test_contagem_nao_calcula_sha1_ao_digitar(qapp, tmp_path):
    """A contagem por tras do debounce e a mesma counts.contagens barata --
    reforca em nivel de formulario o que test_counts.py ja garante em
    isolamento."""
    import hashlib

    pasta = tmp_path / "entrada"
    pasta.mkdir()
    (pasta / "a.mp3").write_bytes(b"conteudo")

    chamado = []
    original = hashlib.sha1

    def _sha1_espiao(*args, **kwargs):
        chamado.append(True)
        return original(*args, **kwargs)

    monkeypatch_alvo = hashlib.sha1
    hashlib.sha1 = _sha1_espiao
    try:
        form = SettingsForm(escolher_pasta=lambda *_: "")
        form._campos["inbox"].set_texto(str(pasta))
        _bombeia(1000, ate=lambda: form.chip_do_campo("inbox") != "")
    finally:
        hashlib.sha1 = monkeypatch_alvo

    assert chamado == []
    assert form.chip_do_campo("inbox") == "1 NOVAS"
