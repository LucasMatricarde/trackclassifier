from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import librosa
import numpy as np
import pyloudnorm

from .audio_io import ANALYSIS_SR, decode
from .descriptors import DESCRIPTOR_NAMES, describe_window

MAX_WINDOW_SECONDS = 10.0
MIN_TRACK_SECONDS = 10.0

STAT_SUFFIXES = ["median", "p90", "p10", "ratio"]
GLOBAL_NAMES = ["bpm", "lufs", "dynamic_range_db", "duration_s"]

FEATURE_NAMES: list[str] = [
    f"{descritor}_{sufixo}" for descritor in DESCRIPTOR_NAMES for sufixo in STAT_SUFFIXES
] + GLOBAL_NAMES

_EPS = 1e-9


class TrackTooShortError(Exception):
    pass


@dataclass(frozen=True)
class TrackAnalysis:
    vector: np.ndarray
    energy_curve: list[float]
    peak_offset_s: float
    bpm: float
    duration_s: float


class FeatureExtractor(Protocol):
    name: str

    def extract(self, path: Path) -> TrackAnalysis: ...


def _stats(valores: list[float]) -> list[float]:
    arr = np.asarray(valores, dtype=np.float64)
    mediana = float(np.median(arr))
    p90 = float(np.percentile(arr, 90))
    p10 = float(np.percentile(arr, 10))
    razao = float(p90 / (abs(mediana) + _EPS))
    return [mediana, p90, p10, razao]


def _window_plan(duracao: float) -> tuple[float, float]:
    janela = min(MAX_WINDOW_SECONDS, duracao / 3.0)
    return janela, janela / 2.0


class HandcraftedExtractor:
    name = "handcrafted-v1"

    def extract(self, path: Path) -> TrackAnalysis:
        y = decode(path, sample_rate=ANALYSIS_SR)
        duracao = len(y) / ANALYSIS_SR
        if duracao < MIN_TRACK_SECONDS:
            raise TrackTooShortError(
                f"Track de {duracao:.1f}s e curta demais (minimo {MIN_TRACK_SECONDS:.0f}s): "
                f"{Path(path).name}"
            )

        janela_s, salto_s = _window_plan(duracao)
        tamanho = int(janela_s * ANALYSIS_SR)
        salto = max(int(salto_s * ANALYSIS_SR), 1)

        por_descritor: dict[str, list[float]] = {nome: [] for nome in DESCRIPTOR_NAMES}
        curva_energia: list[float] = []
        offsets: list[float] = []

        for inicio in range(0, len(y) - tamanho + 1, salto):
            trecho = y[inicio : inicio + tamanho]
            medidas = describe_window(trecho, ANALYSIS_SR)
            for nome, valor in medidas.items():
                por_descritor[nome].append(valor)
            curva_energia.append(medidas["rms"])
            offsets.append(inicio / ANALYSIS_SR)

        vetor_janelas: list[float] = []
        for nome in DESCRIPTOR_NAMES:
            vetor_janelas.extend(_stats(por_descritor[nome]))

        energia = np.asarray(curva_energia, dtype=np.float64)
        faixa_db = 20.0 * np.log10(
            (float(np.percentile(energia, 95)) + _EPS) / (float(np.percentile(energia, 10)) + _EPS)
        )

        tempo = librosa.beat.beat_track(y=y, sr=ANALYSIS_SR)[0]
        bpm = float(np.atleast_1d(tempo)[0])

        medidor = pyloudnorm.Meter(ANALYSIS_SR)
        lufs = float(medidor.integrated_loudness(y.astype(np.float64)))
        if not np.isfinite(lufs):
            lufs = -70.0

        globais = [bpm, lufs, float(faixa_db), float(duracao)]
        vetor = np.asarray(vetor_janelas + globais, dtype=np.float64)

        return TrackAnalysis(
            vector=vetor,
            energy_curve=[float(v) for v in curva_energia],
            peak_offset_s=float(offsets[int(np.argmax(energia))]),
            bpm=bpm,
            duration_s=float(duracao),
        )
