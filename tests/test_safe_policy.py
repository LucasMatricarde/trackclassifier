from pathlib import Path

from trackclassifier.labels import Label
from trackclassifier.safe_policy import AutomationState, SafetyPolicyStore


def test_classe_so_libera_depois_dos_gates_offline_e_sombra(tmp_path):
    store = SafetyPolicyStore(tmp_path / "policy.sqlite3", evidence_version="v1")
    store.record_offline(Label.UP, correct=30, eligible=30, threshold=0.91)
    assert store.state_for(Label.UP).state is AutomationState.SHADOW

    for indice in range(99):
        store.record_shadow(Label.UP, correct=indice < 96)
    assert store.state_for(Label.UP).state is AutomationState.SHADOW

    store.record_shadow(Label.UP, correct=True)
    estado = store.state_for(Label.UP)
    assert estado.state is AutomationState.RELEASED
    assert estado.shadow_correct == 97
    assert estado.shadow_total == 100


def test_gates_sao_independentes_por_classe(tmp_path):
    store = SafetyPolicyStore(tmp_path / "policy.sqlite3", evidence_version="v1")
    store.record_offline(Label.DOWN, correct=30, eligible=30, threshold=0.9)

    assert store.state_for(Label.DOWN).state is AutomationState.SHADOW
    assert store.state_for(Label.NEUTRAL).state is AutomationState.MANUAL
    assert store.state_for(Label.UP).state is AutomationState.MANUAL


def test_janela_movel_suspende_classe_abaixo_de_97_por_cento(tmp_path):
    store = SafetyPolicyStore(tmp_path / "policy.sqlite3", evidence_version="v1")
    store.record_offline(Label.UP, correct=30, eligible=30, threshold=0.9)
    for _ in range(100):
        store.record_shadow(Label.UP, correct=True)
    assert store.state_for(Label.UP).state is AutomationState.RELEASED

    for indice in range(100):
        store.record_audit(Label.UP, correct=indice < 96)

    estado = store.state_for(Label.UP)
    assert estado.state is AutomationState.SUSPENDED
    assert estado.recent_precision == 0.96


def test_mudar_versao_da_evidencia_ignora_historico_anterior(tmp_path):
    caminho = tmp_path / "policy.sqlite3"
    antiga = SafetyPolicyStore(caminho, evidence_version="v1")
    antiga.record_offline(Label.UP, correct=30, eligible=30, threshold=0.9)

    nova = SafetyPolicyStore(caminho, evidence_version="v2")
    assert nova.state_for(Label.UP).state is AutomationState.MANUAL


def test_movimento_pendente_nao_e_exemplo_humano_ate_confirmacao(tmp_path):
    store = SafetyPolicyStore(tmp_path / "policy.sqlite3", evidence_version="v1")
    store.begin_move(
        batch_id="batch-1",
        sha1="abc",
        source=Path("/inbox/a.mp3"),
        destination=Path("/up/a.mp3"),
        label=Label.UP,
        model_version="model-1",
        probability=0.99,
    )
    store.complete_move("batch-1", "abc", Path("/up/a.mp3"))

    assert store.pending_auto_sha1s() == {"abc"}
    store.confirm_auto_label("abc")
    assert store.pending_auto_sha1s() == set()
    assert store.is_human_labeled("abc") is True
