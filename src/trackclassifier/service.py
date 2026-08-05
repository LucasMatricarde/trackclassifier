from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .apply import FileVanishedError, move_to_folder
from .cache import AnalysisCache
from .config import Config
from .features import FeatureExtractor, HandcraftedExtractor, TrackAnalysis
from .labels import Label
from .library import TrackRef, scan_inbox, scan_labeled
from .model import Metrics, TrackModel


@dataclass(frozen=True)
class QueueItem:
    sha1: str
    filename: str
    path: Path
    label: Label
    score: float
    confidence: float
    bpm: float
    duration_s: float
    energy_curve: list[float]
    peak_offset_s: float


@dataclass(frozen=True)
class FailedItem:
    filename: str
    reason: str


class TrackService:
    def __init__(self, config: Config, extractor: FeatureExtractor | None = None):
        self.config = config
        self.extractor = extractor or HandcraftedExtractor()
        self.cache = AnalysisCache(config.data_dir / "analyses.parquet")
        self.model_path = config.data_dir / "model.joblib"
        self.model = TrackModel.load(self.model_path) if self.model_path.is_file() else TrackModel()
        self._labeled: list[TrackRef] = []
        self._inbox: list[TrackRef] = []
        self._failures: list[FailedItem] = []
        self._decisions_since_train = 0

    def analyze_all(self) -> None:
        self._failures = []
        self._labeled = self._analyze(scan_labeled(self.config))
        self._inbox = self._analyze(scan_inbox(self.config))
        self.cache.save()

    def _analyze(self, refs: list[TrackRef]) -> list[TrackRef]:
        aceitos: list[TrackRef] = []
        for ref in refs:
            if self.cache.get(ref.sha1) is not None:
                aceitos.append(ref)
                continue
            try:
                analise = self.extractor.extract(ref.path)
            except Exception as erro:
                self._failures.append(FailedItem(filename=ref.path.name, reason=str(erro)))
                continue
            self.cache.put(ref.sha1, ref.path.name, self.extractor.name, analise)
            aceitos.append(ref)
        return aceitos

    def _analysis(self, ref: TrackRef) -> TrackAnalysis:
        analise = self.cache.get(ref.sha1)
        assert analise is not None
        return analise

    def train(self) -> Metrics:
        matriz = np.asarray([self._analysis(ref).vector for ref in self._labeled])
        rotulos = [ref.label for ref in self._labeled if ref.label is not None]
        self.model.fit(matriz, rotulos, min_examples=self.config.min_examples)
        self.model.save(self.model_path)
        self._decisions_since_train = 0
        assert self.model.metrics_ is not None
        return self.model.metrics_

    def failures(self) -> list[FailedItem]:
        return list(self._failures)

    def queue(self) -> list[QueueItem]:
        vivos = [ref for ref in self._inbox if ref.path.is_file()]
        self._inbox = vivos
        if not vivos or not self.model.is_fitted:
            return []

        matriz = np.asarray([self._analysis(ref).vector for ref in vivos])
        predicoes = self.model.predict(matriz)

        itens = []
        for ref, predicao in zip(vivos, predicoes):
            analise = self._analysis(ref)
            itens.append(
                QueueItem(
                    sha1=ref.sha1,
                    filename=ref.path.name,
                    path=ref.path,
                    label=predicao.label,
                    score=predicao.score,
                    confidence=predicao.confidence,
                    bpm=analise.bpm,
                    duration_s=analise.duration_s,
                    energy_curve=analise.energy_curve,
                    peak_offset_s=analise.peak_offset_s,
                )
            )
        return sorted(itens, key=lambda item: item.confidence)

    def path_for(self, sha1: str) -> Path:
        for ref in self._inbox:
            if ref.sha1 == sha1:
                return ref.path
        raise KeyError(f"Track fora da fila: {sha1}")

    def decide(self, sha1: str, label: Label) -> bool:
        ref = next((r for r in self._inbox if r.sha1 == sha1), None)
        if ref is None:
            return False

        self._inbox = [r for r in self._inbox if r.sha1 != sha1]
        try:
            destino = move_to_folder(ref.path, self.config.folders[label])
        except FileVanishedError:
            return False

        self._labeled.append(TrackRef(path=destino, label=label, sha1=ref.sha1))
        self._decisions_since_train += 1
        if self._decisions_since_train >= self.config.retrain_every:
            self.train()
            return True
        return False

    def bulk_approve(self, min_confidence: float) -> int:
        alvos = [item for item in self.queue() if item.confidence >= min_confidence]
        for item in alvos:
            self.decide(item.sha1, item.label)
        return len(alvos)
