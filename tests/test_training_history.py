import os
import time
from pathlib import Path

import numpy as np
import pytest

from trackclassifier.config import Config
from trackclassifier.features import TrackAnalysis
from trackclassifier.labels import Label
from trackclassifier.model import TrackModel, per_class_metrics, weighted_f1
from trackclassifier.service import TrackService
from trackclassifier.training_history import (
    TrainingEntry,
    append,
    era_de,
    load,
    next_version,
)
from trackclassifier.ui.viewmodel import model_state

# ---------------------------------------------------------------------------
# Helpers de calculo (model.py)
# ---------------------------------------------------------------------------

#: Matriz de teste: reais nas linhas [12, 22, 9], previstos nas colunas
#: [11, 23, 9]. Composta para ter classe com previstos de mais fora da
#: diagonal e para produzir floats faceis de conferir.
CONFUSAO_TESTE = [[10, 2, 0], [1, 20, 1], [0, 1, 8]]


class TestPerClass:
    def test_precisao_recall_f1_por_classe(self):
        p0, r0, f10 = per_class_metrics(CONFUSAO_TESTE)[0]
        assert p0 == pytest.approx(10 / 11)
        assert r0 == pytest.approx(10 / 12)
        assert f10 == pytest.approx(
            2 * (10 / 11) * (10 / 12) / ((10 / 11) + (10 / 12))
        )

    def test_classe_nunca_prevista_gera_f1_zero(self):
        # Coluna 2 zerada: o modelo nunca previu a classe. Zero-division do
        # sklearn: precisao 0 e F1 0 -- um erro honesto do modelo, nao uma
        # barra ausente.
        confusao = [[10, 2, 0], [1, 20, 0], [0, 1, 0]]
        p2, _, f12 = per_class_metrics(confusao)[2]
        assert (p2, f12) == (0.0, 0.0)

    def test_classe_sem_reais_tem_recall_zero(self):
        # Linha 2 zerada: a classe nao existe no conjunto (o fit real exige
        # exemplos das tres, mas a funcao e defensiva). Zero-division: 0.
        confusao = [[10, 2, 0], [1, 20, 1], [0, 0, 0]]
        _, r2, _ = per_class_metrics(confusao)[2]
        assert r2 == 0.0

    def test_confusao_vazia_tem_f1_ponderado_zero(self):
        assert weighted_f1([[0, 0, 0], [0, 0, 0], [0, 0, 0]]) == 0.0


class TestWeightedF1:
    def test_usa_suporte_real_e_o_estimador_do_sklearn(self):
        por_classe = per_class_metrics(CONFUSAO_TESTE)
        reais = [sum(linha) for linha in CONFUSAO_TESTE]
        esperado = (
            sum(f1 * suporte for (_, _, f1), suporte in zip(por_classe, reais, strict=True))
            / sum(reais)
        )
        assert weighted_f1(CONFUSAO_TESTE) == pytest.approx(esperado)

    def test_erros_graduam_o_ponderado(self):
        # Uma confusion perfeita contra uma em que o modelo ignora os
        # exemplos de +1: o suporte da classe continua no denominador, o
        # F1 dela vira 0 -- a media nao finge perfeicao.
        perfeita = [[10, 0, 0], [0, 20, 0], [0, 0, 8]]
        ignora_plus = [[10, 0, 0], [0, 20, 0], [0, 8, 0]]
        assert weighted_f1(ignora_plus) < weighted_f1(perfeita)


# ---------------------------------------------------------------------------
# Historico (training_history.py)
# ---------------------------------------------------------------------------


class TestNextVersion:
    def test_primeiro_treino_da_era(self):
        assert next_version([], "handcrafted-v2") == "v2.0.0"

    def test_segundo_treino_da_era_incrementa_minor(self):
        entrada = TrainingEntry(
            ts="2026-01-01T00:00:00",
            extractor="handcrafted-v2",
            version="v2.0.0",
            n_examples=10,
            accuracy=1.0,
            ordinal_mae=0.0,
            weighted_f1=1.0,
        )
        assert next_version([entrada], "handcrafted-v2") == "v2.1.0"

    def test_era_de_outro_extrator_no_historico_nao_conta(self):
        entrada = TrainingEntry(
            ts="2026-01-01T00:00:00",
            extractor="handcrafted-v1",
            version="v1.0.0",
            n_examples=10,
            accuracy=1.0,
            ordinal_mae=0.0,
            weighted_f1=1.0,
        )
        assert next_version([entrada], "handcrafted-v2") == "v2.0.0"

    def test_extrator_sem_sufixo_trava_na_era_1(self):
        assert era_de("extrator-qualquer") == 1


class TestAppend:
    def test_entrada_nova_e_a_ultima_e_load_devolve_em_ordem(self, tmp_path):
        caminho = tmp_path / "data" / "model_history.json"
        append(
            caminho,
            TrainingEntry("2026-01-01T00:00:00", "handcrafted-v2", "v2.0.0", 10, 0.5, 0.1, 0.4),
        )
        append(
            caminho,
            TrainingEntry("2026-01-02T00:00:00", "handcrafted-v2", "v2.1.0", 11, 0.6, 0.1, 0.5),
        )
        entradas = load(caminho)
        assert [e.ts for e in entradas] == ["2026-01-01T00:00:00", "2026-01-02T00:00:00"]
        assert entradas[-1].version == "v2.1.0"

    def test_cap_mantem_os_mais_recentes(self, tmp_path):
        caminho = tmp_path / "model_history.json"
        for i in range(52):
            append(
                caminho,
                TrainingEntry(
                    f"2026-01-01T{i:02d}:00:00",
                    "handcrafted-v2",
                    f"v2.{i}.0",
                    10,
                    0.5,
                    0.1,
                    0.4,
                ),
            )
        entradas = load(caminho)
        assert len(entradas) == 50
        # Os dois primeiros saem; o cap nunca desloca a versao de quem fica.
        assert entradas[0].version == "v2.2.0"
        assert entradas[-1].version == "v2.51.0"
        assert not caminho.with_suffix(".json.tmp").exists()

    def test_arquivo_corrompido_vira_lista_vazia_nao_crash(self, tmp_path):
        caminho = tmp_path / "model_history.json"
        caminho.write_text("{ nao sou json")
        assert load(caminho) == []

    def test_arquivo_inexistente_vira_lista_vazia(self, tmp_path):
        assert load(tmp_path / "nada.json") == []


# ---------------------------------------------------------------------------
# Integracao no servico (backfill, train, history/deltas)
# ---------------------------------------------------------------------------


class ExtratorSimples:
    """Vetor derivado do nome, derivacao barata e deterministica."""

    name = "falso-v1"

    def extract(self, path: Path) -> TrackAnalysis:
        energia = float(path.stem.split("_")[-1])
        vetor = np.zeros(44, dtype=np.float64)
        vetor[0] = energia
        return TrackAnalysis(
            vector=vetor,
            energy_curve=[energia] * 6,
            peak_offset_s=12.0,
            bpm=128.0,
            duration_s=300.0,
        )


def _config(tmp_path) -> Config:
    pastas = {}
    for chave, rotulo in (("down", Label.DOWN), ("neutral", Label.NEUTRAL), ("up", Label.UP)):
        destino = tmp_path / chave
        destino.mkdir()
        pastas[rotulo] = destino
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    return Config.from_folders(
        folders=pastas, inbox=inbox, data_dir=data, retrain_every=10, min_examples=5
    )


def _povoa(config: Config) -> None:
    for rotulo, energia in ((Label.DOWN, 0.0), (Label.NEUTRAL, 0.5), (Label.UP, 1.0)):
        for i in range(6):
            valor = energia + i * 0.001
            (config.folders[rotulo] / f"t{i}_{valor:.3f}.mp3").write_bytes(
                f"{rotulo.value}{i}".encode()
            )


def _model_artigo(destino, n_por_classe=4) -> TrackModel:
    """Treina um TrackModel de verdade e grava o joblib em destino/model.joblib."""
    X = np.asarray(
        [[0.9]] * n_por_classe + [[0.5]] * n_por_classe + [[0.1]] * n_por_classe,
        dtype=np.float64,
    )
    rotulos = (
        [Label.UP] * n_por_classe
        + [Label.NEUTRAL] * n_por_classe
        + [Label.DOWN] * n_por_classe
    )
    model = TrackModel()
    model.fit(X, rotulos, min_examples=1)
    model.save(destino)
    return model


class TestBackfill:
    def test_modelo_antigo_sem_historico_ganha_entrada_com_mtime(self, tmp_path):
        config = _config(tmp_path)
        model = _model_artigo(config.data_dir / "model.joblib")
        stamp = os.stat(config.data_dir / "model.joblib").st_mtime

        servico = TrackService(config)
        entradas = servico.historico_treinos()
        assert len(entradas) == 1
        (entrada,) = entradas
        assert entrada.ts == time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stamp))
        assert entrada.n_examples == model.n_examples_
        assert entrada.extractor == servico.extractor.name
        assert entrada.accuracy == pytest.approx(model.metrics_.accuracy)

    def test_historico_presente_nao_ganha_backfill(self, tmp_path):
        config = _config(tmp_path)
        _model_artigo(config.data_dir / "model.joblib")
        append(
            config.data_dir / "model_history.json",
            TrainingEntry(
                "2099-01-01T00:00:00", "handcrafted-v2", "v2.0.0", 5, 0.5, 0.1, 0.4
            ),
        )
        servico = TrackService(config)
        entradas = servico.historico_treinos()
        assert len(entradas) == 1
        assert entradas[0].ts == "2099-01-01T00:00:00"

    def test_sem_modelo_nao_ha_entrada(self, tmp_path):
        config = _config(tmp_path)
        servico = TrackService(config)
        assert servico.historico_treinos() == []


class TestModelStateTreinado:
    """model_state com treino real: version, history, per_class, deltas."""

    def _servico(self, config: Config) -> TrackService:
        servico = TrackService(config, extractor=ExtratorSimples(), max_workers=1)
        servico.analyze_all()
        return servico

    def test_primeiro_treino_tem_version_e_sem_delta(self, tmp_path):
        config = _config(tmp_path)
        _povoa(config)
        servico = self._servico(config)
        servico.train()
        state = model_state(servico)
        assert state.version == "v1.0.0"  # o ExtratorSimples vive na era 1
        assert state.deltas == ()
        assert state.per_class is not None
        assert len(state.per_class) == 3
        assert state.last_trained_at is not None

    def test_retreino_na_mesma_era_gera_deltas_e_minor(self, tmp_path):
        config = _config(tmp_path)
        _povoa(config)
        servico = self._servico(config)
        servico.train()
        servico.train()
        state = model_state(servico)
        assert state.version == "v1.1.0"
        assert len(state.history) == 2
        assert state.history[0][1] == "v1.1.0"  # recente primeiro
        assert dict(state.deltas) != {}
        # delta de accuracy e a diferenca literal entre as entradas
        _, anterior = servico.historico_treinos()
        assert dict(state.deltas)["accuracy"] == pytest.approx(
            servico.historico_treinos()[-1].accuracy - anterior.accuracy
        )

    def test_history_recentes_primeiro_e_ate_12(self, tmp_path):
        config = _config(tmp_path)
        _povoa(config)
        servico = self._servico(config)
        for _ in range(14):
            servico.train()
        state = model_state(servico)
        assert len(state.history) == 12
        # 14 treinos, cap de exibicao em 12: v1.13.0 esta na frente, v1.2.0
        # na ultima linha (o corte derruba v1.0 e v1.1).
        assert state.history[0][1] == "v1.13.0"
        assert state.history[-1][1] == "v1.2.0"

    def test_sem_treino_nao_versiona_ou_deltas(self, tmp_path):
        config = _config(tmp_path)
        servico = TrackService(config)
        state = model_state(servico)
        assert state.version is None
        assert state.deltas == ()
        assert state.per_class is None
