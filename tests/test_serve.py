"""Testes do servidor FastAPI (serve.py).

Usa httpx.AsyncClient com ASGI transport para testar sem subir uvicorn.
O ExtratorFalso dos outros testes é reutilizado via conftest.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from trackclassifier.config import Config
from trackclassifier.labels import Label
from trackclassifier.serve import _token, app
from trackclassifier.service import TrackService


@pytest.fixture()
def service(tmp_path):
    """TrackService com ExtratorFalso e pastas temporárias."""
    from tests.test_service import ExtratorFalso

    for name in ("up", "neutral", "down", "inbox"):
        (tmp_path / name).mkdir(exist_ok=True)

    config = Config.from_folders(
        folders={
            Label.UP: tmp_path / "up",
            Label.NEUTRAL: tmp_path / "neutral",
            Label.DOWN: tmp_path / "down",
        },
        inbox=tmp_path / "inbox",
        data_dir=tmp_path / "data",
        retrain_every=10,
        min_examples=5,
    )
    svc = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    return svc


@pytest.fixture()
async def client(service):
    """AsyncClient com o serviço injetado no estado do app."""
    # Injeta o serviço no módulo (o app usa variáveis globais)
    import trackclassifier.serve as serve_mod

    serve_mod._service = service
    serve_mod._config = service.config

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["token"] == _token


@pytest.mark.asyncio
async def test_review_state_empty(client):
    r = await client.get(f"/api/review/state?token={_token}")
    assert r.status_code == 200
    data = r.json()
    assert data["current"] is None
    assert data["remaining"] == 0
    assert data["active_profile"] == "default"


@pytest.mark.asyncio
async def test_review_state_requires_token(client):
    r = await client.get("/api/review/state?token=wrong")
    assert r.status_code in (401, 422)


@pytest.mark.asyncio
async def test_decide_and_undo(client):
    # Sem tracks na inbox, decide deve dar 404
    r = await client.post(
        f"/api/review/decide?token={_token}",
        json={"sha1": "abc123", "label": 1},
    )
    assert r.status_code in (404, 500)


@pytest.mark.asyncio
async def test_decide_mapeia_indice_para_label(client, service):
    """O fluxo real: scan -> decide por indice (teclado 1/2/3) -> undo.

    Regressao dupla: decide por int (0) tem que virar Label.NEUTRAL (antes
    Label("0") estourava 500) e o token via header X-Auth-Token tem que
    autenticar igual a query string (o front manda header no REST).

    O modelo precisa estar treinado: service.queue() devolve [] quando
    is_fitted e False, e sem fila o decide cai no caminho de reclassify.
    """
    from tests.test_service import _povoa

    _povoa(service.config)
    service.analyze_all()
    service.train()

    (service.config.inbox / "nova_0.750.mp3").write_bytes(b"nova")
    r = await client.post(f"/api/scan?token={_token}", json={})
    assert r.status_code == 200

    estado = (await client.get(f"/api/review/state?token={_token}")).json()
    assert estado["current"] is not None
    sha1 = estado["current"]["sha1"]

    # label 0 (tecla "2") -> neutra, autenticando por header
    r = await client.post(
        "/api/review/decide",
        json={"sha1": sha1, "label": 0},
        headers={"X-Auth-Token": _token},
    )
    assert r.status_code == 200, r.text
    assert not (service.config.inbox / "nova_0.750.mp3").exists()
    assert (service.config.folders[Label.NEUTRAL] / "nova_0.750.mp3").exists()

    # undo devolve para a inbox
    r = await client.post(f"/api/review/undo?token={_token}")
    assert r.status_code == 200, r.text
    assert (service.config.inbox / "nova_0.750.mp3").exists()


@pytest.mark.asyncio
async def test_decide_label_invalido(client):
    r = await client.post(
        f"/api/review/decide?token={_token}",
        json={"sha1": "abc123", "label": 7},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_undo_empty(client):
    r = await client.post(f"/api/review/undo?token={_token}")
    assert r.status_code in (400, 500)


@pytest.mark.asyncio
async def test_profiles(client):
    r = await client.get(f"/api/profiles?token={_token}")
    assert r.status_code == 200
    data = r.json()
    assert data["active"] == "default"
    assert "default" in data["all"]


@pytest.mark.asyncio
async def test_switch_profile_invalid(client):
    r = await client.post(
        f"/api/profiles/switch?token={_token}",
        json={"name": "inexistente"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_audio_not_found(client):
    r = await client.get(f"/api/audio/abc123?token={_token}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_cover_not_found(client):
    r = await client.get(f"/api/cover/abc123?token={_token}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_peaks_not_found(client):
    r = await client.get(f"/api/peaks/abc123?token={_token}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_search_empty(client):
    r = await client.get(f"/api/library/search?q=test&token={_token}")
    assert r.status_code == 200
    assert r.json()["rows"] == []


@pytest.mark.asyncio
async def test_scan(client):
    r = await client.post(f"/api/scan?token={_token}", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True


@pytest.mark.asyncio
async def test_config_get(client):
    r = await client.get(f"/api/config?token={_token}")
    assert r.status_code == 200
    data = r.json()
    assert "active_profile" in data
    assert "profiles" in data


@pytest.mark.asyncio
async def test_config_validate(client):
    r = await client.post(
        f"/api/config/validate?token={_token}",
        json={"raw": {}},
    )
    assert r.status_code == 200
    data = r.json()
    assert "valid" in data
    assert "errors" in data
