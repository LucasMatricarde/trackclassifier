import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURE_NAMES, TrackAnalysis

_COLUNAS_META = [
    "sha1",
    "filename",
    "extractor",
    "energy_curve",
    "peak_offset_s",
    "meta_bpm",
    "meta_duration_s",
]
_CHUNK = 1024 * 1024


def file_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with Path(path).open("rb") as handle:
        for bloco in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(bloco)
    return digest.hexdigest()


class AnalysisCache:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._linhas: dict[str, dict] = {}
        if self.path.is_file():
            frame = pd.read_parquet(self.path)
            for registro in frame.to_dict(orient="records"):
                self._linhas[registro["sha1"]] = registro

    def __len__(self) -> int:
        return len(self._linhas)

    def get(self, sha1: str) -> TrackAnalysis | None:
        registro = self._linhas.get(sha1)
        if registro is None:
            return None
        return TrackAnalysis(
            vector=np.asarray([registro[nome] for nome in FEATURE_NAMES], dtype=np.float64),
            energy_curve=json.loads(registro["energy_curve"]),
            peak_offset_s=float(registro["peak_offset_s"]),
            bpm=float(registro["meta_bpm"]),
            duration_s=float(registro["meta_duration_s"]),
        )

    def put(self, sha1: str, filename: str, extractor: str, analysis: TrackAnalysis) -> None:
        registro = {
            "sha1": sha1,
            "filename": filename,
            "extractor": extractor,
            "energy_curve": json.dumps(analysis.energy_curve),
            "peak_offset_s": float(analysis.peak_offset_s),
            "meta_bpm": float(analysis.bpm),
            "meta_duration_s": float(analysis.duration_s),
        }
        registro.update(
            {nome: float(valor) for nome, valor in zip(FEATURE_NAMES, analysis.vector)}
        )
        self._linhas[sha1] = registro

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        frame = pd.DataFrame(list(self._linhas.values()), columns=_COLUNAS_META + FEATURE_NAMES)
        frame.to_parquet(self.path, index=False)
