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


def test_argv_vazio_empacotado_sobe_o_serve(monkeypatch, tmp_path):
    # Clique duplo no .app invoca o executavel sem argumentos -- sem o
    # fallback pra "serve" em main(), argparse (subcomando required=True)
    # sairia com erro antes de o servidor sequer tentar subir.
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli.sys, "argv", ["TrackClassifier"])
    monkeypatch.setattr(cli, "_caminho_config_padrao", lambda: tmp_path / "config.toml")
    chamadas = []
    monkeypatch.setattr(
        "trackclassifier.serve.run_server",
        lambda caminho, **kwargs: chamadas.append((caminho, kwargs)),
    )

    codigo = cli.main()

    assert codigo == 0
    assert chamadas == [
        (
            str(tmp_path / "config.toml"),
            {"host": "127.0.0.1", "port": 8765, "open_browser": True},
        )
    ]


def test_review_nao_e_mais_subcomando(capsys):
    with pytest.raises(SystemExit):
        main(["review"])

    assert "review" in capsys.readouterr().err


# --- dj keys: tonalidade por audio em lote ------------------------------------


def _com_triades(config):
    """Duas triades decodificaveis (La menor e Do maior) em pastas rotuladas."""
    from tests.test_key_batch import _triade, _triade_do_maior, _triade_la_menor
    from trackclassifier.labels import Label

    _triade_la_menor(config.folders[Label.UP] / "am_0.500.wav")
    _triade_do_maior(config.folders[Label.DOWN] / "c_0.100.wav")
    _triade(config.folders[Label.NEUTRAL] / "am2_0.300.wav", (220.0, 261.63, 329.63), duracao=5.0)


def _presentation(config):
    from trackclassifier.presentation import PresentationCache

    return PresentationCache(config.data_dir / "presentation.parquet", config.data_dir / "covers")


def _servico_relido(config):
    from trackclassifier.service import TrackService

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()
    return servico


def test_keys_detecta_e_grava_pelo_audio(tmp_path, capsys):
    config = _config(tmp_path)
    _com_triades(config)
    caminho = _escreve_config_toml(tmp_path, _Atalho(config))

    codigo = main(["keys", "--config", str(caminho)])
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "3 detectada(s)" in saida
    # Progresso do lote no terminal, alem do progresso do scan que o precede.
    assert saida.count("] am_0.500.wav") >= 2
    # Instancia nova: o que vale e o que foi para o disco.
    servico = _servico_relido(config)
    camelots = {r.path.name: servico.key_for(r.sha1).camelot for r in servico._labeled}
    assert camelots == {"am_0.500.wav": "8A", "am2_0.300.wav": "8A", "c_0.100.wav": "8B"}
    assert {servico.key_source_for(r.sha1) for r in servico._labeled} == {"audio"}


def test_keys_rodado_duas_vezes_nao_refaz_nada(tmp_path, capsys):
    config = _config(tmp_path)
    _com_triades(config)
    caminho = _escreve_config_toml(tmp_path, _Atalho(config))
    main(["keys", "--config", str(caminho)])
    capsys.readouterr()

    codigo = main(["keys", "--config", str(caminho)])

    assert codigo == 0
    assert "0 detectada(s), 0 sem resultado, 3 pulada(s)" in capsys.readouterr().out


def test_keys_calibrar_imprime_a_tabela_e_nao_grava_nada(tmp_path, capsys):
    import hashlib

    from trackclassifier.keys import Key, Mode

    config = _config(tmp_path)
    _com_triades(config)
    caminho = _escreve_config_toml(tmp_path, _Atalho(config))
    assert main(["scan", "--config", str(caminho)]) == 0
    # Gabarito semeado a mao: uma tag igual a estimativa (La menor), uma
    # relativa dela (a triade de Do maior estimada contra uma tag 8A) e uma
    # longe de tudo (Fa# maior).
    servico = _servico_relido(config)
    por_nome = {r.path.name: r.sha1 for r in servico._labeled}
    apresentacao = _presentation(config)
    apresentacao.set_key(por_nome["am_0.500.wav"], Key(9, Mode.MINOR), "tag")  # exato
    apresentacao.set_key(por_nome["c_0.100.wav"], Key(9, Mode.MINOR), "tag")  # relativa
    apresentacao.set_key(por_nome["am2_0.300.wav"], Key(6, Mode.MAJOR), "tag")  # errada
    apresentacao.save()
    parquet = config.data_dir / "presentation.parquet"
    antes = hashlib.sha1(parquet.read_bytes()).hexdigest()
    capsys.readouterr()

    codigo = main(["keys", "--calibrar", "--config", str(caminho)])
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "Calibracao da tonalidade (nada foi gravado)" in saida
    assert "Tracks com tag de key:     3" in saida
    assert "Comparadas contra a tag:   3" in saida
    assert "Acerto exato:" in saida and "    1   33.3%" in saida
    assert "Acerto vizinho:" in saida and "    2   66.7%" in saida
    assert "Sem resultado (none):          0    0.0%" in saida
    assert hashlib.sha1(parquet.read_bytes()).hexdigest() == antes


def test_keys_calibrar_sem_nenhuma_tag_avisa_em_vez_de_dividir_por_zero(tmp_path, capsys):
    config = _config(tmp_path)
    _com_triades(config)
    caminho = _escreve_config_toml(tmp_path, _Atalho(config))

    codigo = main(["keys", "--calibrar", "--config", str(caminho)])

    assert codigo == 0
    assert "Nenhuma track comparada." in capsys.readouterr().out


def test_ctrl_c_no_keys_cancela_cooperativamente_e_salva_o_parcial(tmp_path, capsys):
    import os
    import signal

    from tests.test_key_batch import _detector_fixo
    from trackclassifier.keys import Key, Mode
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    _povoa(config, n_por_classe=3)  # 9 alvos
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()
    base = _detector_fixo(Key(9, Mode.MINOR))

    def _detector_que_recebe_ctrl_c(path):
        resultado = base(path)
        if len(base.chamadas) == 3:
            os.kill(os.getpid(), signal.SIGINT)  # o terminal mandaria isto no Ctrl-C
        return resultado

    servico._detector_de_key = _detector_que_recebe_ctrl_c
    handler_antes = signal.getsignal(signal.SIGINT)

    codigo = cli._executa_keys(servico, calibrar=False)
    saida = capsys.readouterr().out

    assert codigo == 130
    assert "Cancelando" in saida
    assert "o parcial foi salvo e 6 track(s) seguem pendentes" in saida
    assert signal.getsignal(signal.SIGINT) is handler_antes
    gravadas = [r for r in servico._labeled if _presentation(config).get(r.sha1).key is not None]
    assert len(gravadas) == 3
