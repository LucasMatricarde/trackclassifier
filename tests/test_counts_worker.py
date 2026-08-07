"""ContadorEmSegundoPlano: contagem fora da thread da GUI, so a mais recente."""

from PySide6.QtCore import QCoreApplication, QDeadlineTimer, QEventLoop

from trackclassifier.ui.counts_worker import ContadorEmSegundoPlano


def _roda_ate(sinal, timeout_ms=2000):
    """Bombeia o loop de eventos ate o sinal disparar ou estourar o prazo.

    Necessario porque o resultado atravessa de uma thread do QThreadPool de
    volta para a thread da GUI por conexao em fila -- so e entregue quando
    esta thread volta ao loop de eventos, o que um teste sincrono nao faz
    sozinho.
    """
    loop = QEventLoop()
    recebido = {}

    def _marca(*args):
        recebido["args"] = args
        loop.quit()

    conexao = sinal.connect(_marca)
    prazo = QDeadlineTimer(timeout_ms)
    while "args" not in recebido and not prazo.hasExpired():
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    sinal.disconnect(conexao)
    return recebido.get("args")


def test_pedir_devolve_resultado_do_callable_injetado(qapp):
    contador = ContadorEmSegundoPlano(contar=lambda caminhos: {"inbox": "3 NOVAS"})

    contador.pedir({"inbox": "/qualquer"})

    args = _roda_ate(contador.pronto)

    assert args == ({"inbox": "3 NOVAS"},)


def test_so_o_pedido_mais_recente_emite(qapp):
    """Duas geracoes em voo: a resposta da mais velha nao pode sobrescrever
    a da mais nova, mesmo chegando depois."""
    import threading

    liberar_primeira = threading.Event()
    ordem = []

    def _contar(caminhos):
        rotulo = caminhos["marca"]
        ordem.append(rotulo)
        if rotulo == "primeira":
            # Segura a primeira ate a segunda ja ter sido pedida, para forcar
            # a primeira terminar DEPOIS -- fora de ordem.
            liberar_primeira.wait(timeout=2)
        return {"marca": rotulo}

    contador = ContadorEmSegundoPlano(contar=_contar)

    contador.pedir({"marca": "primeira"})
    contador.pedir({"marca": "segunda"})

    resultados = []
    contador.pronto.connect(resultados.append)

    prazo = QDeadlineTimer(2000)
    while len(resultados) < 1 and not prazo.hasExpired():
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if "segunda" in ordem:
            liberar_primeira.set()

    assert resultados == [{"marca": "segunda"}]


def test_excecao_na_contagem_nao_propaga(qapp):
    def _explode(caminhos):
        raise RuntimeError("disco caiu")

    contador = ContadorEmSegundoPlano(contar=_explode)

    contador.pedir({"inbox": "/qualquer"})

    # Nao ha assert de resultado: o teste passa se processEvents nao
    # relancar a excecao da thread do pool e a suite continuar de pe.
    prazo = QDeadlineTimer(300)
    while not prazo.hasExpired():
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
