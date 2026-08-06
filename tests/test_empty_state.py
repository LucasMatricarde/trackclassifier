"""O empty state e o rosto do app: as tres abas abrem vazias."""

from trackclassifier.ui.widgets.empty_state import EmptyState


def test_sem_acao_nao_cria_botao(qapp):
    vazio = EmptyState("Fila vazia")

    assert vazio.tem_botao() is False


def test_com_acao_emite_ao_clicar(qapp):
    vazio = EmptyState("Fila vazia", "Escaneie a inbox", "Escanear")
    recebidos = []
    vazio.action_clicked.connect(lambda: recebidos.append(True))

    vazio.acionar()

    assert vazio.tem_botao() is True
    assert recebidos == [True]


def test_subtitulo_vazio_nao_ocupa_altura(qapp):
    """Um QLabel vazio ainda reserva a altura da linha e desloca o bloco
    centralizado para cima."""
    vazio = EmptyState("Fila vazia")

    assert vazio.subtitulo_visivel() is False
