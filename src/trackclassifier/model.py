from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import Ridge, RidgeCV
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .labels import LABEL_ORDER, LABEL_TARGET, Label

ALPHAS = np.logspace(-3, 3, 13)


def classes_faltando(labels: Iterable[Label]) -> list[str]:
    """Classes de LABEL_ORDER ausentes, na ordem ordinal.

    Vazio = da para treinar. Vive aqui, e nao na UI, porque a aba Modelo
    precisa da mesma resposta ANTES do clique -- para desabilitar o botao
    com o motivo a vista, em vez de deixar o NotEnoughClassesError chegar
    na status bar depois. Duas copias da regra e uma copia a mais.
    """
    presentes = set(labels)
    return [rotulo.value for rotulo in LABEL_ORDER if rotulo not in presentes]


@dataclass(frozen=True)
class Metrics:
    accuracy: float
    ordinal_mae: float
    confusion: list[list[int]]
    n_examples: int


@dataclass(frozen=True)
class Prediction:
    label: Label
    score: float
    confidence: float


MIN_MARGIN = 0.05


def _labels_from_scores(scores: np.ndarray, t1: float, t2: float) -> list[Label]:
    return [
        Label.DOWN if s < t1 else (Label.NEUTRAL if s < t2 else Label.UP) for s in scores
    ]


def _threshold_candidates(scores: np.ndarray) -> list[float]:
    ordenados = np.unique(np.round(scores, 6))
    if len(ordenados) < 2:
        return [0.33, 0.66]
    return [float((a + b) / 2.0) for a, b in zip(ordenados[:-1], ordenados[1:], strict=True)]


def _evaluate(previstos: list[Label], reais: list[Label]) -> tuple[float, float, list[list[int]]]:
    indice = {rotulo: posicao for posicao, rotulo in enumerate(LABEL_ORDER)}
    confusao = [[0, 0, 0] for _ in range(3)]
    acertos = 0
    erro_ordinal = 0.0
    for previsto, real in zip(previstos, reais, strict=True):
        confusao[indice[real]][indice[previsto]] += 1
        acertos += int(previsto == real)
        erro_ordinal += abs(indice[previsto] - indice[real])
    total = max(len(reais), 1)
    return acertos / total, erro_ordinal / total, confusao


class NotEnoughClassesError(Exception):
    pass


class NotFittedError(Exception):
    pass


class TrackModel:
    def __init__(self) -> None:
        self._scaler: StandardScaler | None = None
        self._ridge: RidgeCV | None = None
        self.alpha_: float = 0.0
        self.n_examples_: int = 0
        self.thresholds_: tuple[float, float] = (0.33, 0.66)
        self.metrics_: Metrics | None = None
        self.low_confidence_mode: bool = True

    @property
    def is_fitted(self) -> bool:
        return self._ridge is not None

    def fit(self, X: np.ndarray, labels: list[Label], min_examples: int = 15) -> None:
        faltando = classes_faltando(labels)
        if faltando:
            raise NotEnoughClassesError(
                "Nao da para treinar sem exemplos de todas as classes. "
                f"Faltam rotulos: {', '.join(faltando)}"
            )

        X = np.asarray(X, dtype=np.float64)
        y = np.asarray([LABEL_TARGET[rotulo] for rotulo in labels], dtype=np.float64)

        self._scaler = StandardScaler().fit(X)
        self._ridge = RidgeCV(alphas=ALPHAS).fit(self._scaler.transform(X), y)
        self.alpha_ = float(self._ridge.alpha_)
        self.n_examples_ = int(len(labels))
        self.low_confidence_mode = self.n_examples_ < min_examples

        fora_de_amostra = np.clip(
            cross_val_predict(
                make_pipeline(StandardScaler(), Ridge(alpha=self.alpha_)),
                X,
                y,
                cv=LeaveOneOut(),
            ),
            0.0,
            1.0,
        )
        self.thresholds_ = self._calibrate(fora_de_amostra, labels)

        t1, t2 = self.thresholds_
        acuracia, erro_ordinal, confusao = _evaluate(
            _labels_from_scores(fora_de_amostra, t1, t2), labels
        )
        self.metrics_ = Metrics(
            accuracy=acuracia,
            ordinal_mae=erro_ordinal,
            confusion=confusao,
            n_examples=self.n_examples_,
        )

    @staticmethod
    def _calibrate(scores: np.ndarray, labels: list[Label]) -> tuple[float, float]:
        candidatos = _threshold_candidates(scores)
        melhor = (0.33, 0.66)
        melhor_acuracia = -1.0
        melhor_erro = float("inf")
        for i, t1 in enumerate(candidatos):
            for t2 in candidatos[i + 1 :]:
                acuracia, erro_ordinal, _ = _evaluate(
                    _labels_from_scores(scores, t1, t2), labels
                )
                if acuracia > melhor_acuracia or (
                    acuracia == melhor_acuracia and erro_ordinal < melhor_erro
                ):
                    melhor, melhor_acuracia, melhor_erro = (t1, t2), acuracia, erro_ordinal
        return melhor

    def score(self, X: np.ndarray) -> np.ndarray:
        if self._ridge is None or self._scaler is None:
            raise NotFittedError("Modelo ainda nao treinado. Rode: dj train")
        bruto = self._ridge.predict(self._scaler.transform(np.asarray(X, dtype=np.float64)))
        return np.clip(bruto, 0.0, 1.0)

    def predict(self, X: np.ndarray) -> list[Prediction]:
        escores = self.score(X)
        t1, t2 = self.thresholds_
        margem = max((t2 - t1) / 2.0, MIN_MARGIN)
        fator = 0.5 if self.low_confidence_mode else 1.0

        predicoes: list[Prediction] = []
        for escore, rotulo in zip(escores, _labels_from_scores(escores, t1, t2), strict=True):
            distancia = min(abs(escore - t1), abs(escore - t2))
            confianca = min(1.0, distancia / margem) * fator
            predicoes.append(
                Prediction(label=rotulo, score=float(escore), confidence=float(confianca))
            )
        return predicoes

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, Path(path))

    @classmethod
    def load(cls, path: Path) -> TrackModel:
        return joblib.load(Path(path))
