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

    assert "1.80" in aba.detalhe.text()
    assert "handcrafted-v1" in aba.detalhe.text()


def test_detalhe_tecnico_sem_treino_nao_inventa_numero(qapp):
    aba = ModelTab()
    aba.set_state(estado(alpha=None, thresholds=None))

    # alpha_ e thresholds_ tem default no TrackModel; mostra-los como se
    # fossem resultado de treino seria mentira.
    assert "1.80" not in aba.detalhe.text()
    assert "handcrafted-v1" in aba.detalhe.text()


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


def test_sem_exemplo_nenhum_a_aba_e_so_o_empty_state(qapp):
    """Cards de metrica, matriz e balanco com zero em tudo nao informam
    nada -- so ocupam a tela com estrutura vazia."""
    aba = ModelTab()

    aba.set_state(estado(n_examples=0, class_counts=(0, 0, 0), accuracy=None, confusion=None))

    assert aba.vazio_visivel() is True
    assert aba.conteudo_visivel() is False


def test_falhas_continuam_visiveis_sem_exemplo_nenhum(qapp):
    """Achado Important da revisao final.

    FailureList e a UNICA superficie do app que mostra service.failures().
    O early-return de set_state para n_examples==0 (adicionado pela Task 4)
    rodava ANTES de self.falhas.set_failures, entao uma biblioteca fresca
    que acabou de escanear e bateu em falhas reais (ffmpeg ausente, arquivo
    corrompido) mas ainda nao tem exemplo rotulado nenhum -- o estado normal
    logo apos o primeiro scan -- nao mostrava as falhas em lugar nenhum da
    UI, violando o invariante do repo de que erro de borda degrada E
    reporta, nunca so degrada em silencio.
    """
    falhas = (("a.m4a", "ffmpeg nao encontrado", "ffmpeg nao encontrado"),)

    aba = ModelTab()
    aba.set_state(
        estado(
            n_examples=0,
            class_counts=(0, 0, 0),
            accuracy=None,
            confusion=None,
            failures=falhas,
        )
    )

    assert aba.vazio_visivel() is True
    assert aba.falhas_visivel() is True
    assert aba.falhas.badge(0).text() == "1"


def test_com_exemplos_e_sem_treino_o_empty_state_nao_aparece(qapp):
    """Estado diferente: ha o que aprender, so nao treinou ainda. Quem
    responde por ele e o `sem_treino` dentro do card de metricas."""
    aba = ModelTab()

    aba.set_state(estado(n_examples=5, class_counts=(2, 2, 1), accuracy=None, confusion=None))

    assert aba.vazio_visivel() is False
    assert aba.conteudo_visivel() is True
    assert aba.sem_treino.isVisibleTo(aba)


def test_o_botao_do_empty_state_pede_a_revisao(qapp):
    aba = ModelTab()
    aba.set_state(estado(n_examples=0, class_counts=(0, 0, 0), accuracy=None, confusion=None))
    recebidos = []
    aba.review_requested.connect(lambda: recebidos.append(True))

    aba.acionar_empty_state()

    assert recebidos == [True]
