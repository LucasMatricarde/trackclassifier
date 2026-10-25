"""Testes do servidor FastAPI (serve.py).

Usa httpx.AsyncClient com ASGI transport para testar sem subir uvicorn.
O ExtratorFalso dos outros testes é reutilizado via conftest.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from httpx import ASGITransport, AsyncClient

from trackclassifier.config import Config, read_raw
from trackclassifier.labels import Label
from trackclassifier.profiles import ativar
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
    # Cache de stats e global do modulo: sem zerar, um teste herdaria o
    # resultado do anterior dentro do TTL.
    serve_mod._stats_cache = None

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
    # Nome de exibicao (a pill da Revisao mostra e troca por nome); o id
    # continua "default" em /api/profiles e /api/config.
    assert data["active_profile"] == "Padrão"
    assert data["profiles"] == ["Padrão"]


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
async def test_config_stats_segue_perfil_ativo_do_servico(client, service, tmp_path):
    """Trocar de perfil so atualiza service.config (o endpoint de switch nao
    reatribui _config): o stats precisa ler o perfil do servico, senao as
    contagens da sidebar continuam as do perfil anterior."""
    from trackclassifier.config import Profile

    outro_up = tmp_path / "outro_up"
    outro_up.mkdir()
    (outro_up / "x1.mp3").write_bytes(b"x1")
    (outro_up / "x2.mp3").write_bytes(b"x2")
    (tmp_path / "up" / "u.mp3").write_bytes(b"u")
    perfis = dict(service.config.profiles)
    perfis["outro"] = Profile(
        inbox=tmp_path / "outro_inbox",
        folders={
            Label.UP: outro_up,
            Label.NEUTRAL: tmp_path / "outro_neutral",
            Label.DOWN: tmp_path / "outro_down",
        },
    )
    service.config = replace(service.config, profiles=perfis)

    r = await client.get(f"/api/config/stats?token={_token}")
    assert r.json()["destinations"]["up"] == 1

    service.set_config(ativar(service.config, "outro"))

    r = await client.get(f"/api/config/stats?token={_token}")
    assert r.json()["destinations"]["up"] == 2


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
    import trackclassifier.serve as serve_mod

    serve_mod._config = service.config.with_active_settings(
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
    # E no proprio perfil (a fonte de verdade agora).
    assert gravado["profiles"]["default"]["model"] == {"retrain_every": 10, "min_examples": 15}
    assert gravado["profiles"]["default"]["organization"] == {
        "create": False,
        "move": False,
        "copy": False,
    }
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


# ---------------------------------------------------------------------------
# Perfis: CRUD, troca e persistencia
# ---------------------------------------------------------------------------


def _url(caminho: str) -> str:
    return f"{caminho}?token={_token}"


async def _cria(client, nome, copiar=True):
    return await client.post(_url("/api/profiles"), json={"name": nome, "copyFolders": copiar})


def _toml(service):
    return read_raw(service.config.data_dir.parent / "config.toml")


@pytest.mark.asyncio
async def test_get_profiles_devolve_o_formato_completo(client, service):
    r = await client.get(_url("/api/profiles"))

    assert r.status_code == 200
    dados = r.json()
    assert dados["active"] == "default" and dados["all"] == ["default"]
    perfil = dados["profiles"][0]
    assert perfil["id"] == "default" and perfil["name"] == "Padrão"
    assert perfil["inputDir"] == str(service.config.inbox)
    assert perfil["model"] == {"retrainEvery": 10, "minPerClass": 5}
    assert perfil["orgToggles"] == {"create": False, "move": False, "copy": False}
    assert perfil["complete"] is True


@pytest.mark.asyncio
async def test_criar_perfil_copia_pastas_ativa_e_persiste(client, service):
    import trackclassifier.serve as serve_mod

    r = await _cria(client, "Set Trance")

    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados["active"] == "set-trance"
    assert [p["name"] for p in dados["profiles"]] == ["Padrão", "Set Trance"]
    assert dados["profiles"][1]["inputDir"] == str(service.config.profiles["default"].inbox)
    # Estado vivo, global e disco andam juntos.
    assert service.config.active_profile == "set-trance"
    assert serve_mod._config.active_profile == "set-trance"
    gravado = _toml(service)
    assert gravado["active_profile"] == "set-trance"
    assert gravado["profiles"]["set-trance"]["name"] == "Set Trance"


@pytest.mark.asyncio
async def test_criar_perfil_sem_copiar_pastas_fica_incompleto(client, service):
    r = await _cria(client, "Vazio", copiar=False)

    assert r.status_code == 200, r.text
    vazio = r.json()["profiles"][1]
    assert vazio["complete"] is False
    assert vazio["inputDir"] == "" and vazio["destDirs"] == {"-1": "", "neutra": "", "+1": ""}
    assert _toml(service)["profiles"]["vazio"]["folders"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("nome", ["", "   ", "padrão", "PADRÃO"])
async def test_criar_perfil_nome_invalido_e_400_e_nao_grava(client, service, nome):
    r = await _cria(client, nome)

    assert r.status_code == 400
    assert "detail" in r.json()
    assert list(service.config.profiles) == ["default"]
    assert not (service.config.data_dir.parent / "config.toml").exists()


@pytest.mark.asyncio
async def test_renomear_perfil_mantem_o_id_e_persiste(client, service):
    await _cria(client, "Festa")

    r = await client.patch(_url("/api/profiles/festa"), json={"name": "Festa 2024"})

    assert r.status_code == 200, r.text
    assert [p["id"] for p in r.json()["profiles"]] == ["default", "festa"]
    assert r.json()["profiles"][1]["name"] == "Festa 2024"
    assert _toml(service)["profiles"]["festa"]["name"] == "Festa 2024"


@pytest.mark.asyncio
async def test_renomear_para_nome_repetido_400_e_desconhecido_404(client):
    await _cria(client, "Festa")

    repetido = await client.patch(_url("/api/profiles/festa"), json={"name": "Padrão"})
    desconhecido = await client.patch(_url("/api/profiles/nada"), json={"name": "X"})

    assert repetido.status_code == 400
    assert desconhecido.status_code == 404


@pytest.mark.asyncio
async def test_duplicar_perfil_nao_ativa_a_copia(client, service):
    r = await client.post(_url("/api/profiles/default/duplicate"))

    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados["active"] == "default"
    assert [p["name"] for p in dados["profiles"]] == ["Padrão", "Padrão (cópia)"]
    assert service.config.active_profile == "default"


@pytest.mark.asyncio
async def test_excluir_padrao_e_400(client):
    await _cria(client, "Festa")

    r = await client.delete(_url("/api/profiles/default"))

    assert r.status_code == 400
    assert "Padrão" in r.json()["detail"]


@pytest.mark.asyncio
async def test_excluir_o_ativo_troca_para_o_proximo_e_persiste(client, service):
    await _cria(client, "Alfa")
    await _cria(client, "Beta")  # ativo
    assert service.config.active_profile == "beta"

    r = await client.delete(_url("/api/profiles/beta"))

    assert r.status_code == 200, r.text
    assert r.json()["active"] == "alfa"  # era o ultimo: vai para o anterior
    assert service.config.active_profile == "alfa"
    gravado = _toml(service)
    assert gravado["active_profile"] == "alfa" and "beta" not in gravado["profiles"]


@pytest.mark.asyncio
async def test_excluir_perfil_desconhecido_e_404(client):
    r = await client.delete(_url("/api/profiles/nada"))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_trocar_por_id_persiste_no_toml_e_atualiza_o_config(client, service):
    """Regressao: a troca so mexia em service.config. O GET /api/config (de
    onde a Configuracao monta o rascunho) e o TOML ficavam no perfil antigo,
    e o auto-save gravava no perfil errado."""
    import trackclassifier.serve as serve_mod

    await _cria(client, "Alfa")  # o TOML e o estado vivo ficam em "alfa"
    assert _toml(service)["active_profile"] == "alfa"

    # Trocar para um perfil DIFERENTE do gravado: so passa se a troca persiste.
    r = await client.post(_url("/api/profiles/switch"), json={"id": "default"})

    assert r.status_code == 200, r.text
    assert r.json()["active"] == "default"
    assert serve_mod._config.active_profile == "default"
    assert _toml(service)["active_profile"] == "default"
    cfg = (await client.get(_url("/api/config"))).json()
    assert cfg["active_profile"] == "default"
    assert cfg["raw"]["active_profile"] == "default"
    assert (await client.get(_url("/api/profiles"))).json()["active"] == "default"

    # E de volta.
    await client.post(_url("/api/profiles/switch"), json={"id": "alfa"})
    assert _toml(service)["active_profile"] == "alfa"


@pytest.mark.asyncio
async def test_trocar_por_nome_para_a_pill_da_revisao(client, service):
    await _cria(client, "Set Trance")
    await client.post(_url("/api/profiles/switch"), json={"id": "default"})

    r = await client.post(_url("/api/profiles/switch"), json={"name": "Set Trance"})

    assert r.status_code == 200, r.text
    assert service.config.active_profile == "set-trance"
    estado = (await client.get(_url("/api/review/state"))).json()
    # A pill mostra e troca por nome, o mesmo estado global.
    assert estado["profiles"] == ["Padrão", "Set Trance"]
    assert estado["active_profile"] == "Set Trance"


@pytest.mark.asyncio
async def test_trocar_sem_perfil_e_400(client):
    r = await client.post(_url("/api/profiles/switch"), json={})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_operacoes_de_perfil_dao_409_durante_o_scan(client, service, monkeypatch):
    import trackclassifier.serve as serve_mod

    await _cria(client, "Alfa")
    antes = list(service.config.profiles)
    monkeypatch.setattr(serve_mod, "_scan_running", True)

    respostas = [
        await _cria(client, "Beta"),
        await client.patch(_url("/api/profiles/alfa"), json={"name": "Z"}),
        await client.post(_url("/api/profiles/alfa/duplicate")),
        await client.delete(_url("/api/profiles/alfa")),
    ]

    assert [r.status_code for r in respostas] == [409, 409, 409, 409]
    assert list(service.config.profiles) == antes
    # Trocar so muda qual fila aparece: segue permitido.
    r = await client.post(_url("/api/profiles/switch"), json={"id": "default"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_apply_grava_modelo_e_organizacao_por_perfil(client, tmp_path):
    raw = {
        "active_profile": "b",
        "profiles": {
            "a": {
                "folders": _pastas_de_perfil(tmp_path, "a"),
                "model": {"retrain_every": 11, "min_examples": 12},
                "organization": {"create": True, "move": False, "copy": False},
            },
            "b": {
                "name": "Bê",
                "folders": _pastas_de_perfil(tmp_path, "b"),
                "model": {"retrain_every": 21, "min_examples": 22},
                "organization": {"create": False, "move": True, "copy": True},
            },
        },
        "paths": {"data_dir": str(tmp_path / "data")},
    }

    r = await client.post(_url("/api/config/apply"), json={"raw": raw})
    assert r.status_code == 200, r.text

    gravado = read_raw(tmp_path / "config.toml")
    a, b = gravado["profiles"]["a"], gravado["profiles"]["b"]
    assert a["model"] == {"retrain_every": 11, "min_examples": 12}
    assert b["model"] == {"retrain_every": 21, "min_examples": 22}
    assert a["organization"] == {"create": True, "move": False, "copy": False}
    assert b["organization"] == {"create": False, "move": True, "copy": True}
    assert b["name"] == "Bê"
    # O servico vivo le o perfil ativo (b).
    import trackclassifier.serve as serve_mod

    assert serve_mod._service.config.retrain_every == 21
    assert serve_mod._service.config.keep_copy is True


@pytest.mark.asyncio
async def test_model_settings_grava_so_no_perfil_ativo(client, service, monkeypatch):
    import trackclassifier.serve as serve_mod
    from trackclassifier.config import save_config

    await _cria(client, "Alfa")  # ativo
    caminho = service.config.data_dir.parent / "config.toml"
    monkeypatch.setattr(serve_mod, "_config_path", caminho)

    r = await client.post(
        _url("/api/model/settings"), json={"retrain_every": 7, "min_examples": 9}
    )

    assert r.status_code == 200, r.text
    gravado = read_raw(caminho)
    assert gravado["profiles"]["alfa"]["model"] == {"retrain_every": 7, "min_examples": 9}
    assert gravado["profiles"]["default"]["model"] == {"retrain_every": 10, "min_examples": 5}
    assert serve_mod._service.config.retrain_every == 7
    save_config(caminho, serve_mod._service.config)  # round-trip sem erro


@pytest.mark.asyncio
async def test_reset_so_restaura_o_perfil_ativo(client, service):
    await _cria(client, "Alfa")
    await client.post(
        _url("/api/model/settings"), json={"retrain_every": 30, "min_examples": 40}
    )
    await client.post(_url("/api/profiles/switch"), json={"id": "default"})
    await client.post(
        _url("/api/model/settings"), json={"retrain_every": 31, "min_examples": 41}
    )

    r = await client.post(_url("/api/config/reset"), json={})

    assert r.status_code == 200, r.text
    gravado = _toml(service)
    assert gravado["profiles"]["default"]["model"] == {"retrain_every": 10, "min_examples": 15}
    assert gravado["profiles"]["alfa"]["model"] == {"retrain_every": 30, "min_examples": 40}


@pytest.mark.asyncio
async def test_stats_de_perfil_incompleto_e_zero_e_de_perfil_copiado_conta_as_pastas(
    client, service, tmp_path
):
    (tmp_path / "up" / "u.mp3").write_bytes(b"u")
    await _cria(client, "Copia")  # compartilha as pastas do Padrao

    copia = (await client.get(_url("/api/config/stats"))).json()
    assert copia["destinations"]["up"] == 1  # o scan dedupe nao zera o perfil copiado

    await _cria(client, "Vazio", copiar=False)
    vazio = (await client.get(_url("/api/config/stats"))).json()
    assert vazio["destinations"] == {"up": 0, "neutral": 0, "down": 0}
    assert vazio["inbox_new"] == 0


async def _espera(condicao, limite=10.0):
    """Cede o loop ate a condicao valer (o scan roda em worker thread)."""
    import asyncio

    fim = asyncio.get_running_loop().time() + limite
    while not condicao():
        assert asyncio.get_running_loop().time() < fim, "condicao nao atingida a tempo"
        await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_scan_expoe_a_fase_processando_ate_a_apresentacao_terminar(
    client, service, monkeypatch
):
    """O buraco do header: a passada de tags/capa/tonalidade nao emite
    scan_progress, mas _scan_running (e o 409 de perfil) dura ate o fim dela."""
    import asyncio
    import threading

    import trackclassifier.serve as serve_mod
    from tests.test_service import _povoa

    _povoa(service.config, n_por_classe=1)
    mensagens = []

    async def _grava(mensagem):
        mensagens.append(mensagem)

    monkeypatch.setattr(serve_mod, "_broadcast", _grava)

    chegou = threading.Event()
    liberado = threading.Event()

    def _bloqueia(aceitos, should_cancel=None):
        chegou.set()
        assert liberado.wait(timeout=10)
        return False

    monkeypatch.setattr(service, "_preenche_apresentacao", _bloqueia)

    assert (await client.get(_url("/api/scan/status"))).json() == {
        "phase": "idle",
        "running": False,
    }

    tarefa = asyncio.create_task(client.post(_url("/api/scan"), json={}))
    try:
        await _espera(chegou.is_set)
        # A analise ja voltou; so a apresentacao segura o scan.
        await _espera(lambda: {"type": "scan_phase", "phase": "processando"} in mensagens)

        status = (await client.get(_url("/api/scan/status"))).json()
        assert status == {"phase": "processando", "running": True}
        fases = [m["phase"] for m in mensagens if m["type"] == "scan_phase"]
        assert fases == ["analisando", "processando"]
        assert not any(m["type"] == "scan_finished" for m in mensagens)
        # Mesmo instante do header: criar perfil ainda e 409.
        assert (await _cria(client, "Beta")).status_code == 409
    finally:
        liberado.set()
    resposta = await tarefa

    assert resposta.status_code == 200
    assert (await client.get(_url("/api/scan/status"))).json() == {
        "phase": "idle",
        "running": False,
    }
    tipos = [(m["type"], m.get("phase")) for m in mensagens]
    assert tipos[-3:] == [
        ("scan_phase", "idle"),
        ("states_changed", None),
        ("scan_finished", None),
    ]
    assert (await _cria(client, "Beta")).status_code == 200


@pytest.mark.asyncio
async def test_scan_inicial_emite_scan_finished(client, service, monkeypatch):
    import trackclassifier.serve as serve_mod

    mensagens = []

    async def _grava(mensagem):
        mensagens.append(mensagem)

    monkeypatch.setattr(serve_mod, "_broadcast", _grava)

    await serve_mod._scan_inicial()

    # Sem scan_finished quem abriu a pagina durante o scan de abertura ficaria
    # preso no estado de "escaneando" ate o proximo scan manual.
    assert mensagens[-1] == {"type": "scan_finished", "cancelled": False}
    assert [m["type"] for m in mensagens].count("states_changed") == 1


def test_ws_envia_a_fase_atual_no_connect(service, monkeypatch):
    from starlette.testclient import TestClient

    import trackclassifier.serve as serve_mod

    serve_mod._service = service
    serve_mod._config = service.config
    monkeypatch.setattr(serve_mod, "_scan_phase", "processando")

    # Sem `with TestClient`: o lifespan dispararia o scan de abertura e as
    # mensagens dele se misturariam com as do connect.
    cliente = TestClient(app)
    with cliente.websocket_connect(f"/ws?token={_token}") as ws:
        recebidas = [ws.receive_json(), ws.receive_json()]

    assert [m["type"] for m in recebidas] == ["states_changed", "scan_phase"]
    assert recebidas[1]["phase"] == "processando"


@pytest.fixture()
def contador_de_scan(monkeypatch):
    """Conta as varreduras reais de scan_labeled feitas pelo endpoint de stats."""
    import trackclassifier.library as library_mod

    chamadas = {"n": 0}
    original = library_mod.scan_labeled

    def contando(*args, **kwargs):
        chamadas["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(library_mod, "scan_labeled", contando)
    return chamadas


@pytest.fixture()
def relogio(monkeypatch):
    """Relogio falso so para o serve.py: trocar time.monotonic global
    quebraria o proprio event loop."""
    from types import SimpleNamespace

    import trackclassifier.serve as serve_mod

    agora = {"t": 1000.0}
    monkeypatch.setattr(serve_mod, "time", SimpleNamespace(monotonic=lambda: agora["t"]))
    return agora


@pytest.mark.asyncio
async def test_config_stats_segunda_chamada_dentro_do_ttl_nao_reescaneia(
    client, tmp_path, contador_de_scan, relogio
):
    (tmp_path / "up" / "u.mp3").write_bytes(b"u")

    primeira = await client.get(f"/api/config/stats?token={_token}")
    relogio["t"] += 1.0
    (tmp_path / "up" / "novo.mp3").write_bytes(b"novo")
    segunda = await client.get(f"/api/config/stats?token={_token}")

    assert contador_de_scan["n"] == 1
    assert segunda.json() == primeira.json()
    assert segunda.json()["destinations"]["up"] == 1


@pytest.mark.asyncio
async def test_config_stats_broadcast_de_estados_invalida_o_cache(
    client, tmp_path, contador_de_scan, relogio
):
    import trackclassifier.serve as serve_mod

    (tmp_path / "up" / "u.mp3").write_bytes(b"u")
    await client.get(f"/api/config/stats?token={_token}")
    (tmp_path / "up" / "novo.mp3").write_bytes(b"novo")

    await serve_mod._broadcast_states()
    r = await client.get(f"/api/config/stats?token={_token}")

    assert contador_de_scan["n"] == 2
    assert r.json()["destinations"]["up"] == 2


@pytest.mark.asyncio
async def test_config_stats_ttl_expirado_recalcula(client, tmp_path, contador_de_scan, relogio):
    import trackclassifier.serve as serve_mod

    (tmp_path / "up" / "u.mp3").write_bytes(b"u")
    await client.get(f"/api/config/stats?token={_token}")
    (tmp_path / "up" / "novo.mp3").write_bytes(b"novo")

    relogio["t"] += serve_mod._STATS_TTL_S + 0.1
    r = await client.get(f"/api/config/stats?token={_token}")

    assert contador_de_scan["n"] == 2
    assert r.json()["destinations"]["up"] == 2


@pytest.mark.asyncio
async def test_config_stats_nao_serve_cache_de_outro_servico(
    client, service, tmp_path, contador_de_scan, relogio
):
    """Apply/reset recriam o servico: o resultado do anterior, ainda dentro
    do TTL, nao pode vazar para o novo."""
    import trackclassifier.serve as serve_mod

    (tmp_path / "up" / "u.mp3").write_bytes(b"u")
    await client.get(f"/api/config/stats?token={_token}")

    novo = TrackService(service.config, extractor=service.extractor, max_workers=1)
    serve_mod._service = novo
    await client.get(f"/api/config/stats?token={_token}")

    assert contador_de_scan["n"] == 2


@pytest.mark.asyncio
async def test_config_stats_erro_de_scan_nao_entra_no_cache(
    client, monkeypatch, relogio
):
    """Pasta ilegivel degrada para zero, mas o zero nao pode ficar 5 s no cache."""
    import trackclassifier.library as library_mod
    import trackclassifier.serve as serve_mod

    def falha(*args, **kwargs):
        raise OSError("volume desmontado")

    monkeypatch.setattr(library_mod, "scan_labeled", falha)
    r = await client.get(f"/api/config/stats?token={_token}")

    assert r.status_code == 200
    assert r.json()["destinations"] == {"up": 0, "neutral": 0, "down": 0}
    assert serve_mod._stats_cache is None


def _grava_capa(service, sha1, sufixo, dados):
    """Registra uma capa no data_dir temporario do service, como o scan faria."""
    from trackclassifier.presentation import VAZIO, Cover

    service.presentation.put(sha1, VAZIO, Cover(data=dados, suffix=sufixo))
    return service.cover_path_for(sha1)


@pytest.mark.asyncio
async def test_thumb_sem_miniatura_devolve_content_type_da_capa(client, service):
    """Sem `<sha1>.thumb.png` o fallback serve a capa original, que e jpeg.

    Rotular esse jpeg como image/png era mentira: o navegador farejava o
    conteudo e funcionava, mas qualquer cliente estrito falharia.
    """
    capa = _grava_capa(service, "a" * 40, ".jpg", b"\xff\xd8\xff\xe0capa")
    assert capa is not None

    r = await client.get(f"/api/thumb/{'a' * 40}?token={_token}")

    assert r.status_code == 200
    assert r.content == b"\xff\xd8\xff\xe0capa"
    assert r.headers["content-type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_thumb_com_miniatura_devolve_image_png(client, service):
    """Com `<sha1>.thumb.png` ao lado da capa, o arquivo servido e o png."""
    from trackclassifier.presentation import THUMB_SUFFIX

    capa = _grava_capa(service, "b" * 40, ".jpg", b"\xff\xd8\xff\xe0capa")
    assert capa is not None
    miniatura = capa.parent / f"{capa.stem}{THUMB_SUFFIX}"
    miniatura.write_bytes(b"\x89PNG\r\n\x1a\nmini")

    r = await client.get(f"/api/thumb/{'b' * 40}?token={_token}")

    assert r.status_code == 200
    assert r.content == b"\x89PNG\r\n\x1a\nmini"
    assert r.headers["content-type"] == "image/png"
