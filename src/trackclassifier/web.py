from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .labels import Label
from .service import TrackService

STATIC_DIR = Path(__file__).parent / "static"


class DecideRequest(BaseModel):
    sha1: str
    label: Label


class BulkApproveRequest(BaseModel):
    min_confidence: float


def create_app(service: TrackService) -> FastAPI:
    app = FastAPI(title="TrackClassifier")

    @app.get("/api/queue")
    def fila() -> dict:
        metricas = service.model.metrics_
        return {
            "items": [
                {
                    "sha1": item.sha1,
                    "filename": item.filename,
                    "label": item.label.value,
                    "score": item.score,
                    "confidence": item.confidence,
                    "bpm": item.bpm,
                    "duration_s": item.duration_s,
                    "energy_curve": item.energy_curve,
                    "peak_offset_s": item.peak_offset_s,
                }
                for item in service.queue()
            ],
            "low_confidence_mode": service.model.low_confidence_mode,
            "metrics": None
            if metricas is None
            else {
                "accuracy": metricas.accuracy,
                "ordinal_mae": metricas.ordinal_mae,
                "confusion": metricas.confusion,
                "n_examples": metricas.n_examples,
            },
        }

    @app.get("/api/failures")
    def falhas() -> dict:
        return {
            "items": [
                {"filename": falha.filename, "reason": falha.reason}
                for falha in service.failures()
            ]
        }

    @app.post("/api/decide")
    def decidir(pedido: DecideRequest) -> dict:
        if all(item.sha1 != pedido.sha1 for item in service.queue()):
            raise HTTPException(status_code=404, detail="Track fora da fila")
        return {"retrained": service.decide(pedido.sha1, pedido.label)}

    @app.post("/api/bulk-approve")
    def aprovar_em_bloco(pedido: BulkApproveRequest) -> dict:
        return {"moved": service.bulk_approve(pedido.min_confidence)}

    @app.get("/")
    def raiz() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
