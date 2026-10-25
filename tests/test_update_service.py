"""UpdateService: o fluxo de update do `dj serve`, sem rede."""

import threading
import time

import pytest

from trackclassifier.update_service import (
    DONE,
    DOWNLOADING,
    FAILED,
    AlreadyInstalled,
    InstallInProgress,
    UpdateService,
)
from trackclassifier.update_state import EstadoDeAtualizacao
from trackclassifier.updates import Release, UpdateError


def _release(versao="0.9.0", recomputa=frozenset()):
    return Release(
        version=versao,
        url_zip="https://z/app.zip",
        url_sha256="https://z/s",
        notas="notas",
        recomputa=recomputa,
    )


def _servico(tmp_path, *, release=None, bundle=True, state=None, **seams):
    """Servico com tudo falso; `seams` sobrescreve fetch/download/install/verify."""
    n_tracks = seams.pop("n_tracks", lambda: 0)
    padrao = {
        "fetch": lambda: release,
        "download": lambda r, destino, progresso=None: destino,
        "install": lambda zip_baixado, bundle_, versao: None,
        "verify": lambda bundle_: None,
    }
    padrao.update(seams)
    return UpdateService(
        bundle=(tmp_path / "TrackClassifier.app") if bundle else None,
        state=lambda: state,
        n_tracks=n_tracks,
        current_version="0.1.0",
        **padrao,
    )


def _estado(tmp_path, agora=lambda: 1000.0):
    return EstadoDeAtualizacao(tmp_path / "updates.json", agora=agora)


def _espera(servico, situacoes, timeout=2.0):
    """A instalacao roda numa thread: espera o status chegar a um dos estados."""
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        atual = servico.status()
        if atual["state"] in situacoes:
            return atual
        time.sleep(0.005)
    raise AssertionError(f"status nao chegou a {situacoes}: {servico.status()}")


def test_sem_bundle_nao_ha_o_que_atualizar_e_nem_busca(tmp_path):
    buscou = []
    servico = _servico(tmp_path, bundle=False, fetch=lambda: buscou.append(1) or _release())

    assert servico.check(manual=True) == {"supported": False, "available": False}
    assert buscou == []


def test_check_oferece_a_versao_nova_com_o_texto_do_dialogo(tmp_path):
    servico = _servico(tmp_path, release=_release("0.9.0"))

    resposta = servico.check(manual=True)

    assert resposta["supported"] and resposta["available"]
    assert resposta["version"] == "0.9.0"
    assert "0.1.0" in resposta["text"] and "0.9.0" in resposta["text"]


def test_check_sem_versao_nova_nao_oferece(tmp_path):
    servico = _servico(tmp_path, release=_release("0.1.0"))

    assert servico.check(manual=True) == {"supported": True, "available": False}


def test_check_sem_release_utilizavel_nao_oferece(tmp_path):
    servico = _servico(tmp_path, release=None)

    assert servico.check(manual=True) == {"supported": True, "available": False}


def test_automatica_respeita_o_intervalo_de_um_dia(tmp_path):
    estado = _estado(tmp_path)
    estado.marca_checagem()
    buscou = []
    servico = _servico(
        tmp_path, state=estado, fetch=lambda: buscou.append(1) or _release()
    )

    assert servico.check(manual=False) == {"supported": True, "available": False}
    assert buscou == []


def test_manual_ignora_o_intervalo(tmp_path):
    estado = _estado(tmp_path)
    estado.marca_checagem()
    servico = _servico(tmp_path, state=estado, release=_release())

    assert servico.check(manual=True)["available"] is True


def test_automatica_marca_a_checagem_mesmo_quando_a_rede_falha(tmp_path):
    """Sem marcar antes, cada boot sem rede repetiria a requisicao ao GitHub."""
    estado = _estado(tmp_path)

    def _sem_rede():
        raise UpdateError("sem rede")

    servico = _servico(tmp_path, state=estado, fetch=_sem_rede)

    assert servico.check(manual=False) == {"supported": True, "available": False}
    assert estado.deve_checar() is False


def test_automatica_no_primeiro_uso_nao_busca_nem_oferece(tmp_path):
    """Sem data_dir (setup) nao ha onde lembrar a checagem nem a dispensa."""
    buscou = []
    servico = _servico(tmp_path, state=None, fetch=lambda: buscou.append(1) or _release())

    assert servico.check(manual=False) == {"supported": True, "available": False}
    assert buscou == []


def test_manual_no_primeiro_uso_funciona(tmp_path):
    servico = _servico(tmp_path, state=None, release=_release())

    assert servico.check(manual=True)["available"] is True


def test_manual_deixa_o_erro_de_rede_subir(tmp_path):
    def _sem_rede():
        raise UpdateError("sem rede")

    servico = _servico(tmp_path, fetch=_sem_rede)

    with pytest.raises(UpdateError, match="sem rede"):
        servico.check(manual=True)


def test_versao_dispensada_some_na_automatica_mas_volta_na_manual(tmp_path):
    estado = _estado(tmp_path)
    estado.dispensa("0.9.0")
    servico = _servico(tmp_path, state=estado, release=_release("0.9.0"))

    assert servico.check(manual=False)["available"] is False
    assert servico.check(manual=True)["available"] is True


def test_dismiss_grava_a_versao_oferecida(tmp_path):
    estado = _estado(tmp_path)
    servico = _servico(tmp_path, state=estado, release=_release("0.9.0"))
    servico.check(manual=True)

    servico.dismiss()

    assert estado.esta_dispensada("0.9.0")


def test_dismiss_sem_oferta_nao_grava_nada(tmp_path):
    estado = _estado(tmp_path)
    servico = _servico(tmp_path, state=estado, release=None)
    servico.check(manual=True)

    servico.dismiss()

    assert not (tmp_path / "updates.json").exists()


def test_so_conta_as_tracks_quando_a_versao_recalcula_a_analise(tmp_path):
    contagens = []

    def _conta():
        contagens.append(1)
        return 463

    sem = _servico(tmp_path, release=_release(), n_tracks=_conta)
    sem.check(manual=True)
    assert contagens == []

    com = _servico(
        tmp_path, release=_release(recomputa=frozenset({"features"})), n_tracks=_conta
    )
    assert "463 tracks" in com.check(manual=True)["text"]
    assert contagens == [1]


def test_contagem_de_tracks_que_falha_nao_derruba_a_checagem(tmp_path):
    """No primeiro uso nao ha servico: o numero e so uma frase do texto."""

    def _sem_servico():
        raise RuntimeError("Servico nao inicializado")

    servico = _servico(
        tmp_path,
        release=_release(recomputa=frozenset({"features"})),
        n_tracks=_sem_servico,
    )

    resposta = servico.check(manual=True)

    assert resposta["available"] is True
    assert "0 tracks" in resposta["text"]


def test_install_verifica_baixa_e_troca_nessa_ordem(tmp_path):
    ordem = []

    def _baixar(release, destino, progresso=None):
        ordem.append("baixar")
        progresso(512, 1024)
        return destino

    servico = _servico(
        tmp_path,
        release=_release("0.9.0"),
        verify=lambda bundle: ordem.append("verificar"),
        download=_baixar,
        install=lambda zip_baixado, bundle, versao: ordem.append(f"instalar {versao}"),
    )
    servico.check(manual=True)

    servico.install_pending("0.9.0")
    final = _espera(servico, {DONE, FAILED})

    assert ordem == ["verificar", "baixar", "instalar 0.9.0"]
    assert final == {"state": DONE, "done": 512, "total": 1024, "error": None}


def test_install_sem_atualizacao_pendente_recusa(tmp_path):
    servico = _servico(tmp_path, release=_release())

    with pytest.raises(UpdateError, match="Nao ha atualizacao"):
        servico.install_pending()


def test_install_recusa_depois_que_a_busca_nao_achou_mais_nada(tmp_path):
    """Um check sem novidade zera a oferta: nao se instala o que nao esta mais la."""
    releases = [_release("0.9.0"), None]
    servico = _servico(tmp_path, fetch=lambda: releases.pop(0))
    servico.check(manual=True)
    servico.check(manual=True)

    with pytest.raises(UpdateError, match="Nao ha atualizacao"):
        servico.install_pending()


def test_install_recusa_versao_diferente_da_que_o_usuario_viu(tmp_path):
    releases = [_release("0.9.0"), _release("0.9.1")]
    servico = _servico(tmp_path, fetch=lambda: releases.pop(0))
    servico.check(manual=True)  # o dialogo mostrou 0.9.0
    servico.check(manual=True)  # um segundo check trocou a oferta para 0.9.1

    with pytest.raises(UpdateError, match="mudou para 0.9.1"):
        servico.install_pending("0.9.0")


def test_segunda_instalacao_durante_o_download_e_recusada(tmp_path):
    segura = threading.Event()

    def _baixar_devagar(release, destino, progresso=None):
        segura.wait(2)
        return destino

    servico = _servico(tmp_path, release=_release(), download=_baixar_devagar)
    servico.check(manual=True)
    servico.install_pending()

    try:
        assert servico.status()["state"] == DOWNLOADING
        with pytest.raises(InstallInProgress):
            servico.install_pending()
    finally:
        segura.set()
    _espera(servico, {DONE})


def test_check_durante_o_download_diz_que_esta_em_andamento_sem_buscar(tmp_path):
    segura = threading.Event()
    buscas = []

    def _buscar():
        buscas.append(1)
        return _release()

    servico = _servico(
        tmp_path,
        fetch=_buscar,
        download=lambda r, destino, progresso=None: segura.wait(2) and destino,
    )
    servico.check(manual=True)
    servico.install_pending()

    try:
        resposta = servico.check(manual=True)
    finally:
        segura.set()
    _espera(servico, {DONE})

    assert resposta == {"supported": True, "available": False, "in_progress": True}
    assert buscas == [1]


def test_depois_de_concluir_o_estado_e_terminal(tmp_path):
    """O processo ainda e a versao velha: oferecer ou reinstalar seria um laco."""
    servico = _servico(tmp_path, release=_release())
    servico.check(manual=True)
    servico.install_pending()
    _espera(servico, {DONE})

    assert servico.check(manual=True) == {
        "supported": True,
        "available": False,
        "installed": True,
    }
    # Subclasse propria: o servidor responde 409 (estado), nao 400 (pedido ruim).
    with pytest.raises(AlreadyInstalled, match="ja foi instalada"):
        servico.install_pending()


def test_bundle_nao_instalavel_falha_sem_baixar_nada(tmp_path):
    baixou = []

    def _recusa(bundle):
        raise UpdateError("O macOS abriu o app de uma copia temporaria.")

    servico = _servico(
        tmp_path,
        release=_release(),
        verify=_recusa,
        download=lambda r, destino, progresso=None: baixou.append(1) or destino,
    )
    servico.check(manual=True)

    servico.install_pending()
    final = _espera(servico, {FAILED})

    assert "copia temporaria" in final["error"]
    assert baixou == []


def test_checksum_ruim_vira_falha_com_a_mensagem(tmp_path):
    def _baixar_ruim(release, destino, progresso=None):
        raise UpdateError("Download corrompido: o checksum nao confere.")

    servico = _servico(tmp_path, release=_release(), download=_baixar_ruim)
    servico.check(manual=True)

    servico.install_pending()

    assert "corrompido" in _espera(servico, {FAILED})["error"]


def test_erro_inesperado_vira_falha_e_nao_mata_a_thread_em_silencio(tmp_path):
    def _quebra(zip_baixado, bundle, versao):
        raise OSError("disco cheio")

    servico = _servico(tmp_path, release=_release(), install=_quebra)
    servico.check(manual=True)

    servico.install_pending()
    final = _espera(servico, {FAILED})

    assert final["error"] == "Falha na atualizacao: disco cheio"


def test_depois_de_falhar_da_para_tentar_de_novo(tmp_path):
    tentativas = []

    def _instalar(zip_baixado, bundle, versao):
        tentativas.append(1)
        if len(tentativas) == 1:
            raise UpdateError("primeira falha")

    servico = _servico(tmp_path, release=_release(), install=_instalar)
    servico.check(manual=True)

    servico.install_pending()
    _espera(servico, {FAILED})
    servico.install_pending()
    final = _espera(servico, {DONE})

    assert final["error"] is None


def test_check_lento_nao_sobrescreve_a_oferta_de_uma_instalacao_em_curso(tmp_path):
    """A busca roda fora do lock e leva ate 10s: um install pode comecar nesse meio tempo.

    Gravar o release novo por cima do download em curso deixaria, depois de uma
    falha, uma oferta pendente (0.9.1) que o usuario nunca viu.
    """
    busca_pode_seguir = threading.Event()
    segundo_check_na_rede = threading.Event()
    download_pode_seguir = threading.Event()
    ofertas = [_release("0.9.0"), _release("0.9.1")]
    instalou = []

    def _fetch():
        release = ofertas.pop(0)
        if release.version == "0.9.1":
            segundo_check_na_rede.set()  # avisa: ja estou DENTRO do fetch
            busca_pode_seguir.wait(2)  # e fico preso na rede
        return release

    chamadas_de_download = []

    def _baixar(release, destino, progresso=None):
        chamadas_de_download.append(release.version)
        if len(chamadas_de_download) == 1:
            download_pode_seguir.wait(2)
            raise UpdateError("caiu no meio")
        return destino

    servico = _servico(
        tmp_path,
        fetch=_fetch,
        download=_baixar,
        install=lambda zip_baixado, bundle, versao: instalou.append(versao),
    )
    servico.check(manual=True)  # oferta 0.9.0, o que o usuario viu

    resposta = {}
    segundo = threading.Thread(
        target=lambda: resposta.update(servico.check(manual=True)), daemon=True
    )
    segundo.start()
    # Barreira: sem ela, sob um CI carregado o segundo check poderia so comecar
    # DEPOIS do install_pending, cair no atalho de "ja em andamento" e o teste
    # passaria sem nunca exercitar a gravacao da oferta (nem sem a correcao).
    assert segundo_check_na_rede.wait(2), "o segundo check nao chegou ao fetch"
    servico.install_pending("0.9.0")  # comeca enquanto o segundo check espera a rede
    busca_pode_seguir.set()
    segundo.join(2)

    assert resposta == {"supported": True, "available": False, "in_progress": True}

    download_pode_seguir.set()
    _espera(servico, {FAILED})
    # A oferta pendente continua sendo a 0.9.0: tentar de novo instala o que o
    # usuario viu, e nao a 0.9.1 que so o check lento conheceu.
    servico.install_pending()
    _espera(servico, {DONE})
    assert chamadas_de_download == ["0.9.0", "0.9.0"]
    assert instalou == ["0.9.0"]


def test_contagem_de_tracks_que_falha_fica_no_log(tmp_path, caplog):
    def _quebra():
        raise AttributeError("bug na biblioteca")

    servico = _servico(
        tmp_path,
        release=_release(recomputa=frozenset({"features"})),
        n_tracks=_quebra,
    )

    with caplog.at_level("WARNING", logger="trackclassifier.update_service"):
        resposta = servico.check(manual=True)

    assert resposta["available"] is True
    assert any("contar as tracks" in r.getMessage() for r in caplog.records)
    assert any(r.exc_info for r in caplog.records)
