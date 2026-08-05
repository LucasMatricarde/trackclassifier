from pathlib import Path

import numpy as np

from trackclassifier.extraction import extract_one
from trackclassifier.features import TrackAnalysis


class _ExtratorSucesso:
    name = "sucesso-v1"

    def extract(self, path: Path) -> TrackAnalysis:
        return TrackAnalysis(
            vector=np.zeros(44, dtype=np.float64),
            energy_curve=[0.1, 0.2],
            peak_offset_s=1.0,
            bpm=120.0,
            duration_s=30.0,
        )


class _ExtratorFalha:
    name = "falha-v1"

    def extract(self, path: Path) -> TrackAnalysis:
        raise ValueError(f"nao consegui decodificar {path.name}")


def test_sucesso_devolve_analise_e_erro_none(tmp_path):
    caminho = tmp_path / "t.mp3"

    analise, erro = extract_one(_ExtratorSucesso(), caminho)

    assert isinstance(analise, TrackAnalysis)
    assert erro is None


def test_falha_devolve_none_e_mensagem_de_erro(tmp_path):
    caminho = tmp_path / "quebrado.mp3"

    analise, erro = extract_one(_ExtratorFalha(), caminho)

    assert analise is None
    assert "quebrado.mp3" in erro


def test_limita_threads_de_blas_durante_a_chamada(tmp_path, monkeypatch):
    chamadas = []

    class _LimiteEspiao:
        def __init__(self, *args, **kwargs):
            chamadas.append((args, kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr("trackclassifier.extraction.threadpool_limits", _LimiteEspiao)

    extract_one(_ExtratorSucesso(), tmp_path / "t.mp3")

    assert len(chamadas) == 1
