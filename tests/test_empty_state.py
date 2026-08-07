"""O empty state e o rosto do app: as tres abas abrem vazias."""

import pytest

from trackclassifier.ui.widgets.empty_state import Acao, EmptyState


def test_sem_acao_nao_cria_botao(qapp):
    vazio = EmptyState("Fila vazia")

    assert vazio.rotulos_das_acoes() == ()


def test_com_acao_emite_o_rotulo_ao_clicar(qapp):
    vazio = EmptyState("Fila vazia", "Escaneie a inbox", (Acao("Escanear"),))
    recebidos = []
    vazio.acao_clicada.connect(recebidos.append)

    vazio.acionar("Escanear")

    assert recebidos == ["Escanear"]


def test_duas_acoes_sao_distinguiveis_pelo_rotulo(qapp):
    """A busca sem resultado tem dois botoes; um sinal sem argumento
    obrigaria a aba a adivinhar qual deles foi clicado."""
    vazio = EmptyState(
        "Nada encontrado",
        "",
        (Acao("Limpar busca", "base"), Acao("Filtro: todos", "base")),
    )
    recebidos = []
    vazio.acao_clicada.connect(recebidos.append)

    vazio.acionar("Filtro: todos")

    assert vazio.rotulos_das_acoes() == ("Limpar busca", "Filtro: todos")
    assert recebidos == ["Filtro: todos"]


def test_o_rotulo_do_sinal_nao_leva_a_caixa_alta_da_tela(qapp):
    """O botao mostra ESCANEAR (font.case.label), mas quem escuta compara
    com a string que passou -- caixa alta e apresentacao, nao identidade."""
    vazio = EmptyState("Fila vazia", "", (Acao("Escanear"),))
    recebidos = []
    vazio.acao_clicada.connect(recebidos.append)

    vazio.acionar("Escanear")

    assert recebidos == ["Escanear"]


def test_acionar_rotulo_inexistente_levanta(qapp):
    """Erro de programacao, nao estado possivel de tela: silenciar deixaria
    um botao renomeado parar de funcionar sem ninguem notar."""
    vazio = EmptyState("Fila vazia", "", (Acao("Escanear"),))

    with pytest.raises(KeyError):
        vazio.acionar("Cancelar")


def test_subtitulo_vazio_nao_ocupa_altura(qapp):
    """Um QLabel vazio ainda reserva a altura da linha e desloca o bloco
    centralizado para cima."""
    vazio = EmptyState("Fila vazia")

    assert vazio.subtitulo_visivel() is False


def test_o_subtitulo_aceita_rich_text(qapp):
    """A busca sem resultado destaca o termo e o filtro dentro da frase --
    ver LibraryTab._texto_sem_resultado."""
    vazio = EmptyState("x", "Nada em <b>kernel</b>")

    assert "kernel" in vazio.texto_do_subtitulo()


def test_o_titulo_aceita_rich_text(qapp):
    """A busca sem resultado destaca o termo dentro da PRIMEIRA linha."""
    vazio = EmptyState("Nada em <b>kernel</b>")

    assert "kernel" in vazio.texto_do_titulo()
