from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

from .labels import LABEL_ORDER, LABEL_TARGET, Label

ALPHAS = np.logspace(-3, 3, 13)


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

    @property
    def is_fitted(self) -> bool:
        return self._ridge is not None

    def fit(self, X: np.ndarray, labels: list[Label]) -> None:
        presentes = set(labels)
        faltando = [rotulo.value for rotulo in LABEL_ORDER if rotulo not in presentes]
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

    def score(self, X: np.ndarray) -> np.ndarray:
        if self._ridge is None or self._scaler is None:
            raise NotFittedError("Modelo ainda nao treinado. Rode: dj train")
        bruto = self._ridge.predict(self._scaler.transform(np.asarray(X, dtype=np.float64)))
        return np.clip(bruto, 0.0, 1.0)

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, Path(path))

    @classmethod
    def load(cls, path: Path) -> "TrackModel":
        return joblib.load(Path(path))
