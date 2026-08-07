import numpy as np
import pytest

from trackclassifier.labels import Label
from trackclassifier.model import NotEnoughClassesError, NotFittedError, TrackModel


def dataset_sintetico(n_por_classe=25, ruido=0.15, seed=3):
    """Feature 0 codifica energia; as outras 43 sao ruido puro."""
    gerador = np.random.default_rng(seed)
    linhas, rotulos = [], []
    for rotulo, centro in ((Label.DOWN, 0.0), (Label.NEUTRAL, 0.5), (Label.UP, 1.0)):
        for _ in range(n_por_classe):
            vetor = gerador.standard_normal(44)
            vetor[0] = centro + gerador.normal(0.0, ruido)
            linhas.append(vetor)
            rotulos.append(rotulo)
    return np.asarray(linhas), rotulos


def test_treina_e_produz_escores_ordenados_por_classe():
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)

    escores = modelo.score(X)
    media = {
        rotulo: float(np.mean([e for e, r in zip(escores, y, strict=True) if r == rotulo]))
        for rotulo in (Label.DOWN, Label.NEUTRAL, Label.UP)
    }

    assert media[Label.DOWN] < media[Label.NEUTRAL] < media[Label.UP]


def test_escore_fica_no_intervalo_fechado():
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)

    escores = modelo.score(X)

    assert escores.min() >= 0.0
    assert escores.max() <= 1.0


def test_recusa_treinar_sem_as_tres_classes():
    X, y = dataset_sintetico()
    sem_up = [(vetor, rotulo) for vetor, rotulo in zip(X, y, strict=True) if rotulo != Label.UP]
    Xs = np.asarray([v for v, _ in sem_up])
    ys = [r for _, r in sem_up]

    with pytest.raises(NotEnoughClassesError) as exc:
        TrackModel().fit(Xs, ys)

    assert "+1" in str(exc.value)


def test_score_antes_de_treinar_levanta_erro():
    with pytest.raises(NotFittedError):
        TrackModel().score(np.zeros((1, 44)))


def test_registra_alpha_escolhido_e_tamanho_do_dataset():
    X, y = dataset_sintetico(n_por_classe=10)
    modelo = TrackModel()
    modelo.fit(X, y)

    assert modelo.alpha_ > 0
    assert modelo.n_examples_ == 30
    assert modelo.is_fitted is True


def test_persiste_e_recarrega_produzindo_os_mesmos_escores(tmp_path):
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)
    esperado = modelo.score(X)

    destino = tmp_path / "modelo.joblib"
    modelo.save(destino)
    recarregado = TrackModel.load(destino)

    assert np.allclose(recarregado.score(X), esperado)
    assert recarregado.n_examples_ == modelo.n_examples_


def test_classes_faltando_devolve_na_ordem_ordinal():
    from trackclassifier.labels import Label
    from trackclassifier.model import classes_faltando

    assert classes_faltando([Label.NEUTRAL]) == ["-1", "+1"]


def test_classes_faltando_vazio_quando_as_tres_existem():
    from trackclassifier.labels import Label
    from trackclassifier.model import classes_faltando

    assert classes_faltando([Label.UP, Label.DOWN, Label.NEUTRAL]) == []


def test_classes_faltando_sem_exemplo_nenhum_devolve_as_tres():
    from trackclassifier.model import classes_faltando

    assert classes_faltando([]) == ["-1", "neutra", "+1"]
