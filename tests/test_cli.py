import re
from pathlib import Path

import pytest

from tests.test_service import ExtratorFalso, _config, _povoa
from trackclassifier import cli
from trackclassifier.cli import main


@pytest.fixture(autouse=True)
def usa_extrator_falso(monkeypatch):
    monkeypatch.setattr("trackclassifier.service.HandcraftedExtractor", ExtratorFalso)


def _escreve_config_toml(tmp_path, config):
    caminho = tmp_path / "config.toml"
    caminho.write_text(
        f"""
[folders]
up = "{config.folders_up}"
neutral = "{config.folders_neutral}"
down = "{config.folders_down}"
inbox = "{config.inbox}"

[model]
retrain_every = 10
min_examples = 1

[paths]
data_dir = "{config.data_dir}"
""",
        encoding="utf-8",
    )
    return caminho


class _Atalho:
    """Adapta o Config de teste para o formato esperado pelo TOML."""

    def __init__(self, config):
        from trackclassifier.labels import Label

        self.folders_up = config.folders[Label.UP]
        self.folders_neutral = config.folders[Label.NEUTRAL]
        self.folders_down = config.folders[Label.DOWN]
        self.inbox = config.inbox
        self.data_dir = config.data_dir


def test_scan_termina_com_sucesso(tmp_path, capsys):
    config = _config(tmp_path)
    _povoa(config)
    caminho = _escreve_config_toml(tmp_path, _Atalho(config))

    codigo = main(["scan", "--config", str(caminho)])
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "analisadas" in saida.lower()
    # _servico() constroi o TrackService de verdade (sem max_workers
    # explicito), entao este teste e a unica cobertura ponta a ponta de
    # pool + save periodico + impressao de progresso do CLI juntos. Confirma
    # que ao menos uma linha "[N/total] nome" foi de fato impressa, em vez de
    # so confiar que o processo nao explodiu.
    assert re.search(r"^\[\d+/\d+\] .+", saida, re.MULTILINE) is not None


def test_train_imprime_metricas(tmp_path, capsys):
    config = _config(tmp_path)
    _povoa(config)
    caminho = _escreve_config_toml(tmp_path, _Atalho(config))

    codigo = main(["train", "--config", str(caminho)])
    saida = capsys.readouterr().out.lower()

    assert codigo == 0
    assert "acuracia" in saida
    assert "erro ordinal" in saida
    assert "matriz de confusao" in saida


def test_train_sem_uma_classe_falha_com_mensagem_clara(tmp_path, capsys):
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    _povoa(config)
    for arquivo in config.folders[Label.UP].iterdir():
        arquivo.unlink()
    caminho = _escreve_config_toml(tmp_path, _Atalho(config))

    codigo = main(["train", "--config", str(caminho)])

    assert codigo == 1
    assert "+1" in capsys.readouterr().err


def test_config_inexistente_falha_com_mensagem_clara(tmp_path, capsys):
    codigo = main(["scan", "--config", str(tmp_path / "nao_existe.toml")])

    assert codigo == 1
    assert "configuracao" in capsys.readouterr().err.lower()


def test_caminho_config_padrao_e_relativo_ao_cwd_fora_do_pacote(monkeypatch):
    monkeypatch.delattr(cli.sys, "frozen", raising=False)

    assert cli._caminho_config_padrao() == Path("config.toml")


def test_caminho_config_padrao_e_fixo_no_home_quando_empacotado(monkeypatch):
    # Empacotado (clique duplo no .app) nao tem cwd previsivel -- o Finder
    # pode abrir de qualquer lugar, entao o default nao pode depender dele.
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)

    assert cli._caminho_config_padrao() == Path.home() / ".trackclassifier" / "config.toml"


def test_argv_vazio_empacotado_abre_a_janela_de_revisao(monkeypatch, tmp_path):
    # Clique duplo no .app invoca o executavel sem argumentos -- sem o
    # fallback pra "review" em main(), argparse (subcomando required=True)
    # sairia com erro antes de a janela sequer tentar abrir.
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli.sys, "argv", ["TrackClassifier"])
    monkeypatch.setattr(cli, "_caminho_config_padrao", lambda: tmp_path / "config.toml")
    chamadas = []
    monkeypatch.setattr(
        "trackclassifier.ui.__main__.main", lambda caminho: chamadas.append(caminho) or 0
    )

    codigo = cli.main()

    assert codigo == 0
    assert chamadas == [str(tmp_path / "config.toml")]
