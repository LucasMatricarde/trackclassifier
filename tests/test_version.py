"""A versao mora num lugar so: src/trackclassifier/__init__.py."""

import re
from importlib.metadata import version as versao_instalada
from pathlib import Path

import trackclassifier

RAIZ = Path(__file__).resolve().parents[1]


def test_version_e_semver_de_tres_partes():
    assert re.fullmatch(r"\d+\.\d+\.\d+", trackclassifier.__version__)


def test_metadado_do_pacote_vem_do_dunder_version():
    """Prova que o dynamic version do hatchling esta ligado no __init__.

    Sem isto, `pip show trackclassifier` e o __version__ podem divergir e
    ninguem percebe ate o updater comparar contra o numero errado.
    """
    assert versao_instalada("trackclassifier") == trackclassifier.__version__


def test_spec_do_pyinstaller_nao_tem_versao_literal():
    """CFBundleShortVersionString tem que sair de __version__.

    Um literal aqui e o bug que quebra o updater para sempre: o app se
    identifica com uma versao, o release anuncia outra, e a comparacao passa
    a mentir em toda checagem.
    """
    texto = (RAIZ / "packaging" / "trackclassifier.spec").read_text(encoding="utf-8")
    assert not re.search(r'"CFBundleShortVersionString":\s*"\d', texto)
    assert "__version__" in texto
