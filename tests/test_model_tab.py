from trackclassifier.ui.model_tab import ModelTab
from trackclassifier.ui.viewmodel import ModelState

BASE = dict(
    accuracy=0.78,
    ordinal_mae=0.243,
    confusion=((62, 10, 2), (13, 68, 8), (3, 11, 37)),
    n_examples=214,
    failures=(),
    class_counts=(74, 89, 51),
    decisions_since_train=6,
    retrain_every=10,
    train_blocked_reason=None,
    low_confidence=False,
    alpha=1.8,
    thresholds=(-0.33, 0.41),
    extractor_name="handcrafted-v1",
)


def estado(**mudancas) -> ModelState:
    return ModelState(**{**BASE, **mudancas})


def test_metricas_aparecem_treinado(qapp):
    aba = ModelTab()
    aba.set_state(estado())

    assert aba.exemplos.text() == "214"
    assert aba.acuracia.text() == "78.0%"
    assert aba.erro_ordinal.text() == "0.243"


def test_nao_treinado_esconde_metricas_e_mantem_balanco(qapp):
    aba = ModelTab()
    aba.set_state(estado(accuracy=None, ordinal_mae=None, confusion=None))

    # Nao treinado e o estado normal do inicio, nao um erro: o balanco e
    # as falhas continuam valendo.
    assert not aba.metricas.isVisibleTo(aba)
    assert aba.sem_treino.isVisibleTo(aba)
    assert aba.balanco.isVisibleTo(aba)


def test_botao_desabilita_com_motivo_visivel(qapp):
    aba = ModelTab()
    aba.set_state(estado(train_blocked_reason="Faltam exemplos de +1"))

    assert not aba.botao_retreinar.isEnabled()
    assert aba.motivo.text() == "Faltam exemplos de +1"
    assert aba.motivo.isVisibleTo(aba)


def test_bloqueado_esconde_o_contador(qapp):
    aba = ModelTab()
    aba.set_state(estado(train_blocked_reason="Faltam exemplos de +1"))

    # O contador promete um retreino automatico que nao vai acontecer
    # enquanto faltar classe -- mostrar os dois lado a lado se contradiz.
    assert not aba.progresso.isVisibleTo(aba)


def test_train_requested_nao_sai_com_botao_desabilitado(qapp):
    aba = ModelTab()
    aba.set_state(estado(train_blocked_reason="Faltam exemplos de +1"))
    disparos = []
    aba.train_requested.connect(lambda: disparos.append(1))

    aba.botao_retreinar.click()

    assert disparos == []


def test_train_requested_sai_com_botao_habilitado(qapp):
    aba = ModelTab()
    aba.set_state(estado())
    disparos = []
    aba.train_requested.connect(lambda: disparos.append(1))

    aba.botao_retreinar.click()

    assert disparos == [1]


def test_contador_de_retreino(qapp):
    aba = ModelTab()
    aba.set_state(estado(decisions_since_train=6, retrain_every=10))

    assert aba.progresso.text() == "6 / 10 ATE O RETREINO AUTOMATICO"


def test_aviso_de_baixa_confianca_some_quando_falso(qapp):
    aba = ModelTab()
    aba.set_state(estado(low_confidence=False))

    assert not aba.aviso.isVisibleTo(aba)


def test_aviso_de_baixa_confianca_aparece_quando_verdadeiro(qapp):
    aba = ModelTab()
    aba.set_state(estado(low_confidence=True))

    assert aba.aviso.isVisibleTo(aba)


def test_detalhe_tecnico_resume_fechado(qapp):
    aba = ModelTab()
    aba.set_state(estado())

    assert "1.80" in aba.detalhe.resumo.text()
    assert "handcrafted-v1" in aba.detalhe.resumo.text()


def test_detalhe_tecnico_sem_treino_nao_inventa_numero(qapp):
    aba = ModelTab()
    aba.set_state(estado(alpha=None, thresholds=None))

    # alpha_ e thresholds_ tem default no TrackModel; mostra-los como se
    # fossem resultado de treino seria mentira.
    assert "1.80" not in aba.detalhe.resumo.text()
    assert "handcrafted-v1" in aba.detalhe.resumo.text()


def _cards_do_topo(aba: ModelTab) -> list:
    """Os tres cards da primeira faixa, pelo widget interno que cada um guarda
    como atributo -- o card em si (o QWidget de fundo que _card() devolve) nao
    tem nome, so o parent do conteudo."""
    return [aba.metricas.parent(), aba.matriz.parent(), aba.balanco.parent()]


def test_cards_do_topo_tem_a_mesma_altura(qapp):
    aba = ModelTab()
    aba.set_state(estado())
    aba.resize(1100, 900)
    aba.show()

    alturas = {card.height() for card in _cards_do_topo(aba)}

    # QHBoxLayout ja estica os tres para a altura da linha: um card mais
    # baixo que os outros e sinal de que algum ganhou um QSizePolicy que
    # atrapalha esse esticamento, nao um comportamento normal do layout.
    assert len(alturas) == 1


def test_cards_do_topo_nao_esticam_com_a_sobra_da_tela(qapp):
    aba = ModelTab()
    aba.set_state(estado(failures=()))

    aba.resize(1100, 900)
    aba.show()
    alturas_900 = [card.height() for card in _cards_do_topo(aba)]

    aba.resize(1100, 1400)
    aba.show()
    alturas_1400 = [card.height() for card in _cards_do_topo(aba)]

    # A sobra de altura vai pro addStretch no rodape da aba, nao pros cards
    # do topo -- sem falhas pra mostrar, a secao inteira some e e exatamente
    # esse vazio que antes inflava os tres cards do topo pra ~500px.
    assert alturas_900 == alturas_1400


def test_matriz_e_balanco_recebem_o_estado(qapp):
    aba = ModelTab()
    aba.set_state(estado())

    assert aba.matriz.celula(0, 1).text() == "10"
    assert aba.balanco.contagem(1).text() == "89"


def test_falhas_aparecem_agrupadas(qapp):
    falhas = (
        ("a.m4a", "ffmpeg nao encontrado", "ffmpeg nao encontrado"),
        ("b.m4a", "ffmpeg nao encontrado", "ffmpeg nao encontrado"),
    )

    aba = ModelTab()
    aba.set_state(estado(failures=falhas))

    assert aba.falhas.badge(0).text() == "2"
