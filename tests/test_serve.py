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
async def test_config_stats(client, tmp_path):
    """Pill de novas da entrada, contagens por destino, analises e MB usados.
    Arquivo sem extensao de audio nao entra em nenhuma contagem."""
    (tmp_path / "inbox" / "a.mp3").write_bytes(b"a")
    (tmp_path / "inbox" / "b.flac").write_bytes(b"b")
    (tmp_path / "inbox" / "ignorado.txt").write_text("x", "utf-8")
    (tmp_path / "up" / "u.mp3").write_bytes(b"u")
    (tmp_path / "neutral" / "n1.mp3").write_bytes(b"n1")
    (tmp_path / "neutral" / "n2.mp3").write_bytes(b"n2")
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "ocupado.bin").write_bytes(b"x" * 1024 * 1024)

    r = await client.get(f"/api/config/stats?token={_token}")

    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados["inbox_new"] == 2
    assert dados["destinations"] == {"up": 1, "neutral": 2, "down": 0}
    assert dados["analyses"] == 0
    assert dados["data_dir_mb"] >= 1.0


@pytest.mark.asyncio
async def test_config_stats_sem_config_degrada_para_zero(client, monkeypatch):
    """Primeiro uso: nao ha servico nem config, e a tela de setup nao mostra
    stats -- mas o endpoint nao pode derrubar. Zero em tudo."""
    import trackclassifier.serve as serve_mod

    monkeypatch.setattr(serve_mod, "_service", None)
    monkeypatch.setattr(serve_mod, "_config", None)

    r = await client.get(f"/api/config/stats?token={_token}")

    assert r.status_code == 200
    assert r.json() == {
        "data_dir_mb": 0,
        "analyses": 0,
        "inbox_new": 0,
        "destinations": {"up": 0, "neutral": 0, "down": 0},
    }


@pytest.mark.asyncio
async def test_config_reset_volta_aos_padroes_e_preserva_pastas(client, service, monkeypatch):
    from dataclasses import replace

    import trackclassifier.serve as serve_mod

    serve_mod._config = replace(
        service.config,
        retrain_every=30,
        min_examples=50,
        auto_move_enabled=True,
        create_under_root=True,
    )

    r = await client.post(f"/api/config/reset?token={_token}", json={})

    assert r.status_code == 200, r.text
    gravado = read_raw(service.config.data_dir.parent / "config.toml")
    assert gravado["model"]["retrain_every"] == 10
    assert gravado["model"]["min_examples"] == 15
    assert gravado["model"]["auto_move_enabled"] is False
    assert gravado["model"]["create_under_root"] is False
    assert gravado["profiles"]["default"]["folders"]["inbox"] == str(service.config.inbox)


@pytest.mark.asyncio
async def test_health_e_config_desconfigurados(client, monkeypatch):
    import trackclassifier.serve as serve_mod

    monkeypatch.setattr(serve_mod, "_service", None)
    monkeypatch.setattr(serve_mod, "_config", None)

    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["configured"] is False

    r = await client.get(f"/api/config?token={_token}")
    assert r.status_code == 200
    data = r.json()
    assert data["active_profile"] == "default"
    assert data["profiles"] == ["default"]
    # data_dir vem sugerido; as pastas de musica continuam vazias para o
    # usuario escolher.
    assert data["raw"]["paths"]["data_dir"].endswith("/data")
    assert "folders" not in data["raw"]

    # Os endpoints de estado continuam em 503: so config/health respondem.
    r = await client.get(f"/api/review/state?token={_token}")
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_apply_config_cria_config_no_primeiro_uso(client, tmp_path, monkeypatch):
    import trackclassifier.serve as serve_mod

    monkeypatch.setattr(serve_mod, "_service", None)
    monkeypatch.setattr(serve_mod, "_config", None)
    caminho = tmp_path / "config.toml"
    monkeypatch.setattr(serve_mod, "_config_path", caminho)

    raw = {
        "folders": _pastas_de_perfil(tmp_path, "novo"),
        "paths": {"data_dir": str(tmp_path / "data")},
    }
    r = await client.post(f"/api/config/apply?token={_token}", json={"raw": raw})
    assert r.status_code == 200, r.text
    assert caminho.exists()
    # save_config sempre grava no formato multi-perfil, mesmo com um so
    # perfil (o formato plano e so legado de leitura).
    gravado = read_raw(caminho)
    assert gravado["profiles"]["default"]["folders"]["inbox"] == raw["folders"]["inbox"]

    r = await client.get("/api/health")
    assert r.json()["configured"] is True


@pytest.mark.asyncio
async def test_model_settings_persiste_e_troca_config_vivo(client, tmp_path, monkeypatch):
    import tomllib

    import trackclassifier.serve as serve_mod
    from trackclassifier.config import save_config

    caminho = tmp_path / "config.toml"
    save_config(caminho, serve_mod._service.config)
    monkeypatch.setattr(serve_mod, "_config_path", caminho)

    r = await client.post(
        f"/api/model/settings?token={_token}",
        json={"retrain_every": 7, "min_examples": 9},
    )
    assert r.status_code == 200, r.text

    with open(caminho, "rb") as fh:
        gravado = tomllib.load(fh)
    assert gravado["model"]["retrain_every"] == 7
    assert gravado["model"]["min_examples"] == 9

    # O config VIVO troca na mesma hora: o painel e o proximo retreino
    # automatico leem daqui, e nao do disco.
    assert serve_mod._service.config.retrain_every == 7
    assert serve_mod._service.config.min_examples == 9

    r = await client.get(f"/api/model/state?token={_token}")
    assert r.json()["retrain_every"] == 7
    assert r.json()["min_examples"] == 9


@pytest.mark.asyncio
async def test_model_settings_rejeita_valores_menores_que_um(client):
    import trackclassifier.serve as serve_mod

    r = await client.post(
        f"/api/model/settings?token={_token}",
        json={"retrain_every": 0, "min_examples": 9},
    )
    assert r.status_code == 422
    # Config vivo nao mexeu com o valor invalido.
    assert serve_mod._service.config.retrain_every != 0


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



# ---------------------------------------------------------------------------
# Atualizacao do app (/api/update/*)
# ---------------------------------------------------------------------------


def _servico_de_update(tmp_path, *, release, state=None, **seams):
    from trackclassifier.update_service import UpdateService

    padrao = {
        "fetch": lambda: release,
        "download": lambda r, destino, progresso=None: destino,
        "install": lambda zip_baixado, bundle, versao: None,
        "verify": lambda bundle: None,
    }
    padrao.update(seams)
    return UpdateService(
        bundle=tmp_path / "TrackClassifier.app",
        state=lambda: state,
        n_tracks=lambda: 0,
        current_version="0.1.0",
        **padrao,
    )


def _release_de_teste(versao="0.9.0"):
    from trackclassifier.updates import Release

    return Release(
        version=versao,
        url_zip="https://z/app.zip",
        url_sha256="https://z/s",
        notas="notas",
        recomputa=frozenset(),
    )


@pytest.mark.asyncio
async def test_update_check_exige_token(client):
    r = await client.get("/api/update/check?token=wrong")
    # 401 e nao 422: o 422 passaria tambem se a rota perdesse a autenticacao e
    # quebrasse por outro motivo.
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_update_install_exige_token(client):
    r = await client.post("/api/update/install?token=wrong")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_update_check_fora_de_bundle_nao_e_suportado(client, monkeypatch):
    import trackclassifier.serve as serve_mod

    # Em pytest nao ha .app: o servico real nasce sem bundle, como em dev.
    monkeypatch.setattr(serve_mod, "_updates", None)

    r = await client.get(f"/api/update/check?manual=true&token={_token}")

    assert r.status_code == 200
    assert r.json() == {"supported": False, "available": False}


@pytest.mark.asyncio
async def test_update_check_oferece_versao_nova(client, monkeypatch, tmp_path):
    import trackclassifier.serve as serve_mod

    monkeypatch.setattr(
        serve_mod, "_updates", _servico_de_update(tmp_path, release=_release_de_teste())
    )

    r = await client.get(f"/api/update/check?manual=true&token={_token}")

    corpo = r.json()
    assert corpo["available"] is True
    assert corpo["version"] == "0.9.0"
    assert "0.9.0" in corpo["text"]


@pytest.mark.asyncio
async def test_update_check_manual_com_rede_fora_devolve_502(client, monkeypatch, tmp_path):
    import trackclassifier.serve as serve_mod
    from trackclassifier.updates import UpdateError

    def _sem_rede():
        raise UpdateError("sem rede")

    monkeypatch.setattr(
        serve_mod,
        "_updates",
        _servico_de_update(tmp_path, release=None, fetch=_sem_rede),
    )

    r = await client.get(f"/api/update/check?manual=true&token={_token}")

    assert r.status_code == 502
    assert "sem rede" in r.json()["detail"]


@pytest.mark.asyncio
async def test_update_install_sem_pendente_devolve_400(client, monkeypatch, tmp_path):
    import trackclassifier.serve as serve_mod

    monkeypatch.setattr(
        serve_mod, "_updates", _servico_de_update(tmp_path, release=_release_de_teste())
    )

    r = await client.post(f"/api/update/install?token={_token}")

    assert r.status_code == 400


@pytest.mark.asyncio
async def test_update_install_com_versao_trocada_devolve_400(client, monkeypatch, tmp_path):
    import trackclassifier.serve as serve_mod

    monkeypatch.setattr(
        serve_mod, "_updates", _servico_de_update(tmp_path, release=_release_de_teste("0.9.1"))
    )
    await client.get(f"/api/update/check?manual=true&token={_token}")

    r = await client.post(
        f"/api/update/install?token={_token}", json={"version": "0.9.0"}
    )

    assert r.status_code == 400
    assert "mudou para 0.9.1" in r.json()["detail"]


@pytest.mark.asyncio
async def test_update_install_status_e_segunda_instalacao_409(client, monkeypatch, tmp_path):
    import threading

    import trackclassifier.serve as serve_mod

    segura = threading.Event()

    def _baixar_devagar(release, destino, progresso=None):
        segura.wait(2)
        return destino

    monkeypatch.setattr(
        serve_mod,
        "_updates",
        _servico_de_update(
            tmp_path, release=_release_de_teste(), download=_baixar_devagar
        ),
    )
    await client.get(f"/api/update/check?manual=true&token={_token}")

    try:
        primeiro = await client.post(
            f"/api/update/install?token={_token}", json={"version": "0.9.0"}
        )
        segundo = await client.post(f"/api/update/install?token={_token}")
        andamento = await client.get(f"/api/update/status?token={_token}")
    finally:
        segura.set()

    assert primeiro.status_code == 200
    assert segundo.status_code == 409
    assert andamento.json()["state"] == "downloading"


@pytest.mark.asyncio
async def test_update_status_depois_de_concluir_fica_done(client, monkeypatch, tmp_path):
    import asyncio

    import trackclassifier.serve as serve_mod

    monkeypatch.setattr(
        serve_mod, "_updates", _servico_de_update(tmp_path, release=_release_de_teste())
    )
    await client.get(f"/api/update/check?manual=true&token={_token}")
    await client.post(f"/api/update/install?token={_token}")

    for _ in range(200):
        status = (await client.get(f"/api/update/status?token={_token}")).json()
        if status["state"] == "done":
            break
        await asyncio.sleep(0.01)

    assert status["state"] == "done"
    # Concluida, a checagem nao reoferece a versao que o processo ainda nao roda.
    depois = await client.get(f"/api/update/check?manual=true&token={_token}")
    assert depois.json()["installed"] is True
    # E instalar de novo e 409 (estado do servidor), nao 400 (pedido invalido).
    de_novo = await client.post(f"/api/update/install?token={_token}")
    assert de_novo.status_code == 409
    assert "ja foi instalada" in de_novo.json()["detail"]


@pytest.mark.asyncio
async def test_update_dismiss_grava_a_versao_dispensada(client, monkeypatch, tmp_path):
    import trackclassifier.serve as serve_mod
    from trackclassifier.update_state import EstadoDeAtualizacao

    estado = EstadoDeAtualizacao(tmp_path / "updates.json")
    monkeypatch.setattr(
        serve_mod,
        "_updates",
        _servico_de_update(tmp_path, release=_release_de_teste(), state=estado),
    )
    await client.get(f"/api/update/check?manual=true&token={_token}")

    r = await client.post(f"/api/update/dismiss?token={_token}")

    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # Nao basta responder 200: o que importa e a versao ter ficado gravada.
    assert estado.esta_dispensada("0.9.0")


def test_n_tracks_sem_servico_e_zero_e_nao_503(monkeypatch):
    """Primeiro uso: a checagem de update nao pode vazar o 503 de _get_service."""
    import trackclassifier.serve as serve_mod

    monkeypatch.setattr(serve_mod, "_service", None)

    assert serve_mod._n_tracks() == 0
