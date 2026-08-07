# Atualizacao in-app — plano de implementacao

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao `.app` empacotado um item de menu e uma faixa que descobrem e instalam versao nova, sem tocar em nada dentro do `data_dir`.

**Architecture:** Tres camadas independentes. `updates.py` (sem Qt, sem estado) fala com a API do GitHub, baixa, verifica SHA-256 e troca o bundle por rename atomico. `update_state.py` (sem Qt) guarda quando foi a ultima checagem e qual versao foi dispensada. `ui/update_worker.py` + `ui/update_banner.py` levam isso para a janela sobre `QThreadPool`, espelhando `ContadorEmSegundoPlano`. Um workflow do GitHub Actions produz o artefato que o cliente consome.

**Tech Stack:** Python 3.11+, stdlib apenas (`urllib`, `hashlib`, `plistlib`, `subprocess`, `json`), PySide6, PyInstaller, GitHub Actions (`macos-latest`).

**Spec:** `docs/superpowers/specs/2026-08-07-atualizacao-in-app-design.md`

## Global Constraints

- Python `>=3.11,<3.14`. **Nenhuma dependencia nova** — tudo em `updates.py` e `update_state.py` sai da stdlib.
- ruff: `line-length = 100`, regras `E,F,I,UP,B`. Gate do CI.
- **Portugues sem acentos** em nomes de variaveis locais, funcoes internas, comentarios, docstrings, mensagens de erro e nomes de teste. API publica (dataclasses, metodos de classe, campos JSON) em ingles.
- Comentarios explicam **por que**, nao o que.
- Nenhum literal hex fora de `design/design-tokens.json` — `tests/test_tokens.py::test_nenhum_hex_fora_do_json` varre `src/trackclassifier/ui/**.py`. Cor vem de `ui/tokens.py`.
- `ui/viewmodel.py` **nao importa Qt** — ha teste que falha se importar.
- So a thread do `ServiceWorker` fala com `TrackService`. Nenhum codigo deste plano chama o servico.
- Erro numa borda **degrada e reporta**; nunca derruba a janela.
- Testes rodam em `ubuntu-latest` no CI: **nenhum teste pode chamar `ditto`, `open` ou a rede**. Toda borda de sistema e injetavel.
- Commits: conventional commits com escopo (`feat(trackclassifier):`, `feat(ci):`).

**Desvio consciente da spec:** a spec mostra `ultima_checagem` como string ISO. O plano grava **epoch float**. Comparar dois floats nao tem modo de errar; parsear ISO tem. O arquivo e lido so pela maquina.

## Estrutura de arquivos

| Arquivo | Responsabilidade |
| --- | --- |
| `src/trackclassifier/__init__.py` (modificar) | `__version__` — fonte unica de verdade |
| `src/trackclassifier/updates.py` (criar) | busca, download, verificacao, troca do bundle. Sem Qt, sem estado |
| `src/trackclassifier/update_state.py` (criar) | `updates.json`: ultima checagem e versao dispensada |
| `src/trackclassifier/ui/update_worker.py` (criar) | leva `updates.py` para fora da thread da GUI |
| `src/trackclassifier/ui/update_banner.py` (criar) | faixa no topo da janela |
| `src/trackclassifier/ui/viewmodel.py` (modificar) | `texto_de_atualizacao()` — copy do dialogo, testavel sem Qt |
| `src/trackclassifier/ui/window.py` (modificar) | menu, faixa, dialogo, relance |
| `src/trackclassifier/ui/__main__.py` (modificar) | monta bundle + estado e injeta na janela |
| `packaging/trackclassifier.spec` (modificar) | le `__version__` |
| `pyproject.toml` (modificar) | `dynamic = ["version"]` |
| `.github/workflows/release.yml` (criar) | build + zip + checksum + release na tag |
| `README.md` (modificar) | secao de release, correcao da nota de custo de CI |

---

### Task 1: Versao com fonte unica

**Files:**
- Modify: `src/trackclassifier/__init__.py`
- Modify: `pyproject.toml:4`
- Modify: `packaging/trackclassifier.spec:91`
- Test: `tests/test_version.py`

**Interfaces:**
- Consumes: nada.
- Produces: `trackclassifier.__version__: str` — usado por toda task seguinte.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_version.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_version.py -v
```

Esperado: FAIL — `AttributeError: module 'trackclassifier' has no attribute '__version__'`.

- [ ] **Step 3: Escrever `__version__`**

`src/trackclassifier/__init__.py` (hoje vazio) passa a conter apenas:

```python
"""Fonte unica da versao.

Tudo que precisa saber a versao le daqui: o metadado do pacote (via
`dynamic = ["version"]` no pyproject), o CFBundleShortVersionString do
bundle (via packaging/trackclassifier.spec) e a comparacao do updater. O
modulo fica sem import nenhum de proposito -- o spec do PyInstaller importa
este pacote antes de existir ambiente montado, e qualquer import pesado aqui
quebraria o build.
"""

__version__ = "0.2.0"
```

- [ ] **Step 4: Ligar o pyproject**

Em `pyproject.toml`, trocar a linha `version = "0.1.0"` por:

```toml
dynamic = ["version"]
```

E acrescentar, depois do bloco `[tool.hatch.build.targets.wheel]`:

```toml
[tool.hatch.version]
path = "src/trackclassifier/__init__.py"
```

- [ ] **Step 5: Ligar o spec do PyInstaller**

Em `packaging/trackclassifier.spec`, logo apos `raiz = Path(SPECPATH).parent`, inserir:

```python
# Importa o pacote so para ler __version__. Cabe aqui porque
# trackclassifier/__init__.py nao importa nada -- se um dia importar, este
# import passa a arrastar numpy/librosa para dentro do processo que ANALISA
# o bundle, e o build fica lento sem motivo.
sys.path.insert(0, str(raiz / "src"))
from trackclassifier import __version__  # noqa: E402
```

Acrescentar `import sys` no topo do spec (junto de `import shutil`) e trocar
a linha 91 por:

```python
        "CFBundleShortVersionString": __version__,
```

- [ ] **Step 6: Reinstalar e rodar os testes**

```bash
uv sync --extra dev
```

```bash
uv run pytest tests/test_version.py -v
```

Esperado: 3 PASS.

- [ ] **Step 7: Confirmar que o spec ainda parseia**

```bash
uv run --extra build pyinstaller packaging/trackclassifier.spec --noconfirm
```

Esperado: build completa e `dist/TrackClassifier.app/Contents/Info.plist` traz `0.2.0`. Conferir:

```bash
plutil -extract CFBundleShortVersionString raw dist/TrackClassifier.app/Contents/Info.plist
```

- [ ] **Step 8: Commit**

```bash
git add src/trackclassifier/__init__.py pyproject.toml packaging/trackclassifier.spec tests/test_version.py
git commit -m "feat(trackclassifier): centraliza a versao em __version__"
```

---

### Task 2: `updates.py` — parse de versao e busca do release

**Files:**
- Create: `src/trackclassifier/updates.py`
- Test: `tests/test_updates.py`

**Interfaces:**
- Consumes: `trackclassifier.__version__` (Task 1).
- Produces:
  - `class UpdateError(Exception)`
  - `@dataclass(frozen=True) Release(version: str, url_zip: str, url_sha256: str, notas: str, recomputa: frozenset[str])`
  - `versao_como_tupla(versao: str) -> tuple[int, ...] | None`
  - `ha_versao_nova(atual: str, candidata: str) -> bool`
  - `busca_ultimo_release(abrir: Callable = _abre, url: str = URL_LATEST) -> Release | None`
  - `_abre(url: str, timeout: float = 10.0)` — assinatura que todo callable injetado tem que respeitar.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_updates.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_updates.py -v
```

Esperado: FAIL na coleta — `ModuleNotFoundError: No module named 'trackclassifier.updates'`.

- [ ] **Step 3: Escrever a implementacao minima**

Criar `src/trackclassifier/updates.py`:

```python
"""Descoberta e instalacao de versao nova do .app.

Sem Qt e sem estado de proposito: a camada Qt (ui/update_worker.py) so leva
estas funcoes para fora da thread da GUI, e o estado de "quando foi a ultima
checagem" mora em update_state.py. Assim cada parte tem um teste que nao
precisa de janela nem de disco.

Toda borda de sistema -- rede, ditto, open -- entra por parametro com um
default real. Nao e cerimonia de teste: a suite roda em Linux no CI, onde
ditto e open nao existem, e sem injecao nada aqui seria testavel la.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_updates.py -v
```

Esperado: 12 PASS.

**Atencao:** `_url_do_asset(assets, ".zip")` casa tambem com `.zip.sha256`? Nao — `.zip.sha256` nao termina em `.zip`. Mas a ordem importa: se o `.sha256` viesse primeiro na lista e o sufixo fosse `.zip`, ainda assim nao casaria. Confirmar com o teste `test_busca_le_tag_url_e_notas`, que ja poe os dois na lista.

- [ ] **Step 5: Lint**

```bash
uv run ruff check src/trackclassifier/updates.py tests/test_updates.py
```

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/updates.py tests/test_updates.py
git commit -m "feat(trackclassifier): descobre release novo pela API do GitHub"
```

---

### Task 3: `updates.py` — download com verificacao de SHA-256

**Files:**
- Modify: `src/trackclassifier/updates.py`
- Test: `tests/test_updates.py`

**Interfaces:**
- Consumes: `Release`, `UpdateError`, `_abre` (Task 2).
- Produces: `baixa(release: Release, destino: Path, abrir: Callable = _abre, progresso: Callable[[int, int], None] | None = None) -> Path`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_updates.py`:

```python
import hashlib

from trackclassifier.updates import Release, baixa


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_updates.py -k baixa -v
```

Esperado: FAIL — `ImportError: cannot import name 'baixa'`.

- [ ] **Step 3: Implementar `baixa`**

Acrescentar ao topo de `src/trackclassifier/updates.py`:

```python
import hashlib
from pathlib import Path
```

E o corpo, depois de `busca_ultimo_release`:

```python
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
    destino.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    baixados = 0

    try:
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
        destino.unlink(missing_ok=True)
        raise UpdateError(f"Falha ao baixar a atualizacao: {erro}") from erro

    if digest.hexdigest() != esperado:
        # Apagar e obrigatorio, nao higiene: um zip parcial deixado no disco
        # seria candidato a ser instalado por uma tentativa seguinte que so
        # visse "o arquivo ja existe".
        destino.unlink(missing_ok=True)
        raise UpdateError("Download corrompido: o checksum nao confere.")

    return destino
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_updates.py -v
```

Esperado: 16 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trackclassifier/updates.py tests/test_updates.py
git commit -m "feat(trackclassifier): baixa e verifica o zip do release"
```

---

### Task 4: `updates.py` — troca do bundle, relance e localizacao do .app

**Files:**
- Modify: `src/trackclassifier/updates.py`
- Test: `tests/test_updates.py`

**Interfaces:**
- Consumes: `UpdateError` (Task 2).
- Produces:
  - `instala(zip_baixado: Path, bundle: Path, versao_esperada: str, extrair: Callable[[Path, Path], None] = _extrai_com_ditto) -> None`
  - `relanca(bundle: Path, executar: Callable = subprocess.Popen) -> None`
  - `caminho_do_bundle(executavel: Path | None = None, empacotado: bool | None = None) -> Path | None`

Esta e a task que carrega o requisito central: **nada dentro de `data_dir` pode ser tocado**.

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_updates.py`:

```python
import os
import plistlib
from pathlib import Path

from trackclassifier.updates import caminho_do_bundle, instala, relanca


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


def test_instala_nao_deixa_sobra_do_bundle_antigo(tmp_path):
    bundle = _monta_app(tmp_path, "TrackClassifier.app", "0.2.0")

    instala(tmp_path / "novo.zip", bundle, "0.3.0", extrair=_extrator("0.3.0"))

    assert not (tmp_path / "TrackClassifier.app.old").exists()


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_updates.py -k "instala or relanca or caminho_do_bundle" -v
```

Esperado: FAIL — `ImportError: cannot import name 'instala'`.

- [ ] **Step 3: Implementar**

Acrescentar aos imports de `src/trackclassifier/updates.py`:

```python
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
```

E o corpo, ao final do arquivo:

```python
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

        os.rename(bundle, antigo)
        try:
            os.rename(novo, bundle)
        except OSError as erro:
            # Desfaz: sem isto o usuario ficaria sem nenhum app no lugar
            # esperado, e o Dock apontaria para um caminho que nao existe.
            os.rename(antigo, bundle)
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_updates.py -v
```

Esperado: 26 PASS.

- [ ] **Step 5: Lint e suite inteira**

```bash
uv run ruff check . && uv run pytest
```

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/updates.py tests/test_updates.py
git commit -m "feat(trackclassifier): troca o bundle por rename atomico sem tocar no data_dir"
```

---

### Task 5: `update_state.py` — quando checar e o que dispensar

**Files:**
- Create: `src/trackclassifier/update_state.py`
- Test: `tests/test_update_state.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `INTERVALO_PADRAO_S: float`
  - `class EstadoDeAtualizacao(path: Path, agora: Callable[[], float] = time.time)`
    - `deve_checar(intervalo_s: float = INTERVALO_PADRAO_S) -> bool`
    - `marca_checagem() -> None`
    - `dispensa(versao: str) -> None`
    - `esta_dispensada(versao: str) -> bool`

- [ ] **Step 1: Write the failing test**

Criar `tests/test_update_state.py`:

```python
"""updates.json: ultima checagem e versao dispensada."""

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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_update_state.py -v
```

Esperado: FAIL na coleta — `ModuleNotFoundError: No module named 'trackclassifier.update_state'`.

- [ ] **Step 3: Implementar**

Criar `src/trackclassifier/update_state.py`:

```python
"""Controle de quando checar atualizacao e do que ja foi dispensado.

Mora em data_dir/updates.json, junto do resto do estado do app. Guarda epoch
float e nao data ISO de proposito: comparar dois floats nao tem como errar, e
o arquivo e lido so pela maquina.

Nenhum metodo aqui levanta excecao. Este arquivo e controle acessorio -- se
ele estiver corrompido, ilegivel ou num diretorio sem permissao, o pior
resultado aceitavel e checar atualizacao uma vez a mais. Falhar a abertura do
app por causa dele nao e aceitavel.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path

#: Uma vez por dia. Mais frequente nao descobre nada (releases sao manuais) e
#: gasta requisicao do limite anonimo de 60/h da API do GitHub.
INTERVALO_PADRAO_S: float = 24 * 60 * 60


class EstadoDeAtualizacao:
    def __init__(self, path: Path, agora: Callable[[], float] = time.time) -> None:
        self.path = Path(path)
        # Injetavel para o teste nao precisar dormir 24h nem mexer no relogio
        # do sistema.
        self._agora = agora

    def _carrega(self) -> dict:
        try:
            dados = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def _grava(self, dados: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(dados), encoding="utf-8")
        except OSError:
            # Silencio proposital: ver a docstring do modulo.
            return

    def deve_checar(self, intervalo_s: float = INTERVALO_PADRAO_S) -> bool:
        ultima = self._carrega().get("ultima_checagem")
        if not isinstance(ultima, int | float):
            return True
        return (self._agora() - float(ultima)) >= intervalo_s

    def marca_checagem(self) -> None:
        dados = self._carrega()
        dados["ultima_checagem"] = self._agora()
        self._grava(dados)

    def dispensa(self, versao: str) -> None:
        dados = self._carrega()
        dados["versao_dispensada"] = versao
        self._grava(dados)

    def esta_dispensada(self, versao: str) -> bool:
        return self._carrega().get("versao_dispensada") == versao
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_update_state.py -v
```

Esperado: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trackclassifier/update_state.py tests/test_update_state.py
git commit -m "feat(trackclassifier): guarda ultima checagem e versao dispensada"
```

---

### Task 6: `ui/update_worker.py` — checagem e instalacao fora da thread da GUI

**Files:**
- Create: `src/trackclassifier/ui/update_worker.py`
- Test: `tests/test_update_worker.py`

**Interfaces:**
- Consumes: `Release`, `UpdateError`, `busca_ultimo_release`, `ha_versao_nova`, `baixa`, `instala` (Tasks 2–4); `trackclassifier.__version__` (Task 1).
- Produces:
  - `class VerificadorDeAtualizacao(QObject)` com `checar()`, `instalar(release: Release, bundle: Path)` e os sinais `disponivel(object)`, `sem_novidade()`, `falhou(str)`, `progresso(int, int)`, `instalado()`.

Espelha `ui/counts_worker.py` — mesma estrutura de `QRunnable` + contador de geracao + `except RuntimeError` no emit.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_update_worker.py`:

```python
"""VerificadorDeAtualizacao: rede e disco fora da thread da GUI."""

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QDeadlineTimer, QEventLoop

from trackclassifier.updates import Release, UpdateError
from trackclassifier.ui.update_worker import VerificadorDeAtualizacao


def _roda_ate(sinal, timeout_ms=2000):
    """Bombeia o loop de eventos ate o sinal disparar ou estourar o prazo.

    Mesmo motivo de tests/test_counts_worker.py: o resultado atravessa do
    QThreadPool de volta para a thread da GUI por conexao em fila.
    """
    loop = QEventLoop()
    recebido = {}

    def _marca(*args):
        recebido["args"] = args
        loop.quit()

    conexao = sinal.connect(_marca)
    prazo = QDeadlineTimer(timeout_ms)
    while "args" not in recebido and not prazo.hasExpired():
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    sinal.disconnect(conexao)
    return recebido.get("args")


def _release(versao="0.9.0"):
    return Release(
        version=versao,
        url_zip="https://z/app.zip",
        url_sha256="https://z/s",
        notas="notas",
        recomputa=frozenset({"features"}),
    )


def test_checar_emite_disponivel_com_versao_maior(qapp):
    verificador = VerificadorDeAtualizacao(
        versao_atual="0.1.0", buscar=lambda: _release("0.9.0")
    )

    verificador.checar()

    args = _roda_ate(verificador.disponivel)

    assert args[0].version == "0.9.0"


def test_checar_emite_sem_novidade_na_mesma_versao(qapp):
    verificador = VerificadorDeAtualizacao(
        versao_atual="0.9.0", buscar=lambda: _release("0.9.0")
    )

    verificador.checar()

    assert _roda_ate(verificador.sem_novidade) == ()


def test_checar_emite_sem_novidade_quando_nao_ha_release(qapp):
    verificador = VerificadorDeAtualizacao(versao_atual="0.1.0", buscar=lambda: None)

    verificador.checar()

    assert _roda_ate(verificador.sem_novidade) == ()


def test_checar_emite_falhou_com_a_mensagem_do_update_error(qapp):
    def _explode():
        raise UpdateError("Nao foi possivel verificar atualizacoes: rede caiu")

    verificador = VerificadorDeAtualizacao(versao_atual="0.1.0", buscar=_explode)

    verificador.checar()

    args = _roda_ate(verificador.falhou)

    assert "rede caiu" in args[0]


def test_excecao_inesperada_na_busca_vira_falhou_e_nao_derruba_a_thread(qapp):
    def _explode():
        raise RuntimeError("bug meu, nao do usuario")

    verificador = VerificadorDeAtualizacao(versao_atual="0.1.0", buscar=_explode)

    verificador.checar()

    assert _roda_ate(verificador.falhou) is not None


def test_so_a_checagem_mais_recente_emite(qapp):
    """Duas checagens em voo: a mais velha nao pode sobrescrever a nova."""
    import threading

    liberar = threading.Event()
    ordem = []

    def _buscar_lento():
        ordem.append("primeira")
        liberar.wait(timeout=2)
        return _release("0.3.0")

    def _buscar_rapido():
        ordem.append("segunda")
        return _release("0.4.0")

    verificador = VerificadorDeAtualizacao(versao_atual="0.1.0", buscar=_buscar_lento)
    verificador.checar()
    verificador.buscar = _buscar_rapido
    verificador.checar()

    recebidos = []
    verificador.disponivel.connect(lambda r: recebidos.append(r.version))

    prazo = QDeadlineTimer(2000)
    while len(recebidos) < 1 and not prazo.hasExpired():
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if "segunda" in ordem:
            liberar.set()

    assert recebidos == ["0.4.0"]


def test_instalar_emite_instalado_no_caminho_feliz(qapp, tmp_path):
    chamadas = []

    verificador = VerificadorDeAtualizacao(
        versao_atual="0.1.0",
        baixar=lambda release, destino, progresso=None: destino,
        instalar=lambda zip_baixado, bundle, versao: chamadas.append(versao),
    )

    verificador.instalar_release(_release("0.9.0"), tmp_path / "TrackClassifier.app")

    assert _roda_ate(verificador.instalado) == ()
    assert chamadas == ["0.9.0"]


def test_instalar_emite_falhou_quando_o_checksum_nao_bate(qapp, tmp_path):
    def _baixar_ruim(release, destino, progresso=None):
        raise UpdateError("Download corrompido: o checksum nao confere.")

    verificador = VerificadorDeAtualizacao(versao_atual="0.1.0", baixar=_baixar_ruim)

    verificador.instalar_release(_release(), tmp_path / "TrackClassifier.app")

    args = _roda_ate(verificador.falhou)

    assert "corrompido" in args[0]


def test_instalar_repassa_o_progresso(qapp, tmp_path):
    def _baixar(release, destino, progresso=None):
        progresso(512, 1024)
        return destino

    verificador = VerificadorDeAtualizacao(
        versao_atual="0.1.0",
        baixar=_baixar,
        instalar=lambda zip_baixado, bundle, versao: None,
    )

    verificador.instalar_release(_release(), tmp_path / "TrackClassifier.app")

    assert _roda_ate(verificador.progresso) == (512, 1024)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_update_worker.py -v
```

Esperado: FAIL na coleta — `ModuleNotFoundError: No module named 'trackclassifier.ui.update_worker'`.

- [ ] **Step 3: Implementar**

Criar `src/trackclassifier/ui/update_worker.py`:

```python
"""Roda a checagem e a instalacao de atualizacao fora da thread da GUI.

Por que QThreadPool e nao a QThread do servico, como a maioria da UI faz: o
mesmo motivo de counts_worker.py -- nada aqui toca o TrackService. Este
codigo fala com a rede e com o diretorio do .app, e nao ha estado
compartilhado com o servico para proteger. A regra de "uma so thread dona do
servico" continua valendo para tudo que realmente fala com ele.
"""

import tempfile
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from .. import __version__
from ..updates import (
    Release,
    UpdateError,
    baixa,
    busca_ultimo_release,
    ha_versao_nova,
    instala,
)


class _Tarefa(QRunnable):
    def __init__(self, funcao: Callable[[], None]):
        super().__init__()
        self._funcao = funcao

    def run(self) -> None:
        self._funcao()


class VerificadorDeAtualizacao(QObject):
    """Checa e instala; emite tudo de volta na thread da GUI."""

    #: Release mais novo que o atual. `object` porque Release e um dataclass
    #: Python, nao um tipo registrado no meta-objeto do Qt.
    disponivel = Signal(object)
    sem_novidade = Signal()
    falhou = Signal(str)
    #: (bytes baixados, total em bytes). total e 0 quando o servidor nao
    #: manda Content-Length.
    progresso = Signal(int, int)
    instalado = Signal()

    #: Internos: atravessam a thread do pool de volta para a da GUI. Levam a
    #: geracao junto para o resultado de um pedido velho ser descartado.
    _achou = Signal(int, object)
    _nada = Signal(int)
    _erro = Signal(int, str)
    _terminou = Signal(int)
    _andou = Signal(int, int, int)

    def __init__(
        self,
        parent: QObject | None = None,
        versao_atual: str = __version__,
        buscar: Callable[[], Release | None] = busca_ultimo_release,
        baixar: Callable = baixa,
        instalar: Callable = instala,
    ) -> None:
        super().__init__(parent)
        # Injetaveis pelo mesmo motivo do `contar` de ContadorEmSegundoPlano:
        # o teste precisa observar o caminho inteiro sem tocar a rede nem o
        # diretorio do .app.
        self.versao_atual = versao_atual
        self.buscar = buscar
        self.baixar = baixar
        self.instalar = instalar
        self._geracao = 0

        self._achou.connect(self._recebe_achou)
        self._nada.connect(self._recebe_nada)
        self._erro.connect(self._recebe_erro)
        self._terminou.connect(self._recebe_terminou)
        self._andou.connect(self._recebe_andou)

    def _emite(self, sinal, *args) -> None:
        try:
            sinal.emit(*args)
        except RuntimeError:
            # A janela fechou enquanto a tarefa rodava e o objeto C++ ja
            # morreu. Emitir para um dono morto e o unico jeito real desta
            # thread quebrar a janela -- e ela nao tem mais quem ouca.
            return

    def checar(self) -> None:
        self._geracao += 1
        geracao = self._geracao
        QThreadPool.globalInstance().start(_Tarefa(lambda: self._roda_checagem(geracao)))

    def _roda_checagem(self, geracao: int) -> None:
        try:
            release = self.buscar()
        except UpdateError as erro:
            self._emite(self._erro, geracao, str(erro))
            return
        except Exception as erro:
            # Bug nosso nao pode virar excecao solta numa thread do pool: o
            # pior aceitavel e a faixa dizer que nao deu para verificar.
            self._emite(self._erro, geracao, f"Nao foi possivel verificar: {erro}")
            return

        if release is None or not ha_versao_nova(self.versao_atual, release.version):
            self._emite(self._nada, geracao)
            return
        self._emite(self._achou, geracao, release)

    def instalar_release(self, release: Release, bundle: Path) -> None:
        self._geracao += 1
        geracao = self._geracao
        QThreadPool.globalInstance().start(
            _Tarefa(lambda: self._roda_instalacao(geracao, release, bundle))
        )

    def _roda_instalacao(self, geracao: int, release: Release, bundle: Path) -> None:
        try:
            with tempfile.TemporaryDirectory(prefix="trackclassifier-dl-") as pasta:
                destino = Path(pasta) / f"TrackClassifier-{release.version}.zip"
                zip_baixado = self.baixar(
                    release,
                    destino,
                    progresso=lambda feito, total: self._emite(
                        self._andou, geracao, feito, total
                    ),
                )
                self.instalar(zip_baixado, bundle, release.version)
        except UpdateError as erro:
            self._emite(self._erro, geracao, str(erro))
            return
        except Exception as erro:
            self._emite(self._erro, geracao, f"Falha na atualizacao: {erro}")
            return
        self._emite(self._terminou, geracao)

    def _atual(self, geracao: int) -> bool:
        """Descarta resultado de pedido antigo: duas checagens em voo podem
        terminar fora de ordem, e a mais velha ofereceria uma versao que ja
        nao e a ultima."""
        return geracao == self._geracao

    @Slot(int, object)
    def _recebe_achou(self, geracao: int, release: object) -> None:
        if self._atual(geracao):
            self.disponivel.emit(release)

    @Slot(int)
    def _recebe_nada(self, geracao: int) -> None:
        if self._atual(geracao):
            self.sem_novidade.emit()

    @Slot(int, str)
    def _recebe_erro(self, geracao: int, mensagem: str) -> None:
        if self._atual(geracao):
            self.falhou.emit(mensagem)

    @Slot(int)
    def _recebe_terminou(self, geracao: int) -> None:
        if self._atual(geracao):
            self.instalado.emit()

    @Slot(int, int, int)
    def _recebe_andou(self, geracao: int, feito: int, total: int) -> None:
        if self._atual(geracao):
            self.progresso.emit(feito, total)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_update_worker.py -v
```

Esperado: 9 PASS.

- [ ] **Step 5: Lint**

```bash
uv run ruff check src/trackclassifier/ui/update_worker.py tests/test_update_worker.py
```

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/ui/update_worker.py tests/test_update_worker.py
git commit -m "feat(trackclassifier): checa e instala atualizacao fora da thread da GUI"
```

---

### Task 7: Copy do aviso de recomputo em `viewmodel.py`

**Files:**
- Modify: `src/trackclassifier/ui/viewmodel.py`
- Test: `tests/test_viewmodel.py`

**Interfaces:**
- Consumes: `Release` (Task 2).
- Produces: `texto_de_atualizacao(release: Release, versao_atual: str, n_tracks: int) -> str`

O texto mora no viewmodel porque e a camada testavel sem Qt — e o aviso de recomputo e a parte do produto que o usuario mais precisa acertar.

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_viewmodel.py`:

```python
def test_texto_de_atualizacao_avisa_do_recomputo_de_features():
    from trackclassifier.ui.viewmodel import texto_de_atualizacao
    from trackclassifier.updates import Release

    release = Release(
        version="0.3.0",
        url_zip="",
        url_sha256="",
        notas="Corrige o scan.",
        recomputa=frozenset({"features"}),
    )

    texto = texto_de_atualizacao(release, versao_atual="0.2.0", n_tracks=4200)

    assert "0.2.0" in texto
    assert "0.3.0" in texto
    assert "4200" in texto
    assert "recalcula" in texto
    assert "Corrige o scan." in texto


def test_texto_de_atualizacao_sem_recomputo_nao_assusta():
    from trackclassifier.ui.viewmodel import texto_de_atualizacao
    from trackclassifier.updates import Release

    release = Release(
        version="0.3.0", url_zip="", url_sha256="", notas="", recomputa=frozenset()
    )

    texto = texto_de_atualizacao(release, versao_atual="0.2.0", n_tracks=4200)

    assert "recalcula" not in texto
    assert "4200" not in texto


def test_texto_de_atualizacao_diz_que_as_classificacoes_ficam():
    """A pergunta que o usuario faz antes de clicar em Atualizar."""
    from trackclassifier.ui.viewmodel import texto_de_atualizacao
    from trackclassifier.updates import Release

    release = Release(
        version="0.3.0", url_zip="", url_sha256="", notas="", recomputa=frozenset()
    )

    texto = texto_de_atualizacao(release, versao_atual="0.2.0", n_tracks=10)

    assert "classificacoes" in texto
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_viewmodel.py -k texto_de_atualizacao -v
```

Esperado: FAIL — `ImportError: cannot import name 'texto_de_atualizacao'`.

- [ ] **Step 3: Implementar**

Acrescentar ao final de `src/trackclassifier/ui/viewmodel.py`:

```python
def texto_de_atualizacao(release, versao_atual: str, n_tracks: int) -> str:
    """Corpo do dialogo de confirmacao da atualizacao.

    Mora aqui, e nao no widget, porque e a parte que mais precisa de teste e
    a que mais vai mudar de redacao: o usuario decide atualizar ou nao com
    base nestas linhas. O tipo de `release` nao esta anotado de proposito --
    anotar exigiria importar updates.py, e este modulo se mantem sem
    dependencia de nada alem de dataclasses do dominio.
    """
    linhas = [f"Versao {versao_atual} instalada. Versao {release.version} disponivel."]

    if release.notas.strip():
        linhas += ["", release.notas.strip()]

    if release.recomputa:
        linhas += [
            "",
            f"Esta versao recalcula a analise das {n_tracks} tracks da "
            "biblioteca. O proximo scan vai demorar mais que o normal.",
        ]

    linhas += ["", "Suas classificacoes e as pastas do acervo nao sao alteradas."]
    return "\n".join(linhas)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_viewmodel.py -v
```

Esperado: todos PASS, incluindo `test_viewmodel_nao_importa_qt` (a funcao nao importa Qt nem `updates`).

- [ ] **Step 5: Commit**

```bash
git add src/trackclassifier/ui/viewmodel.py tests/test_viewmodel.py
git commit -m "feat(trackclassifier): texto do aviso de recomputo no viewmodel"
```

---

### Task 8: Faixa e integracao na janela

**Files:**
- Create: `src/trackclassifier/ui/update_banner.py`
- Modify: `src/trackclassifier/ui/window.py:27-88` (assinatura, layout central, menu, conexoes)
- Modify: `src/trackclassifier/ui/__main__.py:47`
- Test: `tests/test_window.py`

**Interfaces:**
- Consumes: `VerificadorDeAtualizacao` (Task 6), `EstadoDeAtualizacao` (Task 5), `texto_de_atualizacao` (Task 7), `caminho_do_bundle`, `relanca` (Task 4).
- Produces:
  - `class UpdateBanner(QWidget)` com `atualizar_clicado`, `dispensar_clicado`, `mostra(versao: str)`, `esconde()`, `mostra_progresso(feito: int, total: int)`
  - `MainWindow(service, config_path=None, bundle: Path | None = None, atualizacoes: EstadoDeAtualizacao | None = None)`

`bundle=None` (o default, e o que todos os testes existentes usam) significa: sem menu, sem faixa, nenhuma requisicao. E o comportamento em `uv run dj review`.

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_window.py`:

```python
def _release_falso(versao="0.9.0", recomputa=frozenset()):
    from trackclassifier.updates import Release

    return Release(
        version=versao,
        url_zip="https://z/app.zip",
        url_sha256="https://z/s",
        notas="",
        recomputa=recomputa,
    )


def test_sem_bundle_nao_ha_menu_de_atualizacao(qapp, tmp_path):
    """Em desenvolvimento o recurso nao existe: nao ha .app para trocar."""
    config = _config(tmp_path)
    servico = _servico(config)

    janela = MainWindow(servico)
    try:
        assert janela.acao_atualizar is None
        assert janela.menuBar().actions() == []
    finally:
        janela.close()


def test_com_bundle_o_menu_de_atualizacao_existe(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    janela = MainWindow(servico, bundle=tmp_path / "TrackClassifier.app")
    try:
        assert janela.acao_atualizar is not None
        assert "atualiza" in janela.acao_atualizar.text().lower()
    finally:
        janela.close()


def test_release_disponivel_mostra_a_faixa_com_a_versao(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    janela = MainWindow(servico, bundle=tmp_path / "TrackClassifier.app")
    try:
        janela._atualizacao_disponivel(_release_falso("0.9.0"))

        assert not janela.banner.isHidden()
        assert "0.9.0" in janela.banner.texto()
    finally:
        janela.close()


def test_dispensar_esconde_a_faixa_e_grava_a_versao(qapp, tmp_path):
    from trackclassifier.update_state import EstadoDeAtualizacao

    config = _config(tmp_path)
    servico = _servico(config)
    estado = EstadoDeAtualizacao(tmp_path / "updates.json")

    janela = MainWindow(
        servico, bundle=tmp_path / "TrackClassifier.app", atualizacoes=estado
    )
    try:
        janela._atualizacao_disponivel(_release_falso("0.9.0"))
        janela.banner.dispensar()

        assert janela.banner.isHidden()
        assert estado.esta_dispensada("0.9.0")
    finally:
        janela.close()


def test_versao_ja_dispensada_nao_mostra_a_faixa(qapp, tmp_path):
    from trackclassifier.update_state import EstadoDeAtualizacao

    config = _config(tmp_path)
    servico = _servico(config)
    estado = EstadoDeAtualizacao(tmp_path / "updates.json")
    estado.dispensa("0.9.0")

    janela = MainWindow(
        servico, bundle=tmp_path / "TrackClassifier.app", atualizacoes=estado
    )
    try:
        janela._atualizacao_disponivel(_release_falso("0.9.0"))

        assert janela.banner.isHidden()
    finally:
        janela.close()


def test_menu_forca_a_checagem_mesmo_com_a_versao_dispensada(qapp, tmp_path):
    """Pedido explicito ignora tanto o intervalo quanto o dispensado."""
    from trackclassifier.update_state import EstadoDeAtualizacao

    config = _config(tmp_path)
    servico = _servico(config)
    estado = EstadoDeAtualizacao(tmp_path / "updates.json")
    estado.dispensa("0.9.0")

    janela = MainWindow(
        servico, bundle=tmp_path / "TrackClassifier.app", atualizacoes=estado
    )
    try:
        janela.acao_atualizar.trigger()
        janela._atualizacao_disponivel(_release_falso("0.9.0"))

        assert not janela.banner.isHidden()
    finally:
        janela.close()


def test_falha_de_checagem_nao_mostra_faixa_nem_derruba_a_janela(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    janela = MainWindow(servico, bundle=tmp_path / "TrackClassifier.app")
    try:
        janela._atualizacao_falhou("Nao foi possivel verificar atualizacoes.")

        assert janela.banner.isHidden()
        assert janela.isEnabled()
    finally:
        janela.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_window.py -k atualiza -v
```

Esperado: FAIL — `AttributeError: 'MainWindow' object has no attribute 'acao_atualizar'`.

- [ ] **Step 3: Escrever a faixa**

Criar `src/trackclassifier/ui/update_banner.py`:

```python
"""Faixa fina no topo da janela avisando que ha versao nova.

Faixa e nao dialogo modal de proposito: descobrir atualizacao e um evento do
app, nao do usuario. Um modal no meio de uma sessao de revisao interrompe o
unico fluxo que o app existe para servir.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget

from .tokens import COLOR_ACCENT_BG, COLOR_ACCENT_TEXT, SPACE_4, SPACE_5
from .typography import estiliza_label


class UpdateBanner(QWidget):
    atualizar_clicado = Signal()
    dispensar_clicado = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UpdateBanner")
        # Cor vem de tokens.py: literal hex em ui/ quebra
        # test_tokens.py::test_nenhum_hex_fora_do_json.
        self.setStyleSheet(
            f"#UpdateBanner {{ background: {COLOR_ACCENT_BG}; }}"
            f"#UpdateBanner QLabel {{ color: {COLOR_ACCENT_TEXT}; }}"
        )

        self._texto = QLabel("")
        self._barra = QProgressBar()
        self._barra.setVisible(False)
        self._barra.setMaximumWidth(160)

        self._botao = QPushButton()
        estiliza_label(self._botao, "Atualizar")
        self._botao.setProperty("variant", "primary")
        self._botao.clicked.connect(self.atualizar_clicado)

        self._fechar = QPushButton("✕")
        self._fechar.setProperty("variant", "ghost")
        self._fechar.clicked.connect(self.dispensar_clicado)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_4, SPACE_4, SPACE_4)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self._texto)
        layout.addStretch(1)
        layout.addWidget(self._barra)
        layout.addWidget(self._botao)
        layout.addWidget(self._fechar)

        self.hide()

    def texto(self) -> str:
        return self._texto.text()

    def mostra(self, versao: str) -> None:
        self._texto.setText(f"Versao {versao} disponivel.")
        self._barra.setVisible(False)
        self._botao.setEnabled(True)
        self.show()

    def mostra_progresso(self, feito: int, total: int) -> None:
        self._botao.setEnabled(False)
        self._barra.setVisible(True)
        # total 0 e o servidor nao ter mandado Content-Length: barra
        # indeterminada em vez de uma barra travada em 0%, que le como
        # download parado.
        self._barra.setRange(0, total)
        self._barra.setValue(feito)
        self._texto.setText("Baixando a atualizacao...")

    def esconde(self) -> None:
        self.hide()

    def acionar(self) -> None:
        """Aciona Atualizar. Existe para o teste percorrer o clique real."""
        self._botao.click()

    def dispensar(self) -> None:
        """Aciona o ✕. Mesmo motivo de acionar()."""
        self._fechar.click()
```

- [ ] **Step 4: Ligar na janela**

Em `src/trackclassifier/ui/window.py`:

Acrescentar aos imports:

```python
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..update_state import EstadoDeAtualizacao
from ..updates import Release, relanca
from .update_banner import UpdateBanner
from .update_worker import VerificadorDeAtualizacao
from .viewmodel import LibraryState, ModelState, ReviewState, texto_de_atualizacao
```

Trocar a assinatura (linha 28):

```python
    def __init__(
        self,
        service: TrackService,
        config_path: Path | None = None,
        bundle: Path | None = None,
        atualizacoes: EstadoDeAtualizacao | None = None,
    ) -> None:
```

Trocar `self.setCentralWidget(self.tabs)` (linha 64) por:

```python
        # A faixa entra num container acima das abas, e nao como widget de
        # canto da tab bar: ela precisa da largura inteira e nao pode
        # competir com o botao Escanear, que ja ocupa o canto.
        self.banner = UpdateBanner()
        central = QWidget()
        caixa = QVBoxLayout(central)
        caixa.setContentsMargins(0, 0, 0, 0)
        caixa.setSpacing(0)
        caixa.addWidget(self.banner)
        caixa.addWidget(self.tabs)
        self.setCentralWidget(central)
```

Acrescentar, logo antes de `self._conecta()` (linha 71):

```python
        self._bundle = bundle
        self._atualizacoes = atualizacoes
        self._release_pendente: Release | None = None
        # True enquanto a checagem em voo for a do boot. O menu zera isto:
        # pedido explicito ignora a versao dispensada e merece resposta
        # mesmo quando nao ha novidade.
        self._checagem_automatica = True
        self._n_tracks = 0
        self.acao_atualizar: QAction | None = None
        self._verificador: VerificadorDeAtualizacao | None = None
        if bundle is not None:
            self._monta_atualizacao()
```

E os metodos novos, depois de `_modelo_retreinado`:

```python
    def _monta_atualizacao(self) -> None:
        """So existe dentro do .app: fora dele nao ha bundle para trocar."""
        self._verificador = VerificadorDeAtualizacao(self)
        self._verificador.disponivel.connect(self._atualizacao_disponivel)
        self._verificador.sem_novidade.connect(self._sem_atualizacao)
        self._verificador.falhou.connect(self._atualizacao_falhou)
        self._verificador.progresso.connect(self.banner.mostra_progresso)
        self._verificador.instalado.connect(self._atualizacao_instalada)

        self.banner.atualizar_clicado.connect(self._confirma_atualizacao)
        self.banner.dispensar_clicado.connect(self._dispensa_atualizacao)

        self.acao_atualizar = QAction("Buscar atualizacoes...", self)
        # ApplicationSpecificRole e o que faz o Qt colocar o item no menu
        # "TrackClassifier" do macOS, junto de Sobre e Sair, em vez de criar
        # um menu solto na barra.
        self.acao_atualizar.setMenuRole(QAction.MenuRole.ApplicationSpecificRole)
        self.acao_atualizar.triggered.connect(self._checa_a_pedido)
        self.menuBar().addAction(self.acao_atualizar)

        if self._atualizacoes is not None and self._atualizacoes.deve_checar():
            self._atualizacoes.marca_checagem()
            self._verificador.checar()

    def _checa_a_pedido(self) -> None:
        """Pedido explicito: ignora o intervalo e a versao dispensada."""
        self._checagem_automatica = False
        if self._verificador is not None:
            self._verificador.checar()

    def _atualizacao_disponivel(self, release: Release) -> None:
        dispensada = (
            self._checagem_automatica
            and self._atualizacoes is not None
            and self._atualizacoes.esta_dispensada(release.version)
        )
        if dispensada:
            return
        self._release_pendente = release
        self.banner.mostra(release.version)

    def _sem_atualizacao(self) -> None:
        self.banner.esconde()
        if not self._checagem_automatica:
            # So avisa quando o usuario perguntou. Silencio na checagem
            # automatica e o comportamento correto: nao ha noticia.
            self.statusBar().showMessage("Voce ja esta na versao mais recente.", 4000)

    def _atualizacao_falhou(self, mensagem: str) -> None:
        self.banner.esconde()
        self.statusBar().showMessage(mensagem, 6000)

    def _confirma_atualizacao(self) -> None:
        if self._release_pendente is None or self._bundle is None:
            return
        corpo = texto_de_atualizacao(
            self._release_pendente,
            versao_atual=self._verificador.versao_atual,
            n_tracks=self._n_tracks,
        )
        resposta = QMessageBox.question(
            self,
            "Atualizar o TrackClassifier",
            corpo,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        if resposta != QMessageBox.StandardButton.Ok:
            return
        self._verificador.instalar_release(self._release_pendente, self._bundle)

    def _dispensa_atualizacao(self) -> None:
        if self._release_pendente is not None and self._atualizacoes is not None:
            self._atualizacoes.dispensa(self._release_pendente.version)
        self.banner.esconde()

    def _atualizacao_instalada(self) -> None:
        QMessageBox.information(
            self,
            "Atualizado",
            "A versao nova foi instalada. O app vai reabrir.",
        )
        if self._bundle is not None:
            relanca(self._bundle)
        self.close()
```

Em `apply_states`, guardar a contagem que alimenta o aviso de recomputo:

```python
    def apply_states(
        self, review: ReviewState, library: LibraryState, model: ModelState
    ) -> None:
        self.review_tab.set_state(review)
        self.library_tab.set_state(library)
        self.model_tab.set_state(model)
        # O aviso de recomputo precisa de quantas tracks serao reanalisadas.
        # Sai do estado que a janela ja recebe por sinal -- nenhum widget
        # chama o TrackService.
        self._n_tracks = len(library.rows)
```

- [ ] **Step 5: Ligar em `__main__.py`**

Em `src/trackclassifier/ui/__main__.py`, acrescentar aos imports:

```python
from ..update_state import EstadoDeAtualizacao
from ..updates import caminho_do_bundle
```

E trocar a linha 47 por:

```python
    bundle = caminho_do_bundle()
    # Sem bundle (rodando do checkout) nao ha o que atualizar, e tambem nao
    # ha por que criar o arquivo de controle.
    atualizacoes = (
        EstadoDeAtualizacao(config.data_dir / "updates.json") if bundle else None
    )
    janela = MainWindow(
        TrackService(config),
        config_path=caminho,
        bundle=bundle,
        atualizacoes=atualizacoes,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_window.py -v
```

Esperado: todos PASS, inclusive os 20+ testes ja existentes que constroem `MainWindow(servico)` sem `bundle`.

- [ ] **Step 7: Verificar o teste de hex e a suite inteira**

```bash
uv run pytest && uv run ruff check .
```

Esperado: PASS, incluindo `tests/test_tokens.py::test_nenhum_hex_fora_do_json`.

- [ ] **Step 8: Commit**

```bash
git add src/trackclassifier/ui/update_banner.py src/trackclassifier/ui/window.py src/trackclassifier/ui/__main__.py tests/test_window.py
git commit -m "feat(trackclassifier): faixa e menu de atualizacao na janela"
```

---

### Task 9: Workflow de release

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `README.md:99-109`

**Interfaces:**
- Consumes: `trackclassifier.__version__` (Task 1).
- Produces: um GitHub Release por tag `v*`, com dois assets: `TrackClassifier-<versao>.zip` e `TrackClassifier-<versao>.zip.sha256`. `busca_ultimo_release` (Task 2) depende **exatamente** desses dois sufixos.

- [ ] **Step 1: Escrever o workflow**

Criar `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags: ["v*"]

# gh release create precisa escrever no repositorio; o token padrao vem
# somente-leitura desde 2023.
permissions:
  contents: write

jobs:
  build-app:
    # macos-latest e gratuito neste repositorio por ele ser publico -- a nota
    # antiga do README sobre custo de minutos valia para repositorio privado.
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v7

      - name: Install uv
        uses: astral-sh/setup-uv@v9.0.0
        with:
          enable-cache: true

      - name: Set up Python
        uses: actions/setup-python@v7
        with:
          python-version: "3.11"

      - name: Install ffmpeg
        run: brew install ffmpeg

      - name: Install dependencies
        run: uv sync --extra build

      # Falha aqui e melhor que release publicado mentindo a versao: o app
      # se identificaria com um numero e o release anunciaria outro, e a
      # comparacao do updater passaria a mentir em toda checagem.
      - name: Check tag matches __version__
        run: |
          set -euo pipefail
          versao=$(uv run python -c "import trackclassifier; print(trackclassifier.__version__)")
          tag="${GITHUB_REF_NAME#v}"
          if [ "$versao" != "$tag" ]; then
            echo "Tag $GITHUB_REF_NAME nao bate com __version__ = $versao" >&2
            exit 1
          fi
          echo "versao=$versao" >> "$GITHUB_ENV"

      - name: Build the .app
        run: uv run pyinstaller packaging/trackclassifier.spec --noconfirm

      # ditto e nao zip: o zip comum nao preserva os symlinks internos dos
      # frameworks do Qt, e o bundle chega quebrado do outro lado.
      - name: Zip the bundle
        run: |
          set -euo pipefail
          nome="TrackClassifier-${versao}.zip"
          ditto -c -k --keepParent dist/TrackClassifier.app "$nome"
          shasum -a 256 "$nome" > "${nome}.sha256"
          echo "zip=$nome" >> "$GITHUB_ENV"

      - name: Publish the release
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh release create "$GITHUB_REF_NAME" "$zip" "${zip}.sha256" --generate-notes
```

- [ ] **Step 2: Validar a sintaxe do YAML**

```bash
python3 -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.github/workflows/release.yml').read_text()); print('ok')"
```

Esperado: `ok`. Se `yaml` nao estiver disponivel, o parse so sera validado
pelo GitHub depois do push -- conferir com `gh workflow view Release`.

- [ ] **Step 3: Atualizar o README**

Substituir a secao "Empacotamento (macOS)" de `README.md` por:

```markdown
## Empacotamento e release (macOS)

Build local, para testar:

```bash
uv sync --extra dev --extra build
uv run pyinstaller packaging/trackclassifier.spec --noconfirm
```

Gera `dist/TrackClassifier.app`, um app standalone com ffmpeg embutido que
abre a janela de revisao ao ser clicado no Finder.

Release publico: bumpe `__version__` em `src/trackclassifier/__init__.py`,
comite, e empurre a tag correspondente.

```bash
git tag v0.3.0 && git push origin v0.3.0
```

O workflow `.github/workflows/release.yml` builda em `macos-latest` (gratuito
neste repositorio por ele ser publico), zipa com `ditto`, gera o `.sha256` e
publica o GitHub Release. A tag tem que bater com `__version__` -- o workflow
falha de proposito se divergirem.

Se a versao nova mudar `HandcraftedExtractor.name` ou `PRESENTATION_VERSION`,
acrescente ao corpo do release a linha:

```
recompute: features, presentation
```

E o que faz o app avisar, antes de atualizar, que a analise de toda a
biblioteca sera refeita.
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml README.md
git commit -m "feat(ci): publica o .app em release ao empurrar uma tag"
```

- [ ] **Step 5: Verificar de ponta a ponta**

Este e o unico passo que exige um release de verdade. Depois do merge:

```bash
git tag v0.2.1 && git push origin v0.2.1
```

Acompanhar o workflow e confirmar que o release traz os dois assets. Depois,
com o `.app` da versao **anterior** instalado, abrir o app e usar "Buscar
atualizacoes..." no menu TrackClassifier. Confirmar, em ordem:

1. A faixa aparece com a versao nova.
2. O dialogo mostra o aviso de recomputo somente se o corpo do release trouxe a linha `recompute:`.
3. Depois de instalar, o app reabre na versao nova.
4. **`~/.trackclassifier/` continua com `analyses.parquet`, `sha1.json`, `presentation.parquet`, `covers/`, `peaks/` e `model.joblib` intactos**, e a Biblioteca abre com as mesmas tracks analisadas de antes.

---

## Ordem de execucao e dependencias

```
Task 1 (versao)
  ├─ Task 2 (busca) → Task 3 (download) → Task 4 (instala)
  │                                          └─ Task 6 (worker) ─┐
  ├─ Task 5 (estado) ──────────────────────────────────────────  ├─ Task 8 (janela)
  ├─ Task 7 (copy) ──────────────────────────────────────────────┘
  └─ Task 9 (workflow, independente do resto)
```

Tasks 2–4 sao sequenciais (mesmo arquivo). Tasks 5, 7 e 9 nao dependem umas
das outras e podem ir em qualquer ordem depois da Task 1.

## Verificacao final

```bash
uv run ruff check . && uv run pytest
```

Alem da suite, os tres testes que carregam o requisito do usuario:

- `tests/test_updates.py::test_instala_nao_toca_no_data_dir`
- `tests/test_viewmodel.py::test_texto_de_atualizacao_diz_que_as_classificacoes_ficam`
- O passo 5 da Task 9, manual, com um `.app` de verdade.
