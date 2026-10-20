"""Servidor FastAPI + WebSocket para o front React.

Roda na MESMA thread do TrackService (reusa a lógica já existente).
Não cria novo pool nem novo serviço — apenas expõe o que o ServiceWorker já emite.
"""

from __future__ import annotations

import asyncio
import mimetypes
import secrets
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .config import Config, ConfigError, load_config, read_raw
from .labels import Label
from .service import TrackService
from .ui.viewmodel import library_state, model_state, review_state

#: O frontend decide por indice do teclado (1/2/3 -> -1/0/+1); o dominio usa
#: Label (StrEnum com "+1"/"neutra"/"-1"). A traducao fica na borda.
_LABEL_BY_INT: dict[int, Label] = {-1: Label.DOWN, 0: Label.NEUTRAL, 1: Label.UP}

# ---------------------------------------------------------------------------
# Estado global do servidor
# ---------------------------------------------------------------------------

_service: TrackService | None = None
_config: Config | None = None
_cancel_scan = threading.Event()
_scan_running = False  # guarda contra dois analyze_all concorrentes
_peaks_semaphore = asyncio.Semaphore(3)  # teto de 3 computações em voo
_ws_clients: set[WebSocket] = set()
_token = secrets.token_urlsafe(32)


def _get_service() -> TrackService:
    if _service is None:
        raise HTTPException(status_code=503, detail="Serviço não inicializado")
    return _service


def _get_config() -> Config:
    if _config is None:
        raise HTTPException(status_code=503, detail="Config não carregada")
    return _config


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------


def _verify_token(
    token: str = Query(default=""),
    x_auth_token: str | None = Header(default=None),
) -> None:
    # Aceita header (REST via fetch) ou query (?token=) -- <audio>/<img> e o
    # WebSocket do browser nao conseguem setar header, entao midia e WS
    # autenticam pela query string.
    if token != _token and x_auth_token != _token:
        raise HTTPException(status_code=401, detail="Token inválido")


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------


class DecideBody(BaseModel):
    sha1: str
    label: int  # -1, 0, 1 (indice do teclado 1/2/3)


class ConfigDraftBody(BaseModel):
    raw: dict


class SwitchProfileBody(BaseModel):
    name: str


class ScanBody(BaseModel):
    pass


# ---------------------------------------------------------------------------
# Serialização (dataclass → dict)
# ---------------------------------------------------------------------------


def _track_row_to_dict(row) -> dict:
    return {
        "sha1": row.sha1,
        "filename": row.filename,
        "label": row.label,
        "predicted": row.predicted,
        "score": row.score,
        "confidence": row.confidence,
        "bpm": row.bpm,
        "duration_s": row.duration_s,
        "energy_curve": list(row.energy_curve),
        "peak_offset_s": row.peak_offset_s,
        "path_hint": row.path_hint,
        "title": row.title,
        "artist": row.artist,
        "genre": row.genre,
        "album": row.album,
        "cover_path": row.cover_path,
        "peaks_path": row.peaks_path,
        "key": (
            {
                "pitch_class": row.key.pitch_class,
                "mode": row.key.mode.value,
                "camelot": row.key.camelot,
                "classic": row.key.classic,
                "camelot_number": row.key.camelot_number,
            }
            if row.key is not None
            else None
        ),
        "display_title": row.display_title,
    }


def _review_state_to_dict(state) -> dict:
    return {
        "current": _track_row_to_dict(state.current) if state.current else None,
        "upcoming": [_track_row_to_dict(r) for r in state.upcoming],
        "low_confidence": state.low_confidence,
        "remaining": state.remaining,
        "profiles": list(state.profiles),
        "active_profile": state.active_profile,
    }


def _library_state_to_dict(state) -> dict:
    return {
        "rows": [_track_row_to_dict(r) for r in state.rows],
        "class_counts": list(state.class_counts),
        "total": state.total,
        "genres": list(state.genres),
        "keys": list(state.keys),
    }


def _model_state_to_dict(state) -> dict:
    return {
        "accuracy": state.accuracy,
        "ordinal_mae": state.ordinal_mae,
        "confusion": [list(row) for row in state.confusion] if state.confusion else None,
        "n_examples": state.n_examples,
        "failures": [list(f) for f in state.failures],
        "class_counts": list(state.class_counts),
        "decisions_since_train": state.decisions_since_train,
        "retrain_every": state.retrain_every,
        "train_blocked_reason": state.train_blocked_reason,
        "low_confidence": state.low_confidence,
        "alpha": state.alpha,
        "thresholds": list(state.thresholds) if state.thresholds else None,
        "extractor_name": state.extractor_name,
    }


# ---------------------------------------------------------------------------
# WebSocket helpers
# ---------------------------------------------------------------------------


async def _broadcast(message: dict) -> None:
    """Envia mensagem para todos os clientes WS conectados."""
    disconnected = set()
    for ws in _ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.add(ws)
    _ws_clients.difference_update(disconnected)


async def _broadcast_states() -> None:
    """Envia o estado completo (review, library, model) para todos."""
    service = _get_service()
    review = review_state(service)
    library = library_state(service)
    model = model_state(service)
    await _broadcast(
        {
            "type": "states_changed",
            "review": _review_state_to_dict(review),
            "library": _library_state_to_dict(library),
            "model": _model_state_to_dict(model),
        }
    )


class _ScanJaRodando(Exception):
    """Scan concorrente tentou rodar -- analyze_all muta listas do servico."""


async def _executa_scan() -> bool:
    """Roda analyze_all numa worker thread e devolve se foi cancelado.

    analyze_all e sincrono e dura minutos numa biblioteca virgem; rodar
    direto no handler bloquearia o event loop (WS sem heartbeat, nenhuma
    resposta a cancel/undo). a flag _scan_running impede dois analyze_all
    concorrentes, que corromperiam _inbox/_labeled.
    """
    global _scan_running
    if _scan_running:
        raise _ScanJaRodando()
    _scan_running = True
    _cancel_scan.clear()
    service = _get_service()
    loop = asyncio.get_running_loop()

    def _progresso(concluidas: int, total: int, nome: str) -> None:
        # Chamado de worker thread: o broadcast tem que ser agendado no loop
        # principal (create_task aqui levantaria "no running event loop").
        asyncio.run_coroutine_threadsafe(
            _broadcast(
                {
                    "type": "scan_progress",
                    "done": concluidas,
                    "total": total,
                    "current": nome,
                }
            ),
            loop,
        )

    try:
        return await asyncio.to_thread(
            service.analyze_all,
            on_progress=_progresso,
            should_cancel=_cancel_scan.is_set,
        )
    finally:
        _scan_running = False


async def _scan_inicial() -> None:
    """Scan de abertura: reconstroi a fila a partir do cache.

    Paridade com a janela Qt, que escaneia ao abrir -- sem isso a UI abre
    vazia depois de um restart mesmo com a inbox cheia, porque _inbox so e
    montada por analyze_all. Com tudo ja extraido e so reler o parquet;
    biblioteca virgem extrai de verdade, igual ao primeiro `dj scan`.
    """
    try:
        await _executa_scan()
        await _broadcast_states()
    except _ScanJaRodando:
        pass
    except Exception as e:
        await _broadcast({"type": "error", "message": str(e)})


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # A fila so existe depois de um analyze_all; sem o scan de abertura a UI
    # abriria vazia a cada restart do servidor.
    tarefa = asyncio.create_task(_scan_inicial()) if _service is not None else None
    try:
        yield
    finally:
        if tarefa is not None:
            tarefa.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "tauri://localhost", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints — estado
# ---------------------------------------------------------------------------


@app.get("/api/review/state")
def get_review_state(token: str = Depends(_verify_token)):
    service = _get_service()
    state = review_state(service)
    return _review_state_to_dict(state)


@app.get("/api/library/state")
def get_library_state(token: str = Depends(_verify_token)):
    service = _get_service()
    state = library_state(service)
    return _library_state_to_dict(state)


@app.get("/api/model/state")
def get_model_state(token: str = Depends(_verify_token)):
    service = _get_service()
    state = model_state(service)
    return _model_state_to_dict(state)


# ---------------------------------------------------------------------------
# Endpoints — ações da revisão
# ---------------------------------------------------------------------------


@app.post("/api/review/decide")
async def decide(body: DecideBody, token: str = Depends(_verify_token)):
    service = _get_service()
    try:
        rotulo = _LABEL_BY_INT[body.label]
    except KeyError:
        raise HTTPException(
            status_code=400, detail="label deve ser -1, 0 ou 1"
        ) from None

    try:
        service.path_for(body.sha1)
        na_inbox = True
    except KeyError:
        na_inbox = False

    try:
        if na_inbox:
            retreinou = service.decide(body.sha1, rotulo)
        else:
            retreinou = service.reclassify(body.sha1, rotulo)
    except KeyError:
        raise HTTPException(
            status_code=404, detail="Track não está na fila nem na biblioteca"
        ) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    await _broadcast_states()
    if retreinou:
        await _broadcast({"type": "retrained"})

    # Devolve o estado atualizado
    state = review_state(service)
    return {
        "ok": True,
        "next": _track_row_to_dict(state.current) if state.current else None,
        "remaining": state.remaining,
    }


@app.post("/api/review/undo")
async def undo(token: str = Depends(_verify_token)):
    service = _get_service()
    if not service.undo_last():
        raise HTTPException(status_code=400, detail="Nada para desfazer") from None
    await _broadcast_states()
    state = review_state(service)
    return {
        "ok": True,
        "restored": _track_row_to_dict(state.current) if state.current else None,
    }


@app.post("/api/review/remove")
async def remove(body: DecideBody, token: str = Depends(_verify_token)):
    service = _get_service()
    try:
        service.remove(body.sha1)
    except KeyError:
        raise HTTPException(status_code=404, detail="Track não está mais na fila") from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    await _broadcast_states()
    return {"ok": True}


@app.post("/api/review/bulk")
async def bulk_approve(token: str = Depends(_verify_token)):
    service = _get_service()
    try:
        count = service.bulk_approve(min_confidence=0.75)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    await _broadcast_states()
    return {"ok": True, "count": count}


# ---------------------------------------------------------------------------
# Endpoints — scan
# ---------------------------------------------------------------------------


@app.post("/api/scan")
async def scan(body: ScanBody | None = None, token: str = Depends(_verify_token)):
    try:
        cancelado = await _executa_scan()
    except _ScanJaRodando:
        raise HTTPException(
            status_code=409, detail="Scan já em andamento"
        ) from None
    except Exception as e:
        await _broadcast({"type": "error", "message": str(e)})
        raise HTTPException(status_code=500, detail=str(e)) from e

    await _broadcast_states()
    await _broadcast({"type": "scan_finished", "cancelled": cancelado})
    return {"ok": True, "cancelled": cancelado}


@app.post("/api/scan/cancel")
async def cancel_scan(token: str = Depends(_verify_token)):
    _cancel_scan.set()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Endpoints — mídia
# ---------------------------------------------------------------------------


@app.get("/api/audio/{sha1}")
async def get_audio(
    sha1: str,
    request: Request,
    token: str = Depends(_verify_token),
):
    """Serve o arquivo de áudio com suporte a Range requests (necessário para seek)."""

    service = _get_service()
    try:
        path = service.path_for(sha1)
    except KeyError:
        # Talvez seja uma track da biblioteca (já rotulada)
        for ref in service._labeled:
            if ref.sha1 == sha1:
                path = ref.path
                break
        else:
            raise HTTPException(status_code=404, detail="Áudio não encontrado") from None

    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo de áudio não existe") from None

    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    mime, _ = mimetypes.guess_type(str(path))
    if mime is None:
        mime = "audio/mpeg"

    def _range_stream(start: int, end: int):
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    if range_header:
        try:
            range_str = range_header.replace("bytes=", "")
            parts = range_str.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
            end = min(end, file_size - 1)
            length = end - start + 1

            return StreamingResponse(
                _range_stream(start, end),
                status_code=206,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(length),
                    "Content-Type": mime,
                },
                media_type=mime,
            )
        except (ValueError, IndexError):
            pass  # Range inválido, cai para 200

    return StreamingResponse(
        _range_stream(0, file_size - 1),
        status_code=200,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Type": mime,
        },
        media_type=mime,
    )


@app.get("/api/cover/{sha1}")
def get_cover(sha1: str, token: str = Depends(_verify_token)):
    service = _get_service()
    path = service.cover_path_for(sha1)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Capa não encontrada") from None
    mime, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=mime or "image/jpeg")


@app.get("/api/thumb/{sha1}")
def get_thumb(sha1: str, token: str = Depends(_verify_token)):
    service = _get_service()
    # Thumb já está em covers/<sha1>.thumb.png (96px)
    path = service.cover_path_for(sha1)
    if path is None:
        raise HTTPException(status_code=404, detail="Thumb não encontrada") from None
    thumb_path = path.parent / f"{path.stem}.thumb.png"
    if not thumb_path.is_file():
        # Fallback: capa original
        thumb_path = path
    if not thumb_path.is_file():
        raise HTTPException(status_code=404, detail="Thumb não encontrada") from None
    return FileResponse(thumb_path, media_type="image/png")


@app.get("/api/peaks/{sha1}")
def get_peaks(sha1: str, token: str = Depends(_verify_token)):
    service = _get_service()
    path = service.peaks_for(sha1)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Peaks não computados") from None
    return FileResponse(path, media_type="application/octet-stream")


# ---------------------------------------------------------------------------
# Endpoints — peaks sob demanda (trigger compute)
# ---------------------------------------------------------------------------


@app.post("/api/peaks/{sha1}/compute")
async def compute_peaks(sha1: str, token: str = Depends(_verify_token)):
    """Dispara o computo de peaks para uma track, com teto de 3 em voo."""
    service = _get_service()
    try:
        path = service.path_for(sha1)
    except KeyError:
        raise HTTPException(status_code=404, detail="Track não encontrada") from None

    async def _compute():
        async with _peaks_semaphore:
            try:
                caminho = service.ensure_peaks(sha1, Path(path))
            except Exception:
                caminho = None
            if caminho is not None:
                await _broadcast({"type": "peaks_ready", "sha1": sha1, "path": str(caminho)})
            else:
                await _broadcast({"type": "peaks_failed", "sha1": sha1})

    asyncio.create_task(_compute())
    return {"ok": True, "queued": True}


# ---------------------------------------------------------------------------
# Endpoints — busca na biblioteca
# ---------------------------------------------------------------------------


@app.get("/api/library/search")
def search_library(
    q: str = Query(default=""),
    token: str = Depends(_verify_token),
):
    service = _get_service()
    state = library_state(service)
    if not q.strip():
        return {"rows": [_track_row_to_dict(r) for r in state.rows]}

    q_lower = q.strip().lower()
    filtradas = [
        r
        for r in state.rows
        if q_lower in r.display_title.lower()
        or (r.artist and q_lower in r.artist.lower())
        or (r.album and q_lower in r.album.lower())
        or q_lower in r.filename.lower()
    ]
    return {"rows": [_track_row_to_dict(r) for r in filtradas]}


# ---------------------------------------------------------------------------
# Endpoints — config e perfis
# ---------------------------------------------------------------------------


@app.get("/api/config")
def get_config(token: str = Depends(_verify_token)):
    config = _get_config()
    raw = read_raw(config.data_dir.parent / "config.toml") if config else {}
    return {
        "raw": raw,
        "active_profile": config.active_profile,
        "profiles": list(config.profiles.keys()),
    }


@app.post("/api/config/validate")
def validate_config(body: ConfigDraftBody, token: str = Depends(_verify_token)):
    from .config import SettingsDraft, validate_settings

    draft = SettingsDraft.from_raw(body.raw)
    erros = validate_settings(draft)
    return {"valid": len(erros) == 0, "errors": {e.field: e.message for e in erros}}


@app.post("/api/config/apply")
async def apply_config(body: ConfigDraftBody, token: str = Depends(_verify_token)):
    global _service, _config
    from .config import SettingsDraft, apply_draft

    draft = SettingsDraft.from_raw(body.raw)
    config_path = _config.data_dir.parent / "config.toml" if _config else Path("config.toml")
    try:
        config = apply_draft(draft, config_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Recria o serviço com a nova config (equivalente a reload_config do worker)
    try:
        _service = TrackService(config)
        _config = config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao recriar serviço: {e}") from e

    await _broadcast({"type": "config_reloaded"})
    await _broadcast_states()
    return {"ok": True}


@app.get("/api/profiles")
def get_profiles(token: str = Depends(_verify_token)):
    config = _get_config()
    return {
        "active": config.active_profile,
        "all": list(config.profiles.keys()),
    }


@app.post("/api/profiles/switch")
async def switch_profile(body: SwitchProfileBody, token: str = Depends(_verify_token)):
    service = _get_service()
    config = _get_config()
    if body.name not in config.profiles:
        raise HTTPException(status_code=400, detail=f"Perfil desconhecido: {body.name}") from None

    service.set_active_profile(body.name)
    await _broadcast({"type": "profile_changed", "name": body.name})
    await _broadcast_states()
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True, "token": _token}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    if token != _token:
        await websocket.close(code=4001, reason="Token inválido")
        return

    await websocket.accept()
    _ws_clients.add(websocket)

    try:
        # Envia estado inicial
        await _broadcast_states()
        while True:
            data = await websocket.receive_text()
            # Cliente pode enviar ping; respondemos com pong
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------


def run_server(
    config_path: str,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
) -> None:
    """Inicializa o TrackService e sobe o uvicorn."""
    global _service, _config

    try:
        _config = load_config(Path(config_path))
    except ConfigError as e:
        print(f"Erro de configuração: {e}")
        raise SystemExit(1) from e

    _service = TrackService(_config)

    print(f"Servidor rodando em http://{host}:{port}")
    print(f"Token: {_token}")
    print(f"WS: ws://{host}:{port}/ws?token={_token}")
    if open_browser:
        import webbrowser

        webbrowser.open(f"http://{host}:{port}")

    uvicorn.run(app, host=host, port=port, log_level="warning")
