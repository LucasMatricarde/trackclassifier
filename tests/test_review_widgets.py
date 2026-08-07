"""Os quatro widgets que a Fase 3 tirou de dentro da ReviewTab."""

from trackclassifier.ui.viewmodel import TrackRow
from trackclassifier.ui.widgets.decision_bar import DecisionBar
from trackclassifier.ui.widgets.guess_bar import LIMIAR_ATENCAO, GuessBar
from trackclassifier.ui.widgets.metric_block import MetricBlock
from trackclassifier.ui.widgets.upcoming_list import UpcomingList


def _linha(sha1: str, titulo: str) -> TrackRow:
    return TrackRow(
        sha1=sha1,
        filename=f"{titulo}.wav",
        label=None,
        predicted="+1",
        score=0.8,
        confidence=0.8,
        bpm=128.0,
        duration_s=300.0,
        energy_curve=(0.1, 0.5, 0.2),
        peak_offset_s=10.0,
        path_hint=f"/tmp/{titulo}.wav",
        title=titulo,
    )


# --- MetricBlock ---


def test_metric_block_sem_valor_some_com_o_rotulo_junto(qapp):
    bloco = MetricBlock("BPM")
    bloco.set_value("128")
    bloco.set_value(None)

    # Um micro-label sozinho sobre espaco vazio parece dado que falhou ao
    # carregar; o bloco ausente parece o que e.
    assert bloco.isHidden()


def test_metric_block_com_valor_aparece(qapp):
    bloco = MetricBlock("BPM")
    bloco.set_value("128")

    assert bloco._valor.text() == "128"


# --- GuessBar ---


def test_guess_bar_sem_palpite_some_inteira(qapp):
    barra = GuessBar()
    barra.set_guess("+1", 0.8, low_confidence=False)
    barra.set_guess(None, None, low_confidence=False)

    # Modelo nao treinado nao tem opiniao, e uma faixa vazia com o rotulo
    # PALPITE sugeriria que ele tem uma e a tela nao conseguiu mostrar.
    assert barra.isHidden()


def test_guess_bar_acende_o_segmento_da_classe(qapp):
    barra = GuessBar()
    barra.set_guess("-1", 0.6, low_confidence=False)

    assert barra.escala.aceso() == 0


def test_guess_bar_medidor_segue_a_confianca(qapp):
    barra = GuessBar()
    barra.set_guess("+1", 0.82, low_confidence=False)

    assert barra.medidor.fraction() == 0.82
    assert barra.numero.text() == "confianca 0.82"


def test_guess_bar_confianca_baixa_troca_a_cor(qapp):
    alta = GuessBar()
    alta.set_guess("+1", LIMIAR_ATENCAO + 0.1, low_confidence=False)

    baixa = GuessBar()
    baixa.set_guess("+1", LIMIAR_ATENCAO - 0.1, low_confidence=False)

    # A cor e o que faz "0.31" ser lido como problema sem o usuario
    # precisar lembrar onde fica o corte.
    assert alta.medidor.color() != baixa.medidor.color()


def test_guess_bar_esconde_o_aviso_quando_nao_ha(qapp):
    barra = GuessBar()
    barra.set_guess("+1", 0.8, low_confidence=False)

    assert not barra.aviso.isVisibleTo(barra)


def test_guess_bar_mostra_o_aviso_de_poucos_exemplos(qapp):
    barra = GuessBar()
    barra.set_guess("+1", 0.8, low_confidence=True)

    assert barra.aviso.isVisibleTo(barra)


def test_guess_bar_com_confianca_none_nao_quebra(qapp):
    barra = GuessBar()
    barra.set_guess("+1", None, low_confidence=False)

    assert barra.medidor.fraction() == 0.0


# --- DecisionBar ---


def test_decision_bar_emite_o_rotulo_do_alvo(qapp):
    barra = DecisionBar()
    recebidos = []
    barra.decidido.connect(recebidos.append)

    barra._alvos["neutra"].click()

    assert recebidos == ["neutra"]


def test_decision_bar_tem_um_alvo_por_classe(qapp):
    barra = DecisionBar()

    assert set(barra._alvos) == {"-1", "neutra", "+1"}


def test_decision_bar_desabilita_os_alvos_com_a_fila_vazia(qapp):
    barra = DecisionBar()
    barra.set_enabled_targets(False)

    assert all(not alvo.isEnabled() for alvo in barra._alvos.values())


def test_decision_bar_alvo_desabilitado_nao_emite(qapp):
    barra = DecisionBar()
    recebidos = []
    barra.decidido.connect(recebidos.append)
    barra.set_enabled_targets(False)

    barra._alvos["+1"].click()

    assert recebidos == []


def test_decision_bar_rotulo_do_bloco_mostra_o_limiar(qapp):
    barra = DecisionBar()
    barra.set_bulk_label(0.75)

    assert "0.75" in barra.botao_bloco.text()


# --- UpcomingList ---


def test_upcoming_list_mostra_as_linhas(qapp):
    lista = UpcomingList()
    lista.set_rows((_linha("a", "Um"), _linha("b", "Dois")))

    assert lista.total() == 2


def test_upcoming_list_vazia_some(qapp):
    lista = UpcomingList()
    lista.set_rows((_linha("a", "Um"),))
    lista.set_rows(())

    assert lista.isHidden()


def test_upcoming_list_nao_deixa_faixa_vazia(qapp):
    from trackclassifier.ui.tokens import SIZE_ROW_COMPACT

    lista = UpcomingList()
    lista.set_rows((_linha("a", "Um"), _linha("b", "Dois")))

    # Altura exata das linhas que existem: uma altura fixa de tres deixaria
    # faixa vazia quando a fila tem menos.
    assert lista.height() == 2 * SIZE_ROW_COMPACT


def test_decision_bar_legenda_bate_com_os_atalhos_registrados(qapp):
    """Uma legenda que promete tecla inexistente e pior que legenda nenhuma."""
    from trackclassifier.ui.widgets.decision_bar import _ATALHOS

    teclas = {tecla for tecla, _ in _ATALHOS}

    # O mockup escreve "Z", e nao da para cumprir: QShortcut WindowShortcut
    # roda antes da entrega normal e um "Z" solto roubaria a letra do campo
    # de busca da Biblioteca.
    assert "Z" not in teclas
    assert "ctrl+Z" in teclas


# --- acessibilidade dos widgets pintados a mao ---


def test_medidor_anuncia_o_valor(qapp):
    from trackclassifier.ui.tokens import COLOR_TEXT_SECONDARY
    from trackclassifier.ui.widgets.meter import Meter

    medidor = Meter(COLOR_TEXT_SECONDARY, 3)
    medidor.set_fraction(0.6)

    # O valor so existe como largura de pixel: sem isto um leitor de tela
    # anuncia "Medidor" e nada mais.
    assert medidor.accessibleName() == "Medidor"
    assert medidor.accessibleDescription() == "60%"


def test_escala_ordinal_anuncia_a_classe(qapp):
    from trackclassifier.ui.widgets.ordinal_scale import OrdinalScale

    escala = OrdinalScale()
    escala.set_label("+1")

    assert escala.accessibleDescription() == "+1"

    escala.set_label(None)

    assert escala.accessibleDescription() == "sem classificacao"


def test_matriz_de_confusao_tem_nome_acessivel(qapp):
    from trackclassifier.ui.widgets.confusion_matrix import ConfusionMatrix

    matriz = ConfusionMatrix()

    assert matriz.accessibleName() == "Matriz de confusao"
    assert "real" in matriz.accessibleDescription().lower()
