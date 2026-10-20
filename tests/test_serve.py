"""Testes do servidor FastAPI (serve.py).

Usa httpx.AsyncClient com ASGI transport para testar sem subir uvicorn.
O ExtratorFalso dos outros testes é reutilizado via conftest.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from trackclassifier.config import Config, read_raw
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
    serve_mod._config_path = None

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
async def test_config_usa_o_arquivo_de_onde_foi_carregado(client, tmp_path, monkeypatch):
    import trackclassifier.serve as serve_mod

    outro = tmp_path / "outro.toml"
    outro.write_text(
        'active_profile = "outro"\n[profiles.outro.folders]\ninbox = "/tmp/entrada"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(serve_mod, "_config_path", outro)

    r = await client.get(f"/api/config?token={_token}")
    assert r.status_code == 200
    assert r.json()["raw"]["active_profile"] == "outro"


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


# ---------------------------------------------------------------------------
# Build do front (mount estatico)
# ---------------------------------------------------------------------------


def _dist_falso(base):
    pasta = base / "dist"
    (pasta / "assets").mkdir(parents=True)
    (pasta / "index.html").write_text("<!doctype html><title>TrackClassifier</title>", "utf-8")
    (pasta / "assets" / "app.js").write_text("console.log('ok')", "utf-8")
    return pasta


def _pastas_de_perfil(base, prefixo):
    caminhos = {}
    for chave in ("inbox", "up", "neutral", "down"):
        caminho = base / f"{prefixo}_{chave}"
        caminho.mkdir()
        caminhos[chave] = str(caminho)
    return caminhos


@pytest.mark.asyncio
async def test_apply_config_grava_e_preserva_perfis(client, tmp_path):
    raw = {
        "active_profile": "b",
        "profiles": {
            "a": {"folders": _pastas_de_perfil(tmp_path, "a")},
            "b": {"folders": _pastas_de_perfil(tmp_path, "b")},
        },
        "paths": {"data_dir": str(tmp_path / "data")},
        "model": {"retrain_every": 7, "min_examples": 9},
    }

    r = await client.post(f"/api/config/apply?token={_token}", json={"raw": raw})
    assert r.status_code == 200, r.text

    gravado = read_raw(tmp_path / "config.toml")
    assert set(gravado["profiles"]) == {"a", "b"}
    assert gravado["active_profile"] == "b"
    assert gravado["profiles"]["a"]["folders"]["inbox"] == raw["profiles"]["a"]["folders"]["inbox"]
    assert gravado["model"]["retrain_every"] == 7
    assert gravado["model"]["min_examples"] == 9


@pytest.mark.asyncio
async def test_apply_config_invalido_nao_grava(client, tmp_path):
    pastas = _pastas_de_perfil(tmp_path, "x")
    pastas["up"] = str(tmp_path / "nao-existe")
    raw = {
        "folders": pastas,
        "paths": {"data_dir": str(tmp_path / "data")},
    }

    r = await client.post(f"/api/config/apply?token={_token}", json={"raw": raw})
    assert r.status_code == 400
    assert not (tmp_path / "config.toml").exists()


@pytest.mark.asyncio
async def test_mount_web_serve_index_e_assets(tmp_path):
    from fastapi import FastAPI

    from trackclassifier.serve import _mount_web

    app_teste = FastAPI()
    assert _mount_web(app_teste, _dist_falso(tmp_path)) is True

    async with AsyncClient(
        transport=ASGITransport(app=app_teste), base_url="http://t"
    ) as c:
        raiz = await c.get("/")
        assert raiz.status_code == 200
        assert "TrackClassifier" in raiz.text

        asset = await c.get("/assets/app.js")
        assert asset.status_code == 200
        assert "ok" in asset.text


def test_mount_web_sem_index_nao_monta(tmp_path):
    from fastapi import FastAPI

    from trackclassifier.serve import _mount_web

    # dist/ existe mas o build morreu no meio (sem index.html): montar
    # serviria 404 em tudo e esconderia o erro.
    (tmp_path / "dist").mkdir()
    assert _mount_web(FastAPI(), tmp_path / "dist") is False


def test_web_dist_encontra_o_build_do_checkout():
    from trackclassifier.serve import _web_dist

    # No CI o front nao e buildado e a funcao devolve None; a assercao so
    # vale quando o build existe (maquina de dev ou release).
    pasta = _web_dist()
    if pasta is not None:
        assert (pasta / "index.html").is_file()

