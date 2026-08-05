import pytest
from fastapi.testclient import TestClient

from trackclassifier.streaming import ensure_playable, range_response
from trackclassifier.web import create_app
from tests.test_service import ExtratorFalso, _config, _povoa


@pytest.fixture
def arquivo(tmp_path):
    caminho = tmp_path / "a.mp3"
    caminho.write_bytes(bytes(range(256)))
    return caminho


def test_resposta_completa_sem_cabecalho_range(arquivo):
    resposta = range_response(arquivo, None)

    assert resposta.status_code == 200
    assert resposta.headers["accept-ranges"] == "bytes"
    assert resposta.body == bytes(range(256))


def test_resposta_parcial_com_cabecalho_range(arquivo):
    resposta = range_response(arquivo, "bytes=10-19")

    assert resposta.status_code == 206
    assert resposta.headers["content-range"] == "bytes 10-19/256"
    assert resposta.headers["content-length"] == "10"
    assert resposta.body == bytes(range(10, 20))


def test_range_aberto_vai_ate_o_fim(arquivo):
    resposta = range_response(arquivo, "bytes=250-")

    assert resposta.status_code == 206
    assert resposta.headers["content-range"] == "bytes 250-255/256"


def test_range_alem_do_tamanho_e_truncado(arquivo):
    resposta = range_response(arquivo, "bytes=200-999")

    assert resposta.status_code == 206
    assert resposta.headers["content-range"] == "bytes 200-255/256"


def test_range_malformado_devolve_arquivo_completo(arquivo):
    resposta = range_response(arquivo, "coisas=abc")

    assert resposta.status_code == 200


def test_formato_nativo_nao_e_transcodificado(arquivo, tmp_path):
    assert ensure_playable(arquivo, tmp_path / "cache") == arquivo


def test_endpoint_de_audio_responde_com_o_conteudo(tmp_path):
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.9.mp3").write_bytes(b"conteudo de audio falso")
    servico = TrackService(config, extractor=ExtratorFalso())
    servico.analyze_all()
    servico.train()
    client = TestClient(create_app(servico))
    sha1 = client.get("/api/queue").json()["items"][0]["sha1"]

    resposta = client.get(f"/api/audio/{sha1}")

    assert resposta.status_code == 200
    assert resposta.content == b"conteudo de audio falso"


def test_endpoint_de_audio_com_sha1_desconhecido_retorna_404(tmp_path):
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    _povoa(config)
    servico = TrackService(config, extractor=ExtratorFalso())
    servico.analyze_all()
    servico.train()

    resposta = TestClient(create_app(servico)).get("/api/audio/naoexiste")

    assert resposta.status_code == 404
