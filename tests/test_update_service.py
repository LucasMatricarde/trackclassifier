"""ServicoDeAtualizacao: o fluxo de update do `dj serve`, sem Qt e sem rede."""

import threading
import time

import pytest

from trackclassifier.update_service import (
    BAIXANDO,
    CONCLUIDO,
    FALHOU,
    InstalacaoEmAndamento,
    ServicoDeAtualizacao,
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


def _servico(tmp_path, *, release=None, bundle=True, estado=None, **seams):
    """Servico com tudo falso; `seams` sobrescreve buscar/baixar/instalar/verificar."""
    padrao = {
        "buscar": lambda: release,
        "baixar": lambda r, destino, progresso=None: destino,
        "instalar": lambda zip_baixado, bundle_, versao: None,
        "verificar": lambda bundle_: None,
    }
    n_tracks = seams.pop("n_tracks", lambda: 0)
    padrao.update(seams)
    return ServicoDeAtualizacao(
        bundle=(tmp_path / "TrackClassifier.app") if bundle else None,
        estado=lambda: estado,
        n_tracks=n_tracks,
        versao_atual="0.1.0",
        **padrao,
    )


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
    servico = _servico(
        tmp_path, bundle=False, buscar=lambda: buscou.append(1) or _release()
    )

    assert servico.checa(manual=True) == {"supported": False, "available": False}
    assert buscou == []


def test_checa_oferece_a_versao_nova_com_o_texto_do_dialogo(tmp_path):
    servico = _servico(tmp_path, release=_release("0.9.0"))

    resposta = servico.checa(manual=True)

    assert resposta["supported"] and resposta["available"]
    assert resposta["version"] == "0.9.0"
    assert "0.1.0" in resposta["text"] and "0.9.0" in resposta["text"]


def test_checa_sem_versao_nova_nao_oferece(tmp_path):
    servico = _servico(tmp_path, release=_release("0.1.0"))

    assert servico.checa(manual=True) == {"supported": True, "available": False}


def test_checa_sem_release_utilizavel_nao_oferece(tmp_path):
    servico = _servico(tmp_path, release=None)

    assert servico.checa(manual=True) == {"supported": True, "available": False}


def test_automatica_respeita_o_intervalo_de_um_dia(tmp_path):
    estado = EstadoDeAtualizacao(tmp_path / "updates.json", agora=lambda: 1000.0)
    estado.marca_checagem()
    buscou = []
    servico = _servico(
        tmp_path,
        estado=estado,
        buscar=lambda: buscou.append(1) or _release(),
    )

    assert servico.checa(manual=False) == {"supported": True, "available": False}
    assert buscou == []


def test_manual_ignora_o_intervalo(tmp_path):
    estado = EstadoDeAtualizacao(tmp_path / "updates.json", agora=lambda: 1000.0)
    estado.marca_checagem()
    servico = _servico(tmp_path, estado=estado, release=_release())

    assert servico.checa(manual=True)["available"] is True


def test_automatica_marca_a_checagem_mesmo_quando_a_rede_falha(tmp_path):
    """Sem marcar antes, cada boot sem rede repetiria a requisicao ao GitHub."""
    estado = EstadoDeAtualizacao(tmp_path / "updates.json", agora=lambda: 1000.0)

    def _sem_rede():
        raise UpdateError("sem rede")

    servico = _servico(tmp_path, estado=estado, buscar=_sem_rede)

    assert servico.checa(manual=False) == {"supported": True, "available": False}
    assert estado.deve_checar() is False


def test_manual_deixa_o_erro_de_rede_subir(tmp_path):
    def _sem_rede():
        raise UpdateError("sem rede")

    servico = _servico(tmp_path, buscar=_sem_rede)

    with pytest.raises(UpdateError, match="sem rede"):
        servico.checa(manual=True)


def test_versao_dispensada_some_na_automatica_mas_volta_na_manual(tmp_path):
    estado = EstadoDeAtualizacao(tmp_path / "updates.json")
    estado.dispensa("0.9.0")
    servico = _servico(tmp_path, estado=estado, release=_release("0.9.0"))

    assert servico.checa(manual=False)["available"] is False
    assert servico.checa(manual=True)["available"] is True


def test_dispensa_grava_a_versao_oferecida(tmp_path):
    estado = EstadoDeAtualizacao(tmp_path / "updates.json")
    servico = _servico(tmp_path, estado=estado, release=_release("0.9.0"))
    servico.checa(manual=True)

    servico.dispensa()

    assert estado.esta_dispensada("0.9.0")


def test_so_conta_as_tracks_quando_a_versao_recalcula_a_analise(tmp_path):
    contagens = []

    def _conta():
        contagens.append(1)
        return 463

    sem = _servico(tmp_path, release=_release(), n_tracks=_conta)
    sem.checa(manual=True)
    assert contagens == []

    com = _servico(
        tmp_path, release=_release(recomputa=frozenset({"features"})), n_tracks=_conta
    )
    assert "463 tracks" in com.checa(manual=True)["text"]
    assert contagens == [1]


def test_instala_verifica_baixa_e_troca_nessa_ordem(tmp_path):
    ordem = []

    def _baixar(release, destino, progresso=None):
        ordem.append("baixar")
        progresso(512, 1024)
        return destino

    servico = _servico(
        tmp_path,
        release=_release("0.9.0"),
        verificar=lambda bundle: ordem.append("verificar"),
        baixar=_baixar,
        instalar=lambda zip_baixado, bundle, versao: ordem.append(f"instalar {versao}"),
    )
    servico.checa(manual=True)

    servico.instala_pendente()
    final = _espera(servico, {CONCLUIDO, FALHOU})

    assert ordem == ["verificar", "baixar", "instalar 0.9.0"]
    assert final == {"state": CONCLUIDO, "done": 512, "total": 1024, "error": None}


def test_instala_sem_atualizacao_pendente_recusa(tmp_path):
    servico = _servico(tmp_path, release=_release())

    with pytest.raises(UpdateError, match="Nao ha atualizacao"):
        servico.instala_pendente()


def test_segunda_instalacao_durante_o_download_e_recusada(tmp_path):
    segura = threading.Event()

    def _baixar_devagar(release, destino, progresso=None):
        segura.wait(2)
        return destino

    servico = _servico(tmp_path, release=_release(), baixar=_baixar_devagar)
    servico.checa(manual=True)
    servico.instala_pendente()

    try:
        assert servico.status()["state"] == BAIXANDO
        with pytest.raises(InstalacaoEmAndamento):
            servico.instala_pendente()
    finally:
        segura.set()
    _espera(servico, {CONCLUIDO})


def test_bundle_nao_instalavel_falha_sem_baixar_nada(tmp_path):
    baixou = []

    def _recusa(bundle):
        raise UpdateError("O macOS abriu o app de uma copia temporaria.")

    servico = _servico(
        tmp_path,
        release=_release(),
        verificar=_recusa,
        baixar=lambda r, destino, progresso=None: baixou.append(1) or destino,
    )
    servico.checa(manual=True)

    servico.instala_pendente()
    final = _espera(servico, {FALHOU})

    assert "copia temporaria" in final["error"]
    assert baixou == []


def test_checksum_ruim_vira_falha_com_a_mensagem(tmp_path):
    def _baixar_ruim(release, destino, progresso=None):
        raise UpdateError("Download corrompido: o checksum nao confere.")

    servico = _servico(tmp_path, release=_release(), baixar=_baixar_ruim)
    servico.checa(manual=True)

    servico.instala_pendente()

    assert "corrompido" in _espera(servico, {FALHOU})["error"]


def test_erro_inesperado_vira_falha_e_nao_mata_a_thread_em_silencio(tmp_path):
    def _quebra(zip_baixado, bundle, versao):
        raise OSError("disco cheio")

    servico = _servico(tmp_path, release=_release(), instalar=_quebra)
    servico.checa(manual=True)

    servico.instala_pendente()
    final = _espera(servico, {FALHOU})

    assert final["error"] == "Falha na atualizacao: disco cheio"


def test_depois_de_falhar_da_para_tentar_de_novo(tmp_path):
    tentativas = []

    def _instalar(zip_baixado, bundle, versao):
        tentativas.append(1)
        if len(tentativas) == 1:
            raise UpdateError("primeira falha")

    servico = _servico(tmp_path, release=_release(), instalar=_instalar)
    servico.checa(manual=True)

    servico.instala_pendente()
    _espera(servico, {FALHOU})
    servico.instala_pendente()
    final = _espera(servico, {CONCLUIDO})

    assert final["error"] is None
