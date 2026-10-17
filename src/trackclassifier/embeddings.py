from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from .audio_io import decode

YAMNET_SAMPLE_RATE = 16_000
CLIP_SECONDS = 9.6
CLIP_POSITIONS = (0.1, 0.3, 0.5, 0.7, 0.9)
EMBEDDING_DIM = 1_024
EXTRACTION_VERSION = "yamnet-five-clips-v1"


class EmbeddingUnavailableError(RuntimeError):
    pass


class EmbeddingBackend(Protocol):
    def embed(self, waveform: np.ndarray) -> np.ndarray: ...


def deterministic_clips(
    waveform: np.ndarray,
    *,
    sample_rate: int = YAMNET_SAMPLE_RATE,
    clip_seconds: float = CLIP_SECONDS,
) -> np.ndarray:
    """Recorta cinco janelas centradas em 10/30/50/70/90% da duracao.

    Tracks menores que uma janela sao alinhadas no inicio e preenchidas com
    zeros. Isso evita esticar o audio e preserva uma entrada de tamanho fixo.
    """

    audio = np.asarray(waveform, dtype=np.float32).reshape(-1)
    clip_size = int(round(clip_seconds * sample_rate))
    if audio.size <= clip_size:
        padded = np.zeros(clip_size, dtype=np.float32)
        padded[: audio.size] = audio
        return np.repeat(padded[None, :], len(CLIP_POSITIONS), axis=0)

    max_start = audio.size - clip_size
    starts = [
        min(max(int(round(position * audio.size - clip_size / 2)), 0), max_start)
        for position in CLIP_POSITIONS
    ]
    return np.stack([audio[start : start + clip_size] for start in starts])


def aggregate_embeddings(embeddings: np.ndarray) -> np.ndarray:
    values = np.asarray(embeddings, dtype=np.float32)
    if values.ndim != 2 or values.shape[1] != EMBEDDING_DIM:
        raise ValueError(
            f"Embeddings YAMNet devem ter shape (n, {EMBEDDING_DIM}), recebido {values.shape}"
        )
    return np.concatenate((values.mean(axis=0), values.std(axis=0))).astype(np.float32)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bundled_model_path() -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidates = (
        root / "trackclassifier" / "assets" / "yamnet.onnx",
        root / "assets" / "yamnet.onnx",
        Path(__file__).resolve().parent / "assets" / "yamnet.onnx",
    )
    return next((path for path in candidates if path.is_file()), candidates[-1])


class YamnetOnnxBackend:
    """Adaptador local do YAMNet ONNX; importa o runtime apenas sob demanda."""

    def __init__(self, model_path: Path | None = None):
        self.model_path = Path(model_path or bundled_model_path())
        if not self.model_path.is_file():
            raise EmbeddingUnavailableError(f"Modelo YAMNet ausente: {self.model_path}")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise EmbeddingUnavailableError("ONNX Runtime nao esta instalado") from exc
        self._session = ort.InferenceSession(
            str(self.model_path), providers=["CPUExecutionProvider"]
        )
        self._input_name = self._session.get_inputs()[0].name

    def embed(self, waveform: np.ndarray) -> np.ndarray:
        audio = np.asarray(waveform, dtype=np.float32)
        input_meta = self._session.get_inputs()[0]
        if len(input_meta.shape) == 2:
            audio = audio[None, :]
        outputs = self._session.run(None, {self._input_name: audio})
        candidates = [
            np.asarray(value) for value in outputs if np.asarray(value).shape[-1:] == (1024,)
        ]
        if not candidates:
            raise EmbeddingUnavailableError(
                "O modelo ONNX nao devolveu embeddings de 1024 dimensoes"
            )
        frames = candidates[0].reshape(-1, EMBEDDING_DIM)
        return frames.mean(axis=0).astype(np.float32)


class YamnetEmbeddingExtractor:
    def __init__(self, backend: EmbeddingBackend):
        self.backend = backend

    def extract(self, path: Path) -> np.ndarray:
        waveform = decode(path, sample_rate=YAMNET_SAMPLE_RATE)
        per_clip = np.stack([self.backend.embed(clip) for clip in deterministic_clips(waveform)])
        return aggregate_embeddings(per_clip)


class EmbeddingCache:
    """Cache incremental indexado pelo audio e pelas duas versoes relevantes."""

    _COLUMNS = ("sha1", "weights_sha256", "extraction_version", "vector")

    def __init__(self, path: Path):
        self.path = Path(path)
        self._rows: dict[tuple[str, str, str], np.ndarray] = {}
        if self.path.is_file():
            try:
                frame = pd.read_parquet(self.path)
            except Exception:
                frame = None
            if frame is not None:
                for row in frame.to_dict(orient="records"):
                    key = (row["sha1"], row["weights_sha256"], row["extraction_version"])
                    self._rows[key] = np.asarray(row["vector"], dtype=np.float32)

    def get(
        self, sha1: str, weights_sha256: str, extraction_version: str
    ) -> np.ndarray | None:
        value = self._rows.get((sha1, weights_sha256, extraction_version))
        return None if value is None else value.copy()

    def put(
        self,
        sha1: str,
        *,
        weights_sha256: str,
        extraction_version: str,
        vector: np.ndarray,
    ) -> None:
        values = np.asarray(vector, dtype=np.float32).reshape(-1)
        if values.shape != (EMBEDDING_DIM * 2,):
            raise ValueError(f"Vetor agregado deve ter {EMBEDDING_DIM * 2} dimensoes")
        self._rows[(sha1, weights_sha256, extraction_version)] = values.copy()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        records = [
            {
                "sha1": key[0],
                "weights_sha256": key[1],
                "extraction_version": key[2],
                "vector": value.tolist(),
            }
            for key, value in self._rows.items()
        ]
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        pd.DataFrame(records, columns=self._COLUMNS).to_parquet(temp, index=False)
        os.replace(temp, self.path)
