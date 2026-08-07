"""Ponto de entrada (ui/__main__.main): achado Important da revisao final --
nenhum teste exercitava o main() que este branch inteiro mexeu (reordenou
QApplication antes de load_config, adicionou o gate de FirstRunDialog).

QApplication real e MainWindow real sao substituidas por dublês: Qt so
aceita uma QApplication por processo, e a suite inteira ja sobe uma via a
fixture `qapp` de outros arquivos de teste que rodam no mesmo processo --
chamar o construtor de novo dentro de main() derrubaria a suite com
"Please destroy the QApplication singleton before creating a new
QApplication instance." em vez de testar o que queremos. Substituir
QApplication e MainWindow por dublês tambem evita rodar app.exec() de
verdade, que travaria o teste num loop de eventos sem fim.
"""

from PySide6.QtWidgets import QDialog

import trackclassifier.ui.__main__ as entrypoint
from trackclassifier.config import Config, ConfigError
from trackclassifier.labels import Label


class _AppFalso:
    """Dublê de QApplication: so precisa aceitar setStyleSheet/exec."""

    def __init__(self, argv):
        self.argv = argv

    def setStyleSheet(self, _texto):
        pass

    def exec(self):
        return 0


class _JanelaFalsa:
    """Dublê de MainWindow: prova que foi construida sem abrir nenhum
    QMainWindow de verdade nem tocar TrackService."""

    ultima = None

    def __init__(self, servico, config_path=None, bundle=None, atualizacoes=None):
        self.servico = servico
        self.config_path = config_path
        self.bundle = bundle
        self.atualizacoes = atualizacoes
        _JanelaFalsa.ultima = self

    def show(self):
        pass


def _dialogo_falso(resultado, config=None):
    """Fabrica uma FirstRunDialog dublê presa a `resultado`
    (QDialog.DialogCode.Accepted/Rejected). Guarda toda instancia criada em
    `.instancias`, para o teste provar que o dialogo foi de fato construido
    (equivalente a "mostrado": exec() e como QDialog abre modal)."""

    class _Dialogo:
        instancias: list["_Dialogo"] = []

        def __init__(self, caminho, escolher_pasta=None, parent=None):
            self.caminho = caminho
            self.config = config
            type(self).instancias.append(self)

        def exec(self):
            return resultado

    return _Dialogo


def _config_valido(tmp_path):
    for nome in ("up", "neutral", "down", "inbox", "data"):
        (tmp_path / nome).mkdir()
    return Config(
        folders={
            Label.UP: tmp_path / "up",
            Label.NEUTRAL: tmp_path / "neutral",
            Label.DOWN: tmp_path / "down",
        },
        inbox=tmp_path / "inbox",
        data_dir=tmp_path / "data",
        retrain_every=10,
        min_examples=15,
    )


def _patch_qt_e_janela(monkeypatch):
    monkeypatch.setattr(entrypoint, "QApplication", _AppFalso)
    monkeypatch.setattr(entrypoint, "MainWindow", _JanelaFalsa)
    _JanelaFalsa.ultima = None


def test_config_ausente_abre_o_dialogo_de_primeira_execucao(monkeypatch, tmp_path):
    _patch_qt_e_janela(monkeypatch)
    caminho = tmp_path / "config.toml"
    Dialogo = _dialogo_falso(QDialog.DialogCode.Rejected)
    monkeypatch.setattr(entrypoint, "FirstRunDialog", Dialogo)

    entrypoint.main(str(caminho))

    assert [d.caminho for d in Dialogo.instancias] == [caminho]


def test_dialogo_aceito_constroi_a_janela_principal(monkeypatch, tmp_path):
    _patch_qt_e_janela(monkeypatch)
    caminho = tmp_path / "config.toml"
    config = _config_valido(tmp_path)
    monkeypatch.setattr(
        entrypoint, "FirstRunDialog", _dialogo_falso(QDialog.DialogCode.Accepted, config)
    )

    codigo = entrypoint.main(str(caminho))

    assert codigo == 0
    assert _JanelaFalsa.ultima is not None
    assert _JanelaFalsa.ultima.config_path == caminho
    assert _JanelaFalsa.ultima.servico.config is config


def test_dialogo_cancelado_nao_constroi_janela_e_devolve_zero(monkeypatch, tmp_path):
    _patch_qt_e_janela(monkeypatch)
    caminho = tmp_path / "config.toml"
    monkeypatch.setattr(
        entrypoint, "FirstRunDialog", _dialogo_falso(QDialog.DialogCode.Rejected)
    )

    codigo = entrypoint.main(str(caminho))

    assert codigo == 0
    assert _JanelaFalsa.ultima is None


def test_config_valido_em_disco_pula_o_dialogo(monkeypatch, tmp_path):
    """Quando ja ha config utilizavel, main() nao deve nem construir o
    dialogo -- so a janela principal direto."""
    from trackclassifier.config import save_config

    _patch_qt_e_janela(monkeypatch)
    caminho = tmp_path / "config.toml"
    save_config(caminho, _config_valido(tmp_path))
    Dialogo = _dialogo_falso(QDialog.DialogCode.Rejected)
    monkeypatch.setattr(entrypoint, "FirstRunDialog", Dialogo)

    codigo = entrypoint.main(str(caminho))

    assert Dialogo.instancias == []
    assert _JanelaFalsa.ultima is not None
    assert codigo == 0


def test_qapplication_e_criada_antes_de_tentar_carregar_o_config(monkeypatch, tmp_path):
    """Regressao dedicada da ordem: antes da correcao que este branch trouxe,
    load_config rodava ANTES de existir QApplication, e um ConfigError
    abortava o programa cedo demais para o erro virar algo alem de stderr.
    """
    ordem = []

    class _AppOrdem(_AppFalso):
        def __init__(self, argv):
            ordem.append("app")
            super().__init__(argv)

    def _load_config_espiao(_caminho):
        ordem.append("load_config")
        raise ConfigError("sem config para este teste")

    monkeypatch.setattr(entrypoint, "QApplication", _AppOrdem)
    monkeypatch.setattr(entrypoint, "MainWindow", _JanelaFalsa)
    monkeypatch.setattr(entrypoint, "load_config", _load_config_espiao)
    monkeypatch.setattr(
        entrypoint, "FirstRunDialog", _dialogo_falso(QDialog.DialogCode.Rejected)
    )
    _JanelaFalsa.ultima = None

    entrypoint.main(str(tmp_path / "config.toml"))

    assert ordem == ["app", "load_config"]
