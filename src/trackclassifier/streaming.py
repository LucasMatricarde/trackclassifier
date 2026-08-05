import mimetypes
import re
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from .audio_io import AudioDecodeError, needs_transcode
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

    proc = subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-i", str(path), "-b:a", "192k", str(destino)],
        capture_output=True,
    )
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

    inicio = int(inicio_bruto) if inicio_bruto else 0
    fim = int(fim_bruto) if fim_bruto else tamanho - 1
    fim = min(fim, tamanho - 1)
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
        except KeyError:
            raise HTTPException(status_code=404, detail="Track fora da fila")
        if not caminho.is_file():
            raise HTTPException(status_code=404, detail="Arquivo nao existe mais")
        return range_response(
            ensure_playable(caminho, cache_dir), request.headers.get("range")
        )
