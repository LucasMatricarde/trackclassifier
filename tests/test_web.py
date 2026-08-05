import pytest
from fastapi.testclient import TestClient

from trackclassifier.labels import Label
from trackclassifier.web import create_app
from tests.test_service import ExtratorFalso, _config, _povoa


@pytest.fixture
def cliente(tmp_path):
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    _povoa(config)
    for nome in ("clara_0.99.mp3", "duvidosa_0.34.mp3"):
        (config.inbox / nome).write_bytes(nome.encode())

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()
    servico.train()
    return TestClient(create_app(servico)), servico


def test_fila_retorna_itens_ordenados_por_confianca(cliente):
    client, _ = cliente

    corpo = client.get("/api/queue").json()

    confiancas = [item["confidence"] for item in corpo["items"]]
    assert confiancas == sorted(confiancas)
    assert corpo["low_confidence_mode"] is False
    assert corpo["metrics"]["n_examples"] == 18


def test_item_da_fila_traz_os_campos_da_interface(cliente):
    client, _ = cliente

    item = client.get("/api/queue").json()["items"][0]

    for campo in (
        "sha1", "filename", "label", "score", "confidence",
        "bpm", "duration_s", "energy_curve", "peak_offset_s",
    ):
        assert campo in item
    assert item["label"] in ("+1", "neutra", "-1")


def test_decide_move_o_arquivo_e_tira_da_fila(cliente):
    client, servico = cliente
    sha1 = client.get("/api/queue").json()["items"][0]["sha1"]

    resposta = client.post("/api/decide", json={"sha1": sha1, "label": "-1"})

    assert resposta.status_code == 200
    assert resposta.json() == {"retrained": False}
    restantes = [item["sha1"] for item in client.get("/api/queue").json()["items"]]
    assert sha1 not in restantes
    assert (servico.config.folders[Label.DOWN] / "duvidosa_0.34.mp3").is_file()


def test_decide_com_sha1_desconhecido_retorna_404(cliente):
    client, _ = cliente

    resposta = client.post("/api/decide", json={"sha1": "naoexiste", "label": "+1"})

    assert resposta.status_code == 404


def test_decide_com_rotulo_invalido_retorna_422(cliente):
    client, _ = cliente
    sha1 = client.get("/api/queue").json()["items"][0]["sha1"]

    resposta = client.post("/api/decide", json={"sha1": sha1, "label": "talvez"})

    assert resposta.status_code == 422


def test_aprovacao_em_bloco_reporta_quantidade(cliente):
    client, _ = cliente
    confiancas = [item["confidence"] for item in client.get("/api/queue").json()["items"]]

    resposta = client.post("/api/bulk-approve", json={"min_confidence": max(confiancas)})

    assert resposta.json() == {"moved": 1}


def test_endpoint_de_falhas(tmp_path):
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "ruim_0.5.mp3").write_bytes(b"x")
    servico = TrackService(
        config, extractor=ExtratorFalso(falhar_em={"ruim_0.5.mp3"}), max_workers=1
    )
    servico.analyze_all()
    servico.train()

    corpo = TestClient(create_app(servico)).get("/api/failures").json()

    assert corpo["items"][0]["filename"] == "ruim_0.5.mp3"
    assert "falha proposital" in corpo["items"][0]["reason"]


def test_raiz_serve_a_pagina(cliente):
    client, _ = cliente

    resposta = client.get("/")

    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
