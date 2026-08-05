import mimetypes
import re
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from .audio_io import SUBPROCESS_TIMEOUT_S, AudioDecodeError, needs_transcode
from .service import TrackService

_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


def ensure_playable(path: Path, cache_dir: Path) -> Path:
    path = Path(path)
    if not needs_transcode(path):
        return path

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    destino = cache_dir / f"{path.stem}.mp3"
    if destino.is_file():
        return destino

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioDecodeError("ffmpeg nao encontrado no PATH. Instale com: brew install ffmpeg")

    try:
        proc = subprocess.run(
            [ffmpeg, "-v", "error", "-y", "-i", str(path), "-b:a", "192k", str(destino)],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioDecodeError(f"Tempo esgotado ao transcodificar {path.name}") from exc
    if proc.returncode != 0:
        raise AudioDecodeError(f"Falha ao transcodificar {path.name}")
    return destino


def range_response(path: Path, range_header: str | None) -> Response:
    path = Path(path)
    dados = path.read_bytes()
    tamanho = len(dados)
    tipo = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    correspondencia = _RANGE.match(range_header or "")
    if correspondencia is None:
        return Response(
            content=dados,
            media_type=tipo,
            headers={"accept-ranges": "bytes", "content-length": str(tamanho)},
        )

    inicio_bruto, fim_bruto = correspondencia.groups()
    if not inicio_bruto and not fim_bruto:
        # "bytes=-" nao especifica nada util: trata como pedido do arquivo inteiro.
        return Response(
            content=dados,
            media_type=tipo,
            headers={"accept-ranges": "bytes", "content-length": str(tamanho)},
        )

    if not inicio_bruto:
        # range de sufixo (RFC 7233): "bytes=-500" pede os ULTIMOS 500 bytes,
        # nao os primeiros 500. "bytes=-0" e invalido (zero bytes de sufixo);
        # trata como malformado e cai no fallback de arquivo inteiro abaixo.
        n = int(fim_bruto)
        if n == 0:
            return Response(
                content=dados,
                media_type=tipo,
                headers={"accept-ranges": "bytes", "content-length": str(tamanho)},
            )
        n = min(n, tamanho)
        inicio, fim = tamanho - n, tamanho - 1
    else:
        inicio = int(inicio_bruto)
        fim = min(int(fim_bruto), tamanho - 1) if fim_bruto else tamanho - 1

    if inicio > fim or inicio < 0:
        raise HTTPException(status_code=416, detail="Range invalido")

    trecho = dados[inicio : fim + 1]
    return Response(
        content=trecho,
        status_code=206,
        media_type=tipo,
        headers={
            "accept-ranges": "bytes",
            "content-range": f"bytes {inicio}-{fim}/{tamanho}",
            "content-length": str(len(trecho)),
        },
    )


def register_audio_route(app: FastAPI, service: TrackService, cache_dir: Path) -> None:
    @app.get("/api/audio/{sha1}")
    def audio(sha1: str, request: Request) -> Response:
        try:
            caminho = service.path_for(sha1)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Track fora da fila") from exc
        if not caminho.is_file():
            raise HTTPException(status_code=404, detail="Arquivo nao existe mais")
        # cache_dir e por sha1: dois arquivos-fonte com o mesmo stem (ex.
        # "SetA/01.aiff" e "SetB/01.aiff") nao podem colidir no mesmo
        # destino.mp3 dentro de ensure_playable, que so chaveia por stem.
        return range_response(
            ensure_playable(caminho, cache_dir / sha1), request.headers.get("range")
        )
