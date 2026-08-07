"""VerificadorDeAtualizacao: rede e disco fora da thread da GUI."""


from PySide6.QtCore import QCoreApplication, QDeadlineTimer, QEventLoop

from trackclassifier.ui.update_worker import VerificadorDeAtualizacao
from trackclassifier.updates import Release, UpdateError


def _roda_ate(sinal, timeout_ms=2000):
    """Bombeia o loop de eventos ate o sinal disparar ou estourar o prazo.

    Mesmo motivo de tests/test_counts_worker.py: o resultado atravessa do
    QThreadPool de volta para a thread da GUI por conexao em fila.
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


def _release(versao="0.9.0"):
    return Release(
        version=versao,
        url_zip="https://z/app.zip",
        url_sha256="https://z/s",
        notas="notas",
        recomputa=frozenset({"features"}),
    )


def test_checar_emite_disponivel_com_versao_maior(qapp):
    verificador = VerificadorDeAtualizacao(
        versao_atual="0.1.0", buscar=lambda: _release("0.9.0")
    )

    verificador.checar()

    args = _roda_ate(verificador.disponivel)

    assert args[0].version == "0.9.0"


def test_checar_emite_sem_novidade_na_mesma_versao(qapp):
    verificador = VerificadorDeAtualizacao(
        versao_atual="0.9.0", buscar=lambda: _release("0.9.0")
    )

    verificador.checar()

    assert _roda_ate(verificador.sem_novidade) == ()


def test_checar_emite_sem_novidade_quando_nao_ha_release(qapp):
    verificador = VerificadorDeAtualizacao(versao_atual="0.1.0", buscar=lambda: None)

    verificador.checar()

    assert _roda_ate(verificador.sem_novidade) == ()


def test_checar_emite_falhou_com_a_mensagem_do_update_error(qapp):
    def _explode():
        raise UpdateError("Nao foi possivel verificar atualizacoes: rede caiu")

    verificador = VerificadorDeAtualizacao(versao_atual="0.1.0", buscar=_explode)

    verificador.checar()

    args = _roda_ate(verificador.falhou)

    assert "rede caiu" in args[0]


def test_excecao_inesperada_na_busca_vira_falhou_e_nao_derruba_a_thread(qapp):
    def _explode():
        raise RuntimeError("bug meu, nao do usuario")

    verificador = VerificadorDeAtualizacao(versao_atual="0.1.0", buscar=_explode)

    verificador.checar()

    assert _roda_ate(verificador.falhou) is not None


def test_so_a_checagem_mais_recente_emite(qapp):
    """Duas checagens em voo: a mais velha nao pode sobrescrever a nova."""
    import threading

    liberar = threading.Event()
    ordem = []

    def _buscar_lento():
        ordem.append("primeira")
        liberar.wait(timeout=2)
        return _release("0.3.0")

    def _buscar_rapido():
        ordem.append("segunda")
        return _release("0.4.0")

    verificador = VerificadorDeAtualizacao(versao_atual="0.1.0", buscar=_buscar_lento)
    verificador.checar()
    verificador.buscar = _buscar_rapido
    verificador.checar()

    recebidos = []
    verificador.disponivel.connect(lambda r: recebidos.append(r.version))

    prazo = QDeadlineTimer(2000)
    while len(recebidos) < 1 and not prazo.hasExpired():
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if "segunda" in ordem:
            liberar.set()

    assert recebidos == ["0.4.0"]


def test_checagem_em_voo_nao_engole_o_resultado_de_instalacao_em_voo(qapp, tmp_path):
    """Achado #3 da revisao final: checar() e instalar_release() usavam o
    mesmo contador de geracao. Uma instalacao em andamento (menu Atualizar
    clicado, download rodando) que fosse seguida por um checar() (usuario
    aciona "Buscar atualizacoes..." pelo menu enquanto o download roda)
    tinha o resultado da instalacao descartado por _atual(geracao) -- a
    troca do bundle no disco acontecia de verdade, mas a faixa ficava presa
    em "Baixando..." para sempre porque `instalado` nunca era emitido.
    """
    import threading

    comecou = threading.Event()
    liberar = threading.Event()
    chamadas = []

    def _baixar_lento(release, destino, progresso=None):
        # QThreadPool roda em thread de SO de verdade, independente do loop
        # de eventos do Qt -- diferente de `ordem.append` em
        # test_so_a_checagem_mais_recente_emite, aqui a coordenacao com a
        # thread da GUI precisa de um Event porque o teste bloqueia ate a
        # instalacao estar de fato em voo antes de disparar a checagem.
        comecou.set()
        liberar.wait(timeout=2)
        return destino

    verificador = VerificadorDeAtualizacao(
        versao_atual="0.1.0",
        buscar=lambda: _release("0.4.0"),
        baixar=_baixar_lento,
        instalar=lambda zip_baixado, bundle, versao: chamadas.append(versao),
    )

    verificador.instalar_release(_release("0.9.0"), tmp_path / "TrackClassifier.app")

    # So dispara a checagem depois que a instalacao ja esta de fato em voo --
    # senao a corrida que o achado #3 descreve nao acontece.
    assert comecou.wait(timeout=2), "download nao comecou a tempo"
    verificador.checar()
    liberar.set()

    args = _roda_ate(verificador.instalado)

    assert args == ()
    assert chamadas == ["0.9.0"]


def test_instalar_emite_instalado_no_caminho_feliz(qapp, tmp_path):
    chamadas = []

    verificador = VerificadorDeAtualizacao(
        versao_atual="0.1.0",
        baixar=lambda release, destino, progresso=None: destino,
        instalar=lambda zip_baixado, bundle, versao: chamadas.append(versao),
    )

    verificador.instalar_release(_release("0.9.0"), tmp_path / "TrackClassifier.app")

    assert _roda_ate(verificador.instalado) == ()
    assert chamadas == ["0.9.0"]


def test_instalar_emite_falhou_quando_o_checksum_nao_bate(qapp, tmp_path):
    def _baixar_ruim(release, destino, progresso=None):
        raise UpdateError("Download corrompido: o checksum nao confere.")

    verificador = VerificadorDeAtualizacao(versao_atual="0.1.0", baixar=_baixar_ruim)

    verificador.instalar_release(_release(), tmp_path / "TrackClassifier.app")

    args = _roda_ate(verificador.falhou)

    assert "corrompido" in args[0]


def test_instalar_repassa_o_progresso(qapp, tmp_path):
    def _baixar(release, destino, progresso=None):
        progresso(512, 1024)
        return destino

    verificador = VerificadorDeAtualizacao(
        versao_atual="0.1.0",
        baixar=_baixar,
        instalar=lambda zip_baixado, bundle, versao: None,
    )

    verificador.instalar_release(_release(), tmp_path / "TrackClassifier.app")

    assert _roda_ate(verificador.progresso) == (512, 1024)
