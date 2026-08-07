"""updates.py: descoberta de versao nova. Nenhum teste toca a rede."""

import io
import json

import pytest

from trackclassifier.updates import (
    UpdateError,
    busca_ultimo_release,
    ha_versao_nova,
    versao_como_tupla,
)


def _resposta(corpo: bytes):
    """Fake de urlopen: devolve um BytesIO usavel como context manager."""

    def _abrir(url, timeout=10.0):
        return io.BytesIO(corpo)

    return _abrir


def _json_de_release(tag="v0.3.0", corpo="", assets=None):
    if assets is None:
        assets = [
            {"name": "TrackClassifier-0.3.0.zip", "browser_download_url": "https://z/app.zip"},
            {"name": "TrackClassifier-0.3.0.zip.sha256", "browser_download_url": "https://z/s"},
        ]
    return json.dumps({"tag_name": tag, "body": corpo, "assets": assets}).encode()


def test_versao_como_tupla_converte_tres_partes():
    assert versao_como_tupla("0.3.1") == (0, 3, 1)


def test_versao_como_tupla_devolve_none_no_ilegivel():
    assert versao_como_tupla("beta-de-sexta") is None


def test_ha_versao_nova_compara_como_numero_nao_como_texto():
    """0.10.0 > 0.9.0 -- comparacao de string diria o contrario."""
    assert ha_versao_nova("0.9.0", "0.10.0")
    assert not ha_versao_nova("0.10.0", "0.9.0")


def test_ha_versao_nova_e_falso_na_mesma_versao():
    assert not ha_versao_nova("0.2.0", "0.2.0")


def test_ha_versao_nova_e_falso_com_candidata_ilegivel():
    assert not ha_versao_nova("0.2.0", "nightly")


def test_busca_le_tag_url_e_notas():
    release = busca_ultimo_release(abrir=_resposta(_json_de_release(corpo="notas aqui")))

    assert release.version == "0.3.0"
    assert release.url_zip == "https://z/app.zip"
    assert release.url_sha256 == "https://z/s"
    assert release.notas == "notas aqui"


def test_busca_extrai_a_linha_recompute_do_corpo():
    corpo = "Mudancas\n\nrecompute: features, presentation\n"

    release = busca_ultimo_release(abrir=_resposta(_json_de_release(corpo=corpo)))

    assert release.recomputa == frozenset({"features", "presentation"})


def test_busca_sem_linha_recompute_devolve_conjunto_vazio():
    release = busca_ultimo_release(abrir=_resposta(_json_de_release(corpo="so notas")))

    assert release.recomputa == frozenset()


def test_busca_devolve_none_quando_falta_o_asset_do_checksum():
    """Release sem .sha256 nao da para verificar -- equivale a nao ter update."""
    assets = [{"name": "app.zip", "browser_download_url": "https://z/app.zip"}]

    assert busca_ultimo_release(abrir=_resposta(_json_de_release(assets=assets))) is None


def test_busca_devolve_none_com_tag_ilegivel():
    assert busca_ultimo_release(abrir=_resposta(_json_de_release(tag="nightly"))) is None


def test_busca_levanta_update_error_com_json_quebrado():
    with pytest.raises(UpdateError):
        busca_ultimo_release(abrir=_resposta(b"<html>rate limited</html>"))


def test_busca_levanta_update_error_quando_a_conexao_falha():
    def _explode(url, timeout=10.0):
        raise OSError("nome nao resolve")

    with pytest.raises(UpdateError):
        busca_ultimo_release(abrir=_explode)
