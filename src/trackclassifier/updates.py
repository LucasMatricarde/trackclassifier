"""Descoberta e instalacao de versao nova do .app.

Sem Qt e sem estado de proposito: a camada Qt (ui/update_worker.py) so leva
estas funcoes para fora da thread da GUI, e o estado de "quando foi a ultima
checagem" mora em update_state.py. Assim cada parte tem um teste que nao
precisa de janela nem de disco.

Toda borda de sistema -- rede, ditto, open -- entra por parametro com um
default real. Nao e cerimonia de teste: a suite roda em Linux no CI, onde
ditto e open nao existem, e sem injecao nada aqui seria testavel la.
"""

import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from . import __version__

URL_LATEST = (
    "https://api.github.com/repos/LucasMatricarde/trackclassifier/releases/latest"
)
_TIMEOUT_PADRAO = 10.0


class UpdateError(Exception):
    """Qualquer falha do caminho de atualizacao. A unica que sai do modulo."""


@dataclass(frozen=True)
class Release:
    version: str
    url_zip: str
    url_sha256: str
    notas: str
    #: O que esta versao invalida ("features", "presentation"). Vazio quando
    #: o corpo do release nao declara nada.
    recomputa: frozenset[str]


def _abre(url: str, timeout: float = _TIMEOUT_PADRAO):
    """urlopen com User-Agent. A API do GitHub recusa pedido sem ele."""
    pedido = Request(url, headers={"User-Agent": f"trackclassifier/{__version__}"})
    return urlopen(pedido, timeout=timeout)


def versao_como_tupla(versao: str) -> tuple[int, ...] | None:
    """(maior, menor, patch), ou None se o texto nao for X.Y.Z.

    Nao usa `packaging.version` porque isso seria uma dependencia nova de
    runtime dentro do bundle para comparar tres inteiros.
    """
    partes = versao.lstrip("v").split(".")
    if len(partes) != 3:
        return None
    try:
        return tuple(int(parte) for parte in partes)
    except ValueError:
        return None


def ha_versao_nova(atual: str, candidata: str) -> bool:
    """Compara como numero, nao como texto: "0.10.0" > "0.9.0"."""
    a = versao_como_tupla(atual)
    b = versao_como_tupla(candidata)
    if a is None or b is None:
        return False
    return b > a


def _recomputa_do_corpo(corpo: str) -> frozenset[str]:
    """Le a linha `recompute: features, presentation` do corpo do release.

    Tolerante de proposito: o corpo e texto escrito a mao no momento de
    publicar, e um espaco a mais nao pode virar aviso perdido.
    """
    for linha in corpo.splitlines():
        limpa = linha.strip()
        if not limpa.lower().startswith("recompute:"):
            continue
        valores = limpa.split(":", 1)[1]
        return frozenset(
            item.strip().lower() for item in valores.split(",") if item.strip()
        )
    return frozenset()


def _url_do_asset(assets: list[dict], sufixo: str) -> str | None:
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        nome = asset.get("name", "")
        if nome.endswith(sufixo):
            return asset.get("browser_download_url")
    return None


def busca_ultimo_release(
    abrir: Callable = _abre, url: str = URL_LATEST
) -> Release | None:
    """O release mais recente, ou None quando nao ha um utilizavel.

    None e "nao ha update", nao "deu erro": tag ilegivel ou release sem o
    .sha256 sao releases que este app nao sabe instalar, e tratar isso como
    erro encheria a tela de mensagem por algo que o usuario nao pode
    resolver. Erro de verdade -- rede caida, resposta que nao e JSON -- sobe
    como UpdateError.
    """
    try:
        with abrir(url, timeout=_TIMEOUT_PADRAO) as resposta:
            dados = json.loads(resposta.read())
        if not isinstance(dados, dict):
            # JSON valido mas de outro formato (lista, string, null...) -- a API
            # do GitHub nao devolve isso, mas rate-limit e proxy as vezes
            # respondem com corpo inesperado. Sem essa checagem o `.get` la
            # embaixo levantaria AttributeError e vazaria do modulo.
            raise TypeError(f"resposta da API nao e um objeto JSON: {type(dados).__name__}")
    except UpdateError:
        raise
    except Exception as erro:
        raise UpdateError(f"Nao foi possivel verificar atualizacoes: {erro}") from erro

    versao = str(dados.get("tag_name", "")).lstrip("v")
    if versao_como_tupla(versao) is None:
        return None

    assets = dados.get("assets") or []
    url_sha256 = _url_do_asset(assets, ".sha256")
    url_zip = _url_do_asset(assets, ".zip")
    if not url_zip or not url_sha256:
        return None

    corpo = str(dados.get("body") or "")
    return Release(
        version=versao,
        url_zip=url_zip,
        url_sha256=url_sha256,
        notas=corpo,
        recomputa=_recomputa_do_corpo(corpo),
    )


def _apaga_se_existir(caminho: Path) -> None:
    """unlink(missing_ok=True) so engole FileNotFoundError -- se o pai nunca
    virou pasta de verdade (ex.: mkdir falhou porque um arquivo ocupa o
    nome), o proprio unlink explode com NotADirectoryError. Limpeza de melhor
    esforco nao pode ser a causa de um segundo erro mascarando o primeiro.
    """
    try:
        caminho.unlink(missing_ok=True)
    except OSError:
        pass


_CHUNK = 256 * 1024


def _le_checksum(url: str, abrir: Callable) -> str:
    """O hex do arquivo .sha256 gerado por `shasum -a 256`.

    O formato e "<hex>  <nome>", entao o primeiro campo e tudo que interessa.
    """
    try:
        with abrir(url, timeout=_TIMEOUT_PADRAO) as resposta:
            texto = resposta.read().decode("utf-8", "replace")
    except Exception as erro:
        raise UpdateError(f"Nao foi possivel ler o checksum: {erro}") from erro
    campos = texto.split()
    if not campos:
        raise UpdateError("Arquivo de checksum vazio.")
    return campos[0].strip().lower()


def baixa(
    release: Release,
    destino: Path,
    abrir: Callable = _abre,
    progresso: Callable[[int, int], None] | None = None,
) -> Path:
    """Baixa o zip do release para `destino`, so devolvendo se o hash bater.

    A verificacao acontece com o arquivo ja no disco (e nao em memoria) para
    o download de centenas de MB nao precisar caber na RAM junto com a
    janela, o modelo e o parquet carregados.
    """
    esperado = _le_checksum(release.url_sha256, abrir)
    digest = hashlib.sha256()
    baixados = 0

    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with abrir(release.url_zip, timeout=_TIMEOUT_PADRAO) as resposta:
            total = int(getattr(resposta, "headers", {}).get("Content-Length", 0) or 0)
            with destino.open("wb") as saida:
                while True:
                    bloco = resposta.read(_CHUNK)
                    if not bloco:
                        break
                    saida.write(bloco)
                    digest.update(bloco)
                    baixados += len(bloco)
                    if progresso is not None:
                        progresso(baixados, total)
    except Exception as erro:
        _apaga_se_existir(destino)
        raise UpdateError(f"Falha ao baixar a atualizacao: {erro}") from erro

    if digest.hexdigest() != esperado:
        # Apagar e obrigatorio, nao higiene: um zip parcial deixado no disco
        # seria candidato a ser instalado por uma tentativa seguinte que so
        # visse "o arquivo ja existe".
        _apaga_se_existir(destino)
        raise UpdateError("Download corrompido: o checksum nao confere.")

    return destino


_NOME_EXECUTAVEL = "TrackClassifier"


def _extrai_com_ditto(zip_baixado: Path, para: Path) -> None:
    """ditto, e nao zipfile: o bundle do Qt e cheio de symlink.

    O modulo zipfile da stdlib nao restaura symlink -- ele grava o alvo como
    arquivo comum. Um Frameworks/ do Qt desempacotado assim vira centenas de
    MB duplicados e um app que nao abre. ditto e a ferramenta que o proprio
    macOS usa para isso.
    """
    para.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["/usr/bin/ditto", "-x", "-k", str(zip_baixado), str(para)],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as erro:
        raise UpdateError(f"Falha ao descompactar a atualizacao: {erro}") from erro


def _app_dentro(diretorio: Path) -> Path | None:
    for candidato in sorted(diretorio.iterdir()):
        if candidato.is_dir() and candidato.name.endswith(".app"):
            return candidato
    return None


def _valida_bundle(app: Path, versao_esperada: str) -> None:
    executavel = app / "Contents" / "MacOS" / _NOME_EXECUTAVEL
    if not executavel.is_file() or not os.access(executavel, os.X_OK):
        raise UpdateError("O pacote baixado nao tem o executavel esperado.")

    plist = app / "Contents" / "Info.plist"
    try:
        with plist.open("rb") as entrada:
            versao = plistlib.load(entrada).get("CFBundleShortVersionString")
    except Exception as erro:
        raise UpdateError(f"O pacote baixado tem Info.plist ilegivel: {erro}") from erro

    if versao != versao_esperada:
        raise UpdateError(
            f"O pacote se identifica como {versao}, mas o release anuncia "
            f"{versao_esperada}. Atualizacao cancelada."
        )


def instala(
    zip_baixado: Path,
    bundle: Path,
    versao_esperada: str,
    extrair: Callable[[Path, Path], None] = _extrai_com_ditto,
) -> None:
    """Troca `bundle` pelo .app de dentro do zip. Nao toca em mais nada.

    O temporario e criado no MESMO diretorio do bundle porque os dois
    os.rename abaixo so sao atomicos dentro de um volume: com o temporario em
    /tmp (que pode ser outro volume), o rename viraria copia nao-atomica e
    uma queda de energia no meio deixaria meio app no lugar do app inteiro.

    Nenhuma linha desta funcao abre config.toml ou qualquer coisa dentro do
    data_dir -- e o que garante que analise, cache e modelo sobrevivem ao
    update. Ha teste afirmando isso byte a byte.
    """
    pai = bundle.parent
    if not os.access(pai, os.W_OK):
        raise UpdateError(
            f"Sem permissao de escrita em {pai}. Mova o app para uma pasta sua "
            "(por exemplo ~/Applications) e tente de novo."
        )

    temporario = Path(tempfile.mkdtemp(prefix=".trackclassifier-update-", dir=pai))
    antigo = bundle.with_name(bundle.name + ".old")
    try:
        extrair(zip_baixado, temporario)
        novo = _app_dentro(temporario)
        if novo is None:
            raise UpdateError("O arquivo baixado nao contem um .app.")
        _valida_bundle(novo, versao_esperada)

        try:
            os.rename(bundle, antigo)
        except OSError as erro:
            raise UpdateError(f"Falha ao instalar a atualizacao: {erro}") from erro

        try:
            os.rename(novo, bundle)
        except OSError as erro:
            # Desfaz: sem isto o usuario ficaria sem nenhum app no lugar
            # esperado, e o Dock apontaria para um caminho que nao existe. Mas a
            # propria restauracao pode falhar (mesmo motivo que fez o rename
            # acima falhar, tipicamente); nesse caso o app so existe em
            # `antigo`, entao a mensagem precisa apontar para la em vez de
            # deixar o OSError da restauracao vazar cru e esconder a causa
            # original.
            try:
                os.rename(antigo, bundle)
            except OSError as erro_restauracao:
                raise UpdateError(
                    f"Falha ao instalar a atualizacao ({erro}) e tambem falhou "
                    f"ao restaurar o app anterior ({erro_restauracao}). O app "
                    f"antigo esta em {antigo} -- mova-o de volta para {bundle} "
                    "manualmente."
                ) from erro_restauracao
            raise UpdateError(f"Falha ao instalar a atualizacao: {erro}") from erro

        shutil.rmtree(antigo, ignore_errors=True)
    finally:
        shutil.rmtree(temporario, ignore_errors=True)


def relanca(bundle: Path, executar: Callable = subprocess.Popen) -> None:
    """Abre a versao nova num processo solto; o chamador fecha a janela.

    `open -n` e nao exec do executavel: e o LaunchServices que registra o app
    corretamente no Dock e no switcher, e um exec direto do binario dentro do
    bundle deixaria o app sem identidade para o macOS.
    """
    executar(["/usr/bin/open", "-n", str(bundle)])


def caminho_do_bundle(
    executavel: Path | None = None, empacotado: bool | None = None
) -> Path | None:
    """O .app que esta rodando, ou None fora dele.

    None e a resposta em desenvolvimento (`uv run dj review`), e e o que faz
    o menu de atualizacao nao existir ali: nao ha bundle para trocar, e
    baixar um release por cima de um checkout seria destruir trabalho.
    """
    if empacotado is None:
        empacotado = bool(getattr(sys, "frozen", False))
    if not empacotado:
        return None

    caminho = Path(executavel if executavel is not None else sys.executable)
    for pai in caminho.parents:
        if pai.name.endswith(".app"):
            return pai
    return None
