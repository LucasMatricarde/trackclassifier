import numpy as np
import pytest

from trackclassifier.labels import Label
from trackclassifier.model import Metrics, Prediction, TrackModel
from tests.test_model_core import dataset_sintetico


def test_limiares_ficam_ordenados_e_dentro_do_intervalo():
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)

    t1, t2 = modelo.thresholds_

    assert 0.0 < t1 < t2 < 1.0


def test_predicao_recupera_os_rotulos_de_um_dataset_separavel():
    X, y = dataset_sintetico(n_por_classe=25, ruido=0.08)
    modelo = TrackModel()
    modelo.fit(X, y)

    previstos = [predicao.label for predicao in modelo.predict(X)]
    acertos = sum(1 for p, real in zip(previstos, y) if p == real)

    assert acertos / len(y) > 0.85


def test_predicao_retorna_estrutura_completa():
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)

    predicao = modelo.predict(X[:1])[0]

    assert isinstance(predicao, Prediction)
    assert predicao.label in (Label.DOWN, Label.NEUTRAL, Label.UP)
    assert 0.0 <= predicao.score <= 1.0
    assert 0.0 <= predicao.confidence <= 1.0


def test_confianca_cai_perto_do_limiar():
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)
    t1, _ = modelo.thresholds_

    escores = modelo.score(X)
    indice_proximo = int(np.argmin(np.abs(escores - t1)))
    indice_extremo = int(np.argmax(escores))

    predicoes = modelo.predict(X)

    assert predicoes[indice_proximo].confidence < predicoes[indice_extremo].confidence


def test_metricas_sao_reportadas():
    X, y = dataset_sintetico(n_por_classe=25, ruido=0.08)
    modelo = TrackModel()
    modelo.fit(X, y)

    metricas = modelo.metrics_

    assert isinstance(metricas, Metrics)
    assert 0.0 <= metricas.accuracy <= 1.0
    assert metricas.accuracy > 0.8
    assert metricas.ordinal_mae >= 0.0
    assert np.asarray(metricas.confusion).shape == (3, 3)
    assert sum(sum(linha) for linha in metricas.confusion) == metricas.n_examples
    assert metricas.n_examples == 75


def test_erro_ordinal_penaliza_confusao_entre_extremos():
    X, y = dataset_sintetico(n_por_classe=25, ruido=0.08)
    modelo = TrackModel()
    modelo.fit(X, y)

    assert modelo.metrics_.ordinal_mae < 0.5


def test_modo_de_baixa_confianca_com_poucos_exemplos():
    X, y = dataset_sintetico(n_por_classe=3)
    modelo = TrackModel()
    modelo.fit(X, y, min_examples=15)

    assert modelo.low_confidence_mode is True
    assert max(p.confidence for p in modelo.predict(X)) <= 0.5


def test_dataset_grande_nao_entra_em_baixa_confianca():
    X, y = dataset_sintetico(n_por_classe=25)
    modelo = TrackModel()
    modelo.fit(X, y, min_examples=15)

    assert modelo.low_confidence_mode is False


def test_calibracao_sobrevive_ao_ciclo_de_persistencia(tmp_path):
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)
    destino = tmp_path / "modelo.joblib"
    modelo.save(destino)

    recarregado = TrackModel.load(destino)

    assert recarregado.thresholds_ == modelo.thresholds_
    assert recarregado.metrics_.accuracy == pytest.approx(modelo.metrics_.accuracy)
