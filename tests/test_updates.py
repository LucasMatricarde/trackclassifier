"""updates.py: descoberta de versao nova. Nenhum teste toca a rede."""

import hashlib
import io
import json
import os
import plistlib
from pathlib import Path

import pytest

from trackclassifier.updates import (
    Release,
    UpdateError,
    baixa,
    busca_ultimo_release,
    caminho_do_bundle,
    ha_versao_nova,
    instala,
    relanca,
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


def test_busca_levanta_update_error_quando_o_corpo_e_uma_lista():
    """JSON valido mas nao-objeto (lista, string, null) nao pode vazar AttributeError."""
    with pytest.raises(UpdateError):
        busca_ultimo_release(abrir=_resposta(b"[]"))


def test_busca_levanta_update_error_quando_o_corpo_e_null():
    with pytest.raises(UpdateError):
        busca_ultimo_release(abrir=_resposta(b"null"))


def test_busca_ignora_assets_que_nao_sao_objetos():
    """Asset fora do formato esperado (numero, string...) e pulado, nao derruba a busca."""
    assets = [
        1,
        2,
        {"name": "app.zip", "browser_download_url": "https://z/app.zip"},
        {"name": "app.zip.sha256", "browser_download_url": "https://z/s"},
    ]

    release = busca_ultimo_release(abrir=_resposta(_json_de_release(assets=assets)))

    assert release.url_zip == "https://z/app.zip"
    assert release.url_sha256 == "https://z/s"


def _release(url_zip="https://z/app.zip", url_sha256="https://z/s"):
    return Release(
        version="0.3.0",
        url_zip=url_zip,
        url_sha256=url_sha256,
        notas="",
        recomputa=frozenset(),
    )


def _abridor(conteudo: bytes, checksum: str):
    """Fake que devolve o checksum numa URL e o zip na outra."""

    def _abrir(url, timeout=10.0):
        if url == "https://z/s":
            # Formato do shasum: "<hex>  <nome do arquivo>".
            return io.BytesIO(f"{checksum}  TrackClassifier-0.3.0.zip\n".encode())
        return io.BytesIO(conteudo)

    return _abrir


def test_baixa_grava_o_arquivo_quando_o_checksum_bate(tmp_path):
    conteudo = b"conteudo do zip"
    certo = hashlib.sha256(conteudo).hexdigest()
    destino = tmp_path / "app.zip"

    resultado = baixa(_release(), destino, abrir=_abridor(conteudo, certo))

    assert resultado == destino
    assert destino.read_bytes() == conteudo


def test_baixa_recusa_e_apaga_quando_o_checksum_diverge(tmp_path):
    """Zip truncado que virasse bundle e pior que nao atualizar."""
    destino = tmp_path / "app.zip"

    with pytest.raises(UpdateError, match="corrompido"):
        baixa(_release(), destino, abrir=_abridor(b"zip", "0" * 64))

    assert not destino.exists()


def test_baixa_reporta_progresso(tmp_path):
    conteudo = b"x" * 5000
    certo = hashlib.sha256(conteudo).hexdigest()
    vistos = []

    baixa(
        _release(),
        tmp_path / "app.zip",
        abrir=_abridor(conteudo, certo),
        progresso=lambda feito, total: vistos.append(feito),
    )

    assert vistos and vistos[-1] == 5000


def test_baixa_levanta_update_error_quando_a_rede_cai(tmp_path):
    def _explode(url, timeout=10.0):
        raise OSError("conexao perdida")

    with pytest.raises(UpdateError):
        baixa(_release(), tmp_path / "app.zip", abrir=_explode)


def test_baixa_levanta_update_error_quando_nao_consegue_criar_a_pasta(tmp_path):
    """Pai que e um arquivo, nao uma pasta -- mkdir explode com NotADirectoryError."""
    conteudo = b"conteudo do zip"
    certo = hashlib.sha256(conteudo).hexdigest()
    (tmp_path / "nao-e-pasta").write_text("x")
    destino = tmp_path / "nao-e-pasta" / "app.zip"

    with pytest.raises(UpdateError):
        baixa(_release(), destino, abrir=_abridor(conteudo, certo))


def _monta_app(raiz: Path, nome: str, versao: str) -> Path:
    """Arvore minima que instala() aceita como .app valido."""
    app = raiz / nome
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True)
    executavel = macos / "TrackClassifier"
    executavel.write_text("#!/bin/sh\n")
    executavel.chmod(0o755)
    plist = app / "Contents" / "Info.plist"
    with plist.open("wb") as saida:
        plistlib.dump({"CFBundleShortVersionString": versao}, saida)
    return app


def _extrator(versao: str, nome: str = "TrackClassifier.app"):
    """Fake de ditto: escreve um .app pronto no diretorio pedido.

    ditto nao existe no Linux do CI -- por isso instala() recebe o extrator.
    """

    def _extrai(zip_baixado: Path, para: Path) -> None:
        para.mkdir(parents=True, exist_ok=True)
        _monta_app(para, nome, versao)

    return _extrai


def test_instala_substitui_o_bundle(tmp_path):
    bundle = _monta_app(tmp_path, "TrackClassifier.app", "0.2.0")

    instala(tmp_path / "novo.zip", bundle, "0.3.0", extrair=_extrator("0.3.0"))

    with (bundle / "Contents" / "Info.plist").open("rb") as entrada:
        assert plistlib.load(entrada)["CFBundleShortVersionString"] == "0.3.0"


def test_instala_deixa_o_bundle_antigo_para_limpeza_futura(tmp_path):
    """Achado #4 da revisao final: apagar `.old` na hora arrisca deletar
    arquivos de que o processo em execucao ainda depende (interpretador,
    plugins do Qt etc. nao mmapeados ainda). `instala()` agora deixa o
    `.old` no disco apos um sucesso -- ele so e limpo no INICIO da proxima
    chamada a `instala()`, quando o processo antigo ja terminou fazem
    tempo. Ver `test_instala_limpa_old_orfao_de_execucao_anterior`.
    """
    bundle = _monta_app(tmp_path, "TrackClassifier.app", "0.2.0")

    instala(tmp_path / "novo.zip", bundle, "0.3.0", extrair=_extrator("0.3.0"))

    assert (tmp_path / "TrackClassifier.app.old").exists()


def test_instala_limpa_old_orfao_de_execucao_anterior(tmp_path):
    """Um `.old` deixado por uma instalacao anterior (o comportamento novo,
    ver o teste acima) nao pode colidir com o primeiro os.rename() da
    proxima instalacao -- ele precisa ser limpo automaticamente antes das
    renomeacoes, sem exigir nenhuma acao do usuario.
    """
    bundle = _monta_app(tmp_path, "TrackClassifier.app", "0.2.0")
    orfao = tmp_path / "TrackClassifier.app.old"
    orfao.mkdir()
    (orfao / "lixo-de-uma-instalacao-anterior.txt").write_text("sobra")

    instala(tmp_path / "novo.zip", bundle, "0.3.0", extrair=_extrator("0.3.0"))

    with (bundle / "Contents" / "Info.plist").open("rb") as entrada:
        assert plistlib.load(entrada)["CFBundleShortVersionString"] == "0.3.0"
    # O orfao foi substituido pelo `.old` desta instalacao (o 0.2.0 que
    # acabou de ser trocado), nao pelo lixo da execucao anterior.
    assert not (orfao / "lixo-de-uma-instalacao-anterior.txt").exists()


def test_instala_nao_toca_no_data_dir(tmp_path):
    """O requisito central: nenhuma analise ja feita pode ser perdida."""
    bundle = _monta_app(tmp_path, "TrackClassifier.app", "0.2.0")
    data_dir = tmp_path / ".trackclassifier"
    data_dir.mkdir()
    arquivos = {
        "analyses.parquet": b"features de 4000 tracks",
        "sha1.json": b'{"a": "b"}',
        "presentation.parquet": b"capas e tonalidades",
        "model.joblib": b"modelo treinado",
    }
    for nome, conteudo in arquivos.items():
        (data_dir / nome).write_bytes(conteudo)
    antes = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in data_dir.iterdir()}

    instala(tmp_path / "novo.zip", bundle, "0.3.0", extrair=_extrator("0.3.0"))

    depois = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in data_dir.iterdir()}
    assert depois == antes


def test_instala_recusa_zip_sem_app_dentro(tmp_path):
    bundle = _monta_app(tmp_path, "TrackClassifier.app", "0.2.0")

    def _extrai_lixo(zip_baixado, para):
        para.mkdir(parents=True, exist_ok=True)
        (para / "leiame.txt").write_text("nao sou um app")

    with pytest.raises(UpdateError):
        instala(tmp_path / "novo.zip", bundle, "0.3.0", extrair=_extrai_lixo)

    with (bundle / "Contents" / "Info.plist").open("rb") as entrada:
        assert plistlib.load(entrada)["CFBundleShortVersionString"] == "0.2.0"


def test_instala_recusa_bundle_com_versao_diferente_da_anunciada(tmp_path):
    """Release diz 0.3.0 mas o binario se identifica 0.2.9: nao instala.

    Instalar mesmo assim faria a proxima checagem reoferecer a mesma versao
    para sempre, num laco que o usuario nao consegue sair.
    """
    bundle = _monta_app(tmp_path, "TrackClassifier.app", "0.2.0")

    with pytest.raises(UpdateError):
        instala(tmp_path / "novo.zip", bundle, "0.3.0", extrair=_extrator("0.2.9"))


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignora permissao de diretorio")
def test_instala_recusa_quando_nao_da_para_escrever_no_pai(tmp_path):
    pai = tmp_path / "Applications"
    pai.mkdir()
    bundle = _monta_app(pai, "TrackClassifier.app", "0.2.0")
    pai.chmod(0o555)
    try:
        with pytest.raises(UpdateError, match=str(pai)):
            instala(tmp_path / "novo.zip", bundle, "0.3.0", extrair=_extrator("0.3.0"))
    finally:
        pai.chmod(0o755)


def test_instala_levanta_update_error_quando_falha_ao_mover_bundle_para_old(tmp_path, monkeypatch):
    """os.rename(bundle, antigo) fora de qualquer try/except vazava OSError cru.

    Cenario real: um instala() anterior morreu (kill, queda de energia) entre
    as duas renomeacoes e nunca chegou no rmtree final, deixando `antigo` nao
    vazio. A proxima tentativa bate em OSError ao tentar renomear por cima.
    """
    bundle = _monta_app(tmp_path, "TrackClassifier.app", "0.2.0")

    def _rename_que_falha(origem, destino):
        raise OSError(39, "Directory not empty")

    monkeypatch.setattr(os, "rename", _rename_que_falha)

    with pytest.raises(UpdateError):
        instala(tmp_path / "novo.zip", bundle, "0.3.0", extrair=_extrator("0.3.0"))


def test_instala_levanta_update_error_quando_falha_ao_instalar_e_ao_restaurar(
    tmp_path, monkeypatch
):
    """Duplo fracasso: rename(novo, bundle) falha, e a tentativa de desfazer

    (rename(antigo, bundle)) tambem falha. Antes desta correcao o OSError da
    restauracao vazava cru e escondia o `raise UpdateError` original -- e o
    usuario ficava sem indicacao de que o app antigo esta em `antigo`.
    """
    bundle = _monta_app(tmp_path, "TrackClassifier.app", "0.2.0")
    real_rename = os.rename
    chamadas = {"n": 0}

    def _rename_seletivo(origem, destino):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            # a primeira chamada (bundle -> antigo) precisa funcionar de
            # verdade para o cenario chegar ate a segunda renomeacao.
            real_rename(origem, destino)
            return
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(os, "rename", _rename_seletivo)

    antigo = bundle.with_name(bundle.name + ".old")
    with pytest.raises(UpdateError, match=str(antigo)):
        instala(tmp_path / "novo.zip", bundle, "0.3.0", extrair=_extrator("0.3.0"))


def test_relanca_chama_open_com_o_bundle(tmp_path):
    chamadas = []

    relanca(tmp_path / "TrackClassifier.app", executar=chamadas.append)

    assert chamadas == [["/usr/bin/open", "-n", str(tmp_path / "TrackClassifier.app")]]


def test_caminho_do_bundle_sobe_ate_o_app(tmp_path):
    executavel = tmp_path / "TrackClassifier.app" / "Contents" / "MacOS" / "TrackClassifier"

    achado = caminho_do_bundle(executavel=executavel, empacotado=True)

    assert achado == tmp_path / "TrackClassifier.app"


def test_caminho_do_bundle_e_none_fora_do_bundle(tmp_path):
    """Em `uv run dj review` nao ha .app: o update nem aparece."""
    assert caminho_do_bundle(executavel=tmp_path / "python", empacotado=False) is None


def test_caminho_do_bundle_e_none_se_empacotado_mas_sem_app_no_caminho(tmp_path):
    assert caminho_do_bundle(executavel=tmp_path / "bin" / "x", empacotado=True) is None
