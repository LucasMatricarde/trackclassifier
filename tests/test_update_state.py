"""updates.json: ultima checagem e versao dispensada."""

import os

import pytest

from trackclassifier.update_state import EstadoDeAtualizacao


def test_sem_arquivo_deve_checar(tmp_path):
    estado = EstadoDeAtualizacao(tmp_path / "updates.json", agora=lambda: 1000.0)

    assert estado.deve_checar()


def test_depois_de_marcar_nao_checa_de_novo_no_mesmo_dia(tmp_path):
    relogio = {"t": 1000.0}
    estado = EstadoDeAtualizacao(tmp_path / "updates.json", agora=lambda: relogio["t"])
    estado.marca_checagem()

    relogio["t"] = 1000.0 + 3600

    assert not estado.deve_checar()


def test_checa_de_novo_passado_o_intervalo(tmp_path):
    relogio = {"t": 1000.0}
    estado = EstadoDeAtualizacao(tmp_path / "updates.json", agora=lambda: relogio["t"])
    estado.marca_checagem()

    relogio["t"] = 1000.0 + 25 * 3600

    assert estado.deve_checar()


def test_marca_checagem_sobrevive_a_uma_instancia_nova(tmp_path):
    caminho = tmp_path / "updates.json"
    EstadoDeAtualizacao(caminho, agora=lambda: 1000.0).marca_checagem()

    outro = EstadoDeAtualizacao(caminho, agora=lambda: 1000.0 + 60)

    assert not outro.deve_checar()


def test_versao_dispensada_nao_volta_a_aparecer(tmp_path):
    estado = EstadoDeAtualizacao(tmp_path / "updates.json", agora=lambda: 1000.0)

    estado.dispensa("0.3.0")

    assert estado.esta_dispensada("0.3.0")


def test_dispensar_uma_versao_nao_dispensa_a_seguinte(tmp_path):
    estado = EstadoDeAtualizacao(tmp_path / "updates.json", agora=lambda: 1000.0)
    estado.dispensa("0.3.0")

    assert not estado.esta_dispensada("0.4.0")


def test_json_quebrado_e_tratado_como_nunca_checou(tmp_path):
    """Degrada para checar. Um arquivo de controle corrompido nao pode
    virar mensagem de erro sobre algo que o usuario nao pediu."""
    caminho = tmp_path / "updates.json"
    caminho.write_text("{ isto nao e json")

    estado = EstadoDeAtualizacao(caminho, agora=lambda: 1000.0)

    assert estado.deve_checar()
    assert not estado.esta_dispensada("0.3.0")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignora permissao de diretorio")
def test_diretorio_sem_permissao_nao_derruba_a_gravacao(tmp_path):
    """Nao poder gravar o controle nao pode impedir o app de abrir."""
    pasta = tmp_path / "somente-leitura"
    pasta.mkdir()
    pasta.chmod(0o555)
    try:
        estado = EstadoDeAtualizacao(pasta / "updates.json", agora=lambda: 1000.0)
        estado.marca_checagem()
    finally:
        pasta.chmod(0o755)
