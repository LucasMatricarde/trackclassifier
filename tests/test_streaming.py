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


def test_range_de_sufixo_devolve_os_ultimos_n_bytes(arquivo):
    resposta = range_response(arquivo, "bytes=-10")

    assert resposta.status_code == 206
    assert resposta.headers["content-range"] == "bytes 246-255/256"
    assert resposta.body == bytes(range(246, 256))


def test_range_de_sufixo_igual_ao_arquivo_inteiro(arquivo):
    resposta = range_response(arquivo, "bytes=-256")

    assert resposta.status_code == 206
    assert resposta.headers["content-range"] == "bytes 0-255/256"
    assert resposta.body == bytes(range(256))


def test_range_de_sufixo_maior_que_o_arquivo_e_truncado(arquivo):
    resposta = range_response(arquivo, "bytes=-9999")

    assert resposta.status_code == 206
    assert resposta.headers["content-range"] == "bytes 0-255/256"
    assert resposta.body == bytes(range(256))


def test_range_de_sufixo_zero_e_tratado_como_malformado(arquivo):
    resposta = range_response(arquivo, "bytes=-0")

    assert resposta.status_code == 200


def test_range_malformado_devolve_arquivo_completo(arquivo):
    resposta = range_response(arquivo, "coisas=abc")

    assert resposta.status_code == 200


def test_range_vazio_devolve_arquivo_completo(arquivo):
    resposta = range_response(arquivo, "bytes=-")

    assert resposta.status_code == 200
    assert "content-range" not in resposta.headers


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


def test_duas_faixas_de_mesmo_nome_nao_colidem_no_cache_de_transcodificacao(tmp_path):
    """Regressao: ensure_playable chaveia o cache por path.stem, entao duas
    faixas-fonte com o mesmo nome de arquivo (comum em rips de DJ, ex.
    "SetA/01.aiff" e "SetB/01.aiff") precisam de caches separados -- senao
    a segunda faixa serve, silenciosamente, o audio transcodificado da
    primeira. register_audio_route evita isso passando um subdiretorio de
    cache por sha1 para ensure_playable.
    """
    import numpy as np
    import soundfile as sf

    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    _povoa(config)

    pasta_a = config.inbox / "SetA"
    pasta_b = config.inbox / "SetB"
    pasta_a.mkdir()
    pasta_b.mkdir()

    sr = 8000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    tom_a = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    tom_b = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    # mesmo nome de arquivo ("01_0.9.aiff") em pastas diferentes, formato
    # que exige transcodificacao (needs_transcode(".aiff") == True).
    sf.write(pasta_a / "01_0.9.aiff", tom_a, sr)
    sf.write(pasta_b / "01_0.9.aiff", tom_b, sr)

    servico = TrackService(config, extractor=ExtratorFalso())
    servico.analyze_all()
    servico.train()
    client = TestClient(create_app(servico))

    itens = client.get("/api/queue").json()["items"]
    sha1s = [item["sha1"] for item in itens if item["filename"] == "01_0.9.aiff"]
    assert len(sha1s) == 2

    resposta_a = client.get(f"/api/audio/{sha1s[0]}")
    resposta_b = client.get(f"/api/audio/{sha1s[1]}")

    assert resposta_a.status_code == 200
    assert resposta_b.status_code == 200
    assert resposta_a.content != resposta_b.content


def test_endpoint_de_audio_com_sha1_desconhecido_retorna_404(tmp_path):
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    _povoa(config)
    servico = TrackService(config, extractor=ExtratorFalso())
    servico.analyze_all()
    servico.train()

    resposta = TestClient(create_app(servico)).get("/api/audio/naoexiste")

    assert resposta.status_code == 404
