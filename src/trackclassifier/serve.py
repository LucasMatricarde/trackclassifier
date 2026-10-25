"""Servidor FastAPI + WebSocket para o front React.

Roda na MESMA thread do TrackService (reusa a lógica já existente).
Não cria novo pool nem novo serviço — apenas expõe o que o TrackService já emite.
"""

from __future__ import annotations

import asyncio
import mimetypes
import secrets
import threading
from contextlib import asynccontextmanager
from dataclasses import replace
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
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.types import Scope

from .config import Config, ConfigError, load_config, read_raw, save_config
from .labels import Label
from .model import NotEnoughClassesError
from .profiles import (
    ProfileError,
    ativar,
    criar,
    duplicar,
    excluir,
    nome_de,
    para_json,
    renomear,
    resolver,
)
from .service import TrackService
from .update_service import AlreadyInstalled, InstallInProgress, UpdateService
from .update_state import EstadoDeAtualizacao
from .updates import UpdateError, caminho_do_bundle
from .viewmodel import library_state, model_state, review_state

#: O frontend decide por indice do teclado (1/2/3 -> -1/0/+1); o dominio usa
#: Label (StrEnum com "+1"/"neutra"/"-1"). A traducao fica na borda.
_LABEL_BY_INT: dict[int, Label] = {-1: Label.DOWN, 0: Label.NEUTRAL, 1: Label.UP}

# ---------------------------------------------------------------------------
# Estado global do servidor
# ---------------------------------------------------------------------------

_service: TrackService | None = None
_config: Config | None = None
#: Arquivo de onde _config foi carregado. Nao da para deduzir de data_dir:
#: em dev o config.toml fica no cwd e o data_dir no home, entao get_config
#: lia um arquivo e o servidor usava outro (raw e active_profile vinham de
#: fontes diferentes). Fica None nos testes, que injetam _config direto.
_config_path: Path | None = None
_cancel_scan = threading.Event()
_scan_running = False  # guarda contra dois analyze_all concorrentes
#: "idle" | "analisando" | "processando". Muda junto de _scan_running, no mesmo
#: try/finally de _executa_scan: o header e o 409 de perfil acabam no mesmo
#: instante. Quem abre a pagina (ou reconecta o WS) no meio do scan le daqui.
_scan_phase = "idle"
_peaks_semaphore = asyncio.Semaphore(3)  # teto de 3 computações em voo
_ws_clients: set[WebSocket] = set()
_token = secrets.token_urlsafe(32)
#: Servico de atualizacao, criado na primeira chamada de /api/update/*.
#: Fica None ate la porque descobrir o bundle (caminho_do_bundle) so faz
#: sentido se alguem perguntar; os testes injetam um com seams.
_updates: UpdateService | None = None


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
    #: id OU nome: a pill da Revisao troca por nome, o dropdown da Configuracao
    #: por id. Um dos dois e obrigatorio (checado no handler).
    name: str | None = None
    id: str | None = None


class CreateProfileBody(BaseModel):
    name: str
    copyFolders: bool = True


class RenameProfileBody(BaseModel):
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
        "weighted_f1": state.weighted_f1,
        "per_class": [list(row) for row in state.per_class] if state.per_class else None,
        "version": state.version,
        "last_trained_at": state.last_trained_at,
        "history": [
            {
                "ts": entry[0],
                "version": entry[1],
                "n_examples": entry[2],
                "accuracy": entry[3],
                "ordinal_mae": entry[4],
                "weighted_f1": entry[5],
            }
            for entry in state.history
        ],
        "deltas": dict(state.deltas),
        "failures": [list(f) for f in state.failures],
        "class_counts": list(state.class_counts),
        "decisions_since_train": state.decisions_since_train,
        "retrain_every": state.retrain_every,
        "min_examples": state.min_examples,
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
    # No primeiro uso (sem config) ainda nao ha servico; o front descobre
    # pelo /api/health e mostra o formulario em vez de esperar estado.
    if _service is None:
        return
    review = review_state(_service)
    library = library_state(_service)
    model = model_state(_service)
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
    global _scan_running, _scan_phase
    if _scan_running:
        raise _ScanJaRodando()
    _scan_running = True
    # Antes da thread nascer: o analyze_all anuncia "analisando" por conta
    # propria, mas ate la um GET /api/scan/status ja deve ver o scan rodando.
    _scan_phase = "analisando"
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

    def _fase(fase: str) -> None:
        # Mesmo padrao do _progresso (worker thread -> loop). A global e
        # atribuida aqui, na thread, para o GET /api/scan/status ja ver a
        # fase nova quando a mensagem sair.
        global _scan_phase
        _scan_phase = fase
        asyncio.run_coroutine_threadsafe(
            _broadcast({"type": "scan_phase", "phase": fase}), loop
        )

    try:
        return await asyncio.to_thread(
            service.analyze_all,
            on_progress=_progresso,
            should_cancel=_cancel_scan.is_set,
            on_phase=_fase,
        )
    finally:
        _scan_running = False
        _scan_phase = "idle"
        await _broadcast({"type": "scan_phase", "phase": "idle"})


async def _scan_inicial() -> None:
    """Scan de abertura: reconstroi a fila a partir do cache.

    Paridade com a janela Qt, que escaneia ao abrir -- sem isso a UI abre
    vazia depois de um restart mesmo com a inbox cheia, porque _inbox so e
    montada por analyze_all. Com tudo ja extraido e so reler o parquet;
    biblioteca virgem extrai de verdade, igual ao primeiro `dj scan`.
    """
    try:
        cancelado = await _executa_scan()
        await _broadcast_states()
        # Quem abriu a pagina no meio do scan de abertura recebeu "analisando"
        # e so volta a "concluido" com este evento, como no POST /api/scan.
        await _broadcast({"type": "scan_finished", "cancelled": cancelado})
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
# Endpoints — modelo
# ---------------------------------------------------------------------------


@app.post("/api/model/train")
async def train_model(token: str = Depends(_verify_token)):
    service = _get_service()
    try:
        service.train()
    except NotEnoughClassesError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    await _broadcast_states()
    await _broadcast({"type": "retrained"})
    return {"ok": True}


class _ModelSettingsBody(BaseModel):
    retrain_every: int = Field(ge=1)
    min_examples: int = Field(ge=1)


@app.post("/api/model/settings")
async def update_model_settings(
    body: _ModelSettingsBody, token: str = Depends(_verify_token)
):
    """Retreino automatico e minimo por classe, editados no painel da web.

    Carrega o toml real (load_config), revalida e grava com save_config --
    o saved e a fonte de verdade no disco. O servico vivo troca por
    set_model_settings em vez de recriar Service: nao ha re-scan, e o
    proximo treino automatico (decisions_since_train >= retrain_every)
    precisa ver o novo valor na mesma hora.
    """
    global _config
    service = _get_service()
    config_path = _config_path or service.config.data_dir.parent / "config.toml"
    try:
        config = load_config(config_path)
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        config = config.with_active_settings(
            retrain_every=body.retrain_every,
            min_examples=body.min_examples,
        )
        save_config(config_path, config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    service.set_model_settings(body.retrain_every, body.min_examples)
    _config = config
    await _broadcast_states()
    return {"ok": True}


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


@app.get("/api/scan/status")
async def scan_status(token: str = Depends(_verify_token)):
    return {"phase": _scan_phase, "running": _scan_running}


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
    if _config is None:
        # Primeiro uso: o formulario abre vazio e o proprio apply cria o
        # config.toml. Nao da 503 aqui porque essa e a tela que conserta o
        # 503 dos outros endpoints. data_dir vem sugerido ao lado do
        # config.toml -- sem isso o default de apply_all_drafts e
        # ".trackclassifier" DENTRO de ~/.trackclassifier.
        base = _config_path.parent if _config_path is not None else Path.cwd()
        return {
            "raw": {"paths": {"data_dir": str(base / "data")}},
            "active_profile": "default",
            "profiles": ["default"],
        }

    caminho = _config_path or _config.data_dir.parent / "config.toml"
    raw = read_raw(caminho) if caminho.exists() else {}
    return {
        "raw": raw,
        "active_profile": _config.active_profile,
        "profiles": list(_config.profiles.keys()),
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
    from .config import apply_all_drafts, drafts_from_raw, save_config, validate_settings

    drafts = drafts_from_raw(body.raw)
    active = str(body.raw.get("active_profile") or next(iter(drafts)))
    if active not in drafts:
        raise HTTPException(status_code=400, detail=f"Perfil desconhecido: {active}") from None

    # Revalida no servidor: a UI valida a cada tecla, mas o apply e a borda
    # que cria pasta/grava arquivo, e nao pode depender do cliente.
    erros = validate_settings(drafts[active])
    if erros:
        raise HTTPException(
            status_code=400,
            detail="; ".join(erro.message for erro in erros),
        ) from None

    if _config_path is not None:
        config_path = _config_path
    elif _config is not None:
        config_path = _config.data_dir.parent / "config.toml"
    else:
        config_path = Path("config.toml")
    try:
        # apply_all_drafts (nao apply_draft): o raw pode ter varios perfis e
        # o endpoint antigo descartava todos menos o ativo. save_config e o
        # passo que faltava -- sem ele o apply valia so ate o restart.
        # Modelo e organizacao vem de CADA perfil do raw (drafts); o
        # [model] global do formato antigo so entra como heranca.
        config = apply_all_drafts(drafts, active, config_path)
        save_config(config_path, config)
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


def _tamanho_mb(pasta: Path) -> float:
    """Soma recursiva em MB, com degradacao para 0: a sidebar da Configuracao
    nao pode derrubar so porque uma pasta ficou ilegivel."""
    if not pasta.is_dir():
        return 0.0
    try:
        total = sum(caminho.stat().st_size for caminho in pasta.rglob("*") if caminho.is_file())
    except OSError:
        return 0.0
    return round(total / (1024 * 1024), 1)


@app.get("/api/config/stats")
def get_config_stats(token: str = Depends(_verify_token)):
    """Numeros da sidebar e das pills da Configuracao: novas na entrada,
    tracks por pasta de destino, total de analises do banco e MB usados no
    data_dir. Sem servico (primeiro uso) degrada tudo para zero -- a tela de
    setup nem mostra esses numeros."""
    from .labels import Label
    from .library import scan_inbox, scan_labeled

    # Le o servico uma vez e deriva a config dele: _service e _config sao
    # reatribuidos em dois passos (apply/reset), e o switch de perfil so
    # troca service.config sem tocar em _config -- ler os dois globais
    # separados misturava servico novo com config velha.
    service = _service
    config = service.config if service is not None else _config
    if config is None:
        return {
            "data_dir_mb": 0,
            "analyses": 0,
            "inbox_new": 0,
            "destinations": {"up": 0, "neutral": 0, "down": 0},
        }

    sha1_cache = service.sha1_cache if service is not None else None
    # So o perfil ativo: um perfil copiado de outro compartilha as pastas, e o
    # scan_labeled deduplica por caminho (a faixa pertence ao primeiro perfil),
    # entao filtrar por ref.profile zeraria os numeros do perfil copiado.
    # Perfil incompleto nao varre nada e cai em zero.
    visao = replace(config, profiles={config.active_profile: config.profile})
    try:
        rotuladas = scan_labeled(visao, sha1_cache)
        novas = scan_inbox(visao, sha1_cache)
    except OSError:
        rotuladas, novas = [], []

    chave_por_rotulo = {Label.UP: "up", Label.NEUTRAL: "neutral", Label.DOWN: "down"}
    destinations = {"up": 0, "neutral": 0, "down": 0}
    for ref in rotuladas:
        destinations[chave_por_rotulo[ref.label]] += 1

    # Sem servico nao ha cache para distinguir nova de ja analisada: zero,
    # consistente com o resto da degradacao.
    inbox_new = 0
    if service is not None:
        inbox_new = sum(1 for ref in novas if service.cache.get(ref.sha1) is None)

    return {
        "data_dir_mb": _tamanho_mb(config.data_dir),
        "analyses": len(service.cache) if service is not None else 0,
        "inbox_new": inbox_new,
        "destinations": destinations,
    }


@app.post("/api/config/reset")
async def reset_config(token: str = Depends(_verify_token)):
    """Restaura os padroes do modelo sem tocar nas pastas: nao existe padrao
    sensato para inbox/destinos/data_dir de um acervo real. Salva e recria o
    servico como o apply, senao o reset valeria so ate o restart."""
    global _service, _config

    from .config import _MIN_EXEMPLOS_PADRAO, _RETRAIN_PADRAO, save_config

    config = _get_config().with_active_settings(
        retrain_every=_RETRAIN_PADRAO,
        min_examples=_MIN_EXEMPLOS_PADRAO,
        auto_move_enabled=False,
        create_under_root=False,
        keep_copy=False,
    )
    config_path = _config_path or config.data_dir.parent / "config.toml"
    try:
        save_config(config_path, config)
        _service = TrackService(config)
        _config = config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao restaurar padrões: {e}") from e

    await _broadcast({"type": "config_reloaded"})
    await _broadcast_states()
    return {"ok": True}


def _adota_config(config: Config, persiste: bool = True) -> None:
    """Grava o config e o entrega ao servico vivo E ao global `_config`.

    A troca de perfil so mexia em service.config: o TOML e `_config` ficavam
    com o perfil antigo, e o auto-save da Configuracao (que le /api/config)
    gravava no perfil errado. Aqui os tres andam juntos.
    """
    global _config
    if persiste:
        caminho = _config_path or config.data_dir.parent / "config.toml"
        save_config(caminho, config)
    if _service is not None:
        _service.set_config(config)
    _config = config


async def _muda_perfis(operacao) -> dict:
    """Roda uma operacao estrutural sobre os perfis do config vivo.

    409 durante o scan: o scan le o config a medida que avanca, e criar ou
    excluir perfil no meio dele mistura dois conjuntos de pastas.
    """
    if _scan_running:
        raise HTTPException(
            status_code=409, detail="Aguarde o scan terminar para alterar os perfis."
        )
    service = _get_service()
    antes = service.config
    try:
        config = operacao(antes)
    except ProfileError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e.args[0])) from e
    try:
        _adota_config(config)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Falha ao gravar o config: {e}") from e

    await _broadcast({"type": "profiles_changed"})
    if config.active_profile != antes.active_profile:
        await _broadcast(
            {
                "type": "profile_changed",
                "name": nome_de(config.active_profile, config.profile),
            }
        )
    await _broadcast_states()
    return para_json(config)


@app.get("/api/profiles")
def get_profiles(token: str = Depends(_verify_token)):
    # O servico vivo e a fonte: _config e service.config andam juntos
    # (_adota_config), mas os testes e o fluxo antigo trocam so o do servico.
    service = _service
    config = service.config if service is not None else _get_config()
    return para_json(config)


@app.post("/api/profiles")
async def create_profile(body: CreateProfileBody, token: str = Depends(_verify_token)):
    return await _muda_perfis(lambda c: criar(c, body.name, body.copyFolders)[0])


@app.patch("/api/profiles/{profile_id}")
async def rename_profile(
    profile_id: str, body: RenameProfileBody, token: str = Depends(_verify_token)
):
    return await _muda_perfis(lambda c: renomear(c, profile_id, body.name))


@app.post("/api/profiles/{profile_id}/duplicate")
async def duplicate_profile(profile_id: str, token: str = Depends(_verify_token)):
    return await _muda_perfis(lambda c: duplicar(c, profile_id)[0])


@app.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: str, token: str = Depends(_verify_token)):
    return await _muda_perfis(lambda c: excluir(c, profile_id))


@app.post("/api/profiles/switch")
async def switch_profile(body: SwitchProfileBody, token: str = Depends(_verify_token)):
    service = _get_service()
    ref = body.id or body.name
    if not ref:
        raise HTTPException(status_code=400, detail="Informe o perfil (id ou name).")
    config = service.config
    key = resolver(config, ref)
    if key is None:
        raise HTTPException(status_code=400, detail=f"Perfil desconhecido: {ref}")

    # Trocar NAO e bloqueado durante o scan (so muda qual fila aparece): o
    # mesmo caminho da pill da Revisao, que troca e escaneia em seguida.
    novo = ativar(config, key)
    try:
        _adota_config(novo)
    except OSError:
        # Sem gravar o TOML a troca ainda vale ate o restart; falhar aqui
        # prenderia a pessoa no perfil atual por causa de um disco somente-leitura.
        _adota_config(novo, persiste=False)
    await _broadcast({"type": "profile_changed", "name": nome_de(key, novo.profile)})
    await _broadcast_states()
    return para_json(novo)


# ---------------------------------------------------------------------------
# Endpoints -- atualizacao do app
# ---------------------------------------------------------------------------
#
# Sem tela no React de proposito: o mockup nao tem "Buscar atualizacoes", e a
# regra do projeto e nao inventar elemento. Quem fala com estes endpoints e o
# shell Electron (menu e dialogos nativos).


def _n_tracks() -> int:
    # Sem servico (primeiro uso) a biblioteca e vazia: 0 e a resposta certa, e
    # nao o 503 de _get_service(), que vazaria para a checagem de update.
    if _service is None:
        return 0
    return len(library_state(_service).rows)


def _estado_de_atualizacao() -> EstadoDeAtualizacao | None:
    # Funcao, e nao valor, porque o servidor sobe sem config no primeiro uso e
    # o data_dir so aparece depois do setup.
    if _config is None:
        return None
    return EstadoDeAtualizacao(_config.data_dir / "updates.json")


def _get_updates() -> UpdateService:
    global _updates
    if _updates is None:
        _updates = UpdateService(
            bundle=caminho_do_bundle(),
            state=_estado_de_atualizacao,
            n_tracks=_n_tracks,
        )
    return _updates


@app.get("/api/update/check")
async def update_check(manual: bool = False, token: str = Depends(_verify_token)):
    # A busca e rede bloqueante (urllib): fora do loop, senao a API toda
    # congela durante a requisicao ao GitHub.
    try:
        return await asyncio.to_thread(_get_updates().check, manual)
    except UpdateError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


class UpdateInstallBody(BaseModel):
    #: A versao que o usuario viu no dialogo; ver UpdateService.install_pending.
    version: str | None = None


@app.post("/api/update/install")
async def update_install(
    body: UpdateInstallBody | None = None, token: str = Depends(_verify_token)
):
    try:
        _get_updates().install_pending(body.version if body else None)
    except InstallInProgress:
        raise HTTPException(status_code=409, detail="Atualizacao ja em andamento") from None
    except AlreadyInstalled as e:
        # Antes de UpdateError (e subclasse dele): 409 e nao 400, porque nao e
        # pedido invalido, e o estado do servidor que ja concluiu a troca.
        raise HTTPException(status_code=409, detail=str(e)) from e
    except UpdateError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@app.get("/api/update/status")
def update_status(token: str = Depends(_verify_token)):
    return _get_updates().status()


@app.post("/api/update/dismiss")
def update_dismiss(token: str = Depends(_verify_token)):
    _get_updates().dismiss()
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True, "token": _token, "configured": _config is not None}


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
        # So para este socket: quem conecta no meio de um scan precisa da fase
        # para nao abrir em "Scan concluido" (a mensagem de inicio ja passou).
        await websocket.send_json({"type": "scan_phase", "phase": _scan_phase})
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
# Frontend build
# ---------------------------------------------------------------------------


def _web_dist() -> Path | None:
    """Acha o build do React, no checkout ou no bundle.

    Dois caminhos porque as duas origens tem layouts diferentes: rodando do
    repo o build fica em `web/dist` (na raiz, dois niveis acima de serve.py);
    no PyInstaller os dados vao para dentro do pacote, ao lado deste arquivo
    (`trackclassifier/web`). O `index.html` e o marcador -- um `dist/` vazio
    (npm build interrompido) nao pode ser montado, senao o servidor sobe
    servindo 404 em tudo.
    """
    raiz = Path(__file__).resolve().parent
    for candidato in (raiz / "web", raiz.parents[1] / "web" / "dist"):
        if (candidato / "index.html").is_file():
            return candidato
    return None


class StaticFilesIndexNoCache(StaticFiles):
    """StaticFiles que marca o index.html para sempre revalidar.

    Sem Cache-Control o Chromium/Electron aplica cache heuristico (~10% da
    idade do arquivo): a janela do shell chegou a abrir com a UI de um build
    velho mesmo com um dist novo no disco, porque o index.html velho (e os
    assets hashed que ele referenciava) continuavam validos no cache. Os
    assets sao content-hashed (index-[hash].js), entao podem seguir
    cacheaveis; quem nao pode envelhecer e o documento que aponta para eles.
    `no-cache` nao desliga o cache: obriga a revalidar por ETag, e um 304
    continua barato.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        resposta = await super().get_response(path, scope)
        if resposta.status_code == 200 and Path(getattr(resposta, "path", "")).name == "index.html":
            resposta.headers["Cache-Control"] = "no-cache"
        return resposta


def _mount_web(app_: FastAPI, dist: Path | None = None) -> bool:
    """Monta o build em `/` quando ele existe; devolve se montou.

    Em dev o Vite (5173) serve o front e faz proxy de `/api` e `/ws` para
    ca -- este mount nao e usado. No bundle nao ha Vite: o mesmo processo
    entrega os arquivos, e e isso que permite o shell abrir uma unica porta.

    O mount fica por ultimo de proposito: rotas registradas antes (`/api`,
    `/ws`) tem precedencia; qualquer outra coisa cai no estatico.
    """
    pasta = dist if dist is not None else _web_dist()
    if pasta is None or not (pasta / "index.html").is_file():
        return False
    app_.mount("/", StaticFilesIndexNoCache(directory=pasta, html=True), name="web")
    return True


_mount_web(app)


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
    global _service, _config, _config_path

    _config_path = Path(config_path)
    _service = None
    try:
        _config = load_config(_config_path)
    except ConfigError as e:
        # Arquivo existente e invalido continua sendo erro fatal: abrir em
        # modo de setup mascararia um config quebrado. Ausente e primeiro
        # uso -- sobe sem servico e a UI mostra o formulario.
        if _config_path.exists():
            print(f"Erro de configuração: {e}")
            raise SystemExit(1) from e
        _config = None
        print(f"Configuração ausente em {_config_path}: modo de primeiro uso.")

    if _config is not None:
        _service = TrackService(_config)

    print(f"Servidor rodando em http://{host}:{port}")
    print(f"Token: {_token}")
    print(f"WS: ws://{host}:{port}/ws?token={_token}")
    if open_browser:
        import webbrowser

        webbrowser.open(f"http://{host}:{port}")

    uvicorn.run(app, host=host, port=port, log_level="warning")
