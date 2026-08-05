# UI desktop PySide6 — fase 1 — plano de implementacao

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir `dj review` (FastAPI + navegador) por uma janela PySide6 com tres abas — Revisao, Biblioteca e Modelo — falando in-process com o `TrackService` real.

**Architecture:** Uma `QThread` e dona unica do `TrackService`; a UI manda pedidos e recebe sinais. Entre os dois fica `ui/viewmodel.py`, feito so de dataclasses puras que nao importam Qt — e o que permite testar a logica de tela com `pytest` sem `QApplication`. O backend de analise (`ProcessPoolExecutor` dentro de `service._analyze`) nao muda de forma.

**Tech Stack:** Python 3.11+, PySide6-Essentials (obrigatorio), PySide6-Addons (extra opcional `audio`), numpy, o backend atual (`TrackService`, `AnalysisCache`, `TrackModel`).

## Global Constraints

- Python `>=3.11,<3.14`. Nao usar sintaxe alem de 3.11.
- **Portugues sem acentos em todo `src/`** — variaveis, funcoes, comentarios, docstrings, mensagens de erro **e rotulos visiveis na UI**. O `cli.py` ja imprime `"Acuracia (leave-one-out)"` e `"Matriz de confusao"` para o usuario; a janela segue a mesma regra. Ao portar widgets do ref2, **remova os acentos dos rotulos**: `"Título"` vira `"Titulo"`, `"Classificação"` vira `"Classificacao"`, `"Duração"` vira `"Duracao"`, `"Notação da key"` vira `"Notacao da key"`.
- API publica (dataclasses, nomes de campo, metodos de classe) em ingles; interior das funcoes em portugues.
- Comentarios explicam **por que**, nao o que. Longos quando a decisao nao e obvia.
- ruff: `line-length = 100`, regras `E,F,I,UP,B`. `uv run ruff check .` e gate do CI.
- **Nenhum hex fora de `design/design-tokens.json`.** Cores chegam ao codigo por `ui/tokens.py`, que e gerado.
- Dois pesos de fonte apenas: 400 e 500. Nunca 600/700.
- Numeros (BPM, duracao, confianca) sempre em fonte mono, alinhados a direita.
- Sentence case em rotulos. Uma cor de accent por tela.
- Altura de linha da tabela fixa em **46px** (`SIZE_ROW_COMFORTABLE`). Nao negociavel: e o que permite ao `QTableView` calcular o offset do scroll sem medir cada item.
- `ui/viewmodel.py` **nao importa Qt**. Os modulos de `ui/` **nao importam `TrackService`** — so `ui/worker.py` importa.
- Todo teste que instancia widget roda com `QT_QPA_PLATFORM=offscreen`.
- `PySide6-Essentials` e dependencia obrigatoria; `PySide6-Addons` fica no extra opcional `audio`, para o CI instalar so o Essentials e cair no `SimulatedPlayer`.
- Commits: conventional commits com escopo, ex. `feat(ui):`, `fix(trackclassifier):`.
- Identidade de track e **sha1**, nunca caminho. Qualquer cache novo se chaveia por sha1.

## Escopo desta fase

Entrega da fase 1, conforme a spec: remocao da web, janela com as tres abas contra o `TrackService` real, waveform derivada do `energy_curve` existente (mono, ainda **nao** RGB), scan global em background, cache de sha1 e desfazer.

**Fica fora** (fases 2 a 4, cada uma com plano proprio): `mutagen` (titulo, artista, genero, capa), buckets RGB, key/Camelot e `KeyChip`, `presentation.py`.

Consequencia direta nas colunas da Biblioteca: a spec lista `Onda | Titulo | Artista | Genero | BPM | Key | Classificacao | Duracao`, mas titulo, artista, genero e key so existem a partir da fase 2. **Nesta fase as colunas sao as que tem dado real por tras:** `Onda | Arquivo | BPM | Classificacao | Confianca | Duracao`. As demais entram junto com os dados que as alimentam.

## File Structure

**Criados:**

| Arquivo | Responsabilidade |
|---|---|
| `design/design-tokens.json` | Fonte unica de verdade de cor, tipografia, espaco, raio e tamanho |
| `design/build_tokens.py` | Gera `ui/tokens.py` e `ui/app.qss` a partir do JSON |
| `src/trackclassifier/ui/__init__.py` | Pacote vazio |
| `src/trackclassifier/ui/__main__.py` | `QApplication`, carrega o QSS, abre a janela |
| `src/trackclassifier/ui/viewmodel.py` | `TrackService` -> dataclasses puras. Sem Qt, sem librosa |
| `src/trackclassifier/ui/worker.py` | `QThread` dona do servico; converte progresso e resultados em sinais |
| `src/trackclassifier/ui/window.py` | `QMainWindow`, barra de abas, status bar, botao de scan |
| `src/trackclassifier/ui/review_tab.py` | Aba Revisao: uma track por vez, atalhos 1/2/3 |
| `src/trackclassifier/ui/library_tab.py` | Aba Biblioteca: tabela, filtro, busca |
| `src/trackclassifier/ui/model_tab.py` | Aba Modelo: metricas, retreinar, falhas |
| `src/trackclassifier/ui/tokens.py` | **GERADO** — nao editar a mao |
| `src/trackclassifier/ui/app.qss` | **GERADO** — nao editar a mao |
| `src/trackclassifier/ui/widgets/__init__.py` | Pacote vazio |
| `src/trackclassifier/ui/widgets/waveform_render.py` | Render mono de `energy_curve` em `QPixmap` + LRU por sha1 |
| `src/trackclassifier/ui/widgets/waveform_view.py` | Onda grande com playhead; clique emite seek |
| `src/trackclassifier/ui/widgets/delegates.py` | Mini waveform e chip de classificacao |
| `src/trackclassifier/ui/widgets/player.py` | `create_player()`: `QtAudioPlayer` real ou `SimulatedPlayer` |
| `src/trackclassifier/ui/widgets/track_model.py` | `QAbstractTableModel` com as colunas da fase 1 |

**Modificados:**

| Arquivo | Mudanca |
|---|---|
| `src/trackclassifier/library.py` | `Sha1Cache` por `(path, mtime, size)`; `scan_labeled`/`scan_inbox` aceitam o cache |
| `src/trackclassifier/apply.py` | `undo_move()` — devolve o arquivo a pasta de origem |
| `src/trackclassifier/service.py` | Usa `Sha1Cache`; guarda a ultima decisao; `undo_last()` |
| `src/trackclassifier/cli.py` | `dj review` abre a janela; `dj scan`/`dj train` seguem headless |
| `pyproject.toml` | Entra PySide6; saem fastapi/uvicorn; extra `audio`; `QT_QPA_PLATFORM` no pytest |
| `.github/workflows/ci.yml` | `QT_QPA_PLATFORM=offscreen` |

**Removidos** (Task 9, depois que a janela funciona): `web.py`, `streaming.py`, `static/`, `tests/test_web.py`, `tests/test_streaming.py`.

---

### Task 1: Cache de sha1 por (path, mtime, size)

`library.py` hoje le todo arquivo por inteiro para calcular o sha1, antes de qualquer outra coisa. Com centenas de tracks sao gigabytes de I/O e minutos de janela morta. Sem isto, o resto do design de concorrencia nao salva o boot.

**Files:**
- Modify: `src/trackclassifier/library.py`
- Modify: `src/trackclassifier/service.py:52`
- Test: `tests/test_library.py`

**Interfaces:**
- Consumes: `cache.file_sha1(path) -> str` (ja existe).
- Produces:
  - `library.Sha1Cache(path: Path)` com `get(caminho: Path) -> str`, `save() -> None`, `__len__() -> int`
  - `library.scan_labeled(config: Config, sha1_cache: Sha1Cache | None = None) -> list[TrackRef]`
  - `library.scan_inbox(config: Config, sha1_cache: Sha1Cache | None = None) -> list[TrackRef]`

- [ ] **Step 1: Write the failing test**

Em `tests/test_library.py`:

```python
def test_sha1_cache_nao_rele_arquivo_que_nao_mudou(tmp_path):
    from trackclassifier import library

    arquivo = tmp_path / "t.wav"
    arquivo.write_bytes(b"conteudo qualquer")

    cache = library.Sha1Cache(tmp_path / "sha1.json")
    primeiro = cache.get(arquivo)

    leituras = {"n": 0}
    original = library.file_sha1

    def _espiao(caminho):
        leituras["n"] += 1
        return original(caminho)

    library.file_sha1 = _espiao
    try:
        segundo = cache.get(arquivo)
    finally:
        library.file_sha1 = original

    assert segundo == primeiro
    assert leituras["n"] == 0


def test_sha1_cache_recalcula_quando_o_conteudo_muda(tmp_path):
    import os

    from trackclassifier import library

    arquivo = tmp_path / "t.wav"
    arquivo.write_bytes(b"antes")
    cache = library.Sha1Cache(tmp_path / "sha1.json")
    antes = cache.get(arquivo)

    arquivo.write_bytes(b"depois com outro tamanho")
    # mtime com granularidade grosseira em alguns sistemas de arquivos: forca
    # a diferenca para o teste provar a invalidacao, nao a sorte do relogio.
    os.utime(arquivo, (0, 0))

    assert cache.get(arquivo) != antes


def test_sha1_cache_sobrevive_a_json_corrompido(tmp_path):
    from trackclassifier import library

    caminho = tmp_path / "sha1.json"
    caminho.write_text("{ isto nao e json valido")

    arquivo = tmp_path / "t.wav"
    arquivo.write_bytes(b"x")

    cache = library.Sha1Cache(caminho)
    assert len(cache) == 0
    assert cache.get(arquivo)


def test_sha1_cache_persiste_entre_instancias(tmp_path):
    from trackclassifier import library

    arquivo = tmp_path / "t.wav"
    arquivo.write_bytes(b"persistente")
    caminho = tmp_path / "sha1.json"

    primeiro = library.Sha1Cache(caminho)
    esperado = primeiro.get(arquivo)
    primeiro.save()

    segundo = library.Sha1Cache(caminho)
    assert len(segundo) == 1
    assert segundo.get(arquivo) == esperado
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_library.py -k sha1_cache -v`
Expected: FAIL com `AttributeError: module 'trackclassifier.library' has no attribute 'Sha1Cache'`

- [ ] **Step 3: Write minimal implementation**

Em `src/trackclassifier/library.py`, trocar o import e acrescentar a classe:

```python
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .audio_io import SUPPORTED_SUFFIXES
from .cache import file_sha1
from .config import Config
from .labels import Label


class Sha1Cache:
    """Memoriza o sha1 de cada arquivo por (caminho, mtime, size).

    O sha1 continua sendo a identidade da track -- isto so evita reler o
    arquivo inteiro quando nada nele mudou. A tripla e conservadora de
    proposito: qualquer divergencia em mtime ou tamanho recalcula. Uma
    edicao que preserve os dois e possivel na teoria, mas exigiria
    reescrever o arquivo mantendo byte-count e timestamp, o que nenhuma
    ferramenta de audio faz.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._linhas: dict[str, dict] = {}
        self._sujo = False
        if self.path.is_file():
            try:
                self._linhas = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                # Mesma contencao de cache.py: JSON truncado por interrupcao
                # ou schema antigo vira cache vazio, nunca derruba o comando.
                self._linhas = {}

    def __len__(self) -> int:
        return len(self._linhas)

    def get(self, caminho: Path) -> str:
        caminho = Path(caminho)
        chave = str(caminho)
        info = caminho.stat()
        registro = self._linhas.get(chave)
        if (
            registro is not None
            and registro.get("mtime") == info.st_mtime
            and registro.get("size") == info.st_size
        ):
            return registro["sha1"]

        digest = file_sha1(caminho)
        self._linhas[chave] = {
            "mtime": info.st_mtime,
            "size": info.st_size,
            "sha1": digest,
        }
        self._sujo = True
        return digest

    def save(self) -> None:
        if not self._sujo:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._linhas), encoding="utf-8")
        os.replace(tmp, self.path)
        self._sujo = False
```

E trocar as duas funcoes de scan para aceitarem o cache:

```python
def scan_labeled(config: Config, sha1_cache: Sha1Cache | None = None) -> list[TrackRef]:
    calcula = sha1_cache.get if sha1_cache is not None else file_sha1
    refs: list[TrackRef] = []
    for rotulo, pasta in config.folders.items():
        for caminho in _arquivos_de_audio(pasta):
            refs.append(TrackRef(path=caminho, label=rotulo, sha1=calcula(caminho)))
    return sorted(refs, key=lambda ref: str(ref.path).lower())


def scan_inbox(config: Config, sha1_cache: Sha1Cache | None = None) -> list[TrackRef]:
    calcula = sha1_cache.get if sha1_cache is not None else file_sha1
    pastas_rotuladas = [pasta.resolve() for pasta in config.folders.values()]
    return [
        TrackRef(path=caminho, label=None, sha1=calcula(caminho))
        for caminho in _arquivos_de_audio(config.inbox)
        if not _dentro_de_pasta_rotulada(caminho, pastas_rotuladas)
    ]
```

> Nota para quem implementa: `calcula = sha1_cache.get` e resolvido no momento da chamada, entao o `library.file_sha1 = _espiao` do teste continua enxergando a substituicao no caminho sem cache. No caminho com cache, o espiao nao e chamado — que e exatamente o que o teste afirma.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_library.py -v`
Expected: PASS, incluindo os testes que ja existiam

- [ ] **Step 5: Ligar no TrackService**

Em `src/trackclassifier/service.py`, no `__init__`, depois da linha do `AnalysisCache`:

```python
        self.cache = AnalysisCache(config.data_dir / "analyses.parquet")
        self.sha1_cache = Sha1Cache(config.data_dir / "sha1.json")
```

E em `analyze_all`:

```python
    def analyze_all(self, on_progress: ProgressCallback | None = None) -> None:
        self._failures = []
        candidatos = scan_labeled(self.config, self.sha1_cache) + scan_inbox(
            self.config, self.sha1_cache
        )
        # Salva antes de extrair: a varredura sozinha ja custou o I/O, e uma
        # interrupcao durante a extracao nao pode jogar esse trabalho fora.
        self.sha1_cache.save()
        aceitos = self._analyze(candidatos, on_progress)
        self._labeled = [ref for ref in aceitos if ref.label is not None]
        self._inbox = [ref for ref in aceitos if ref.label is None]
        self.cache.save()
```

Atualizar o import no topo de `service.py`:

```python
from .library import Sha1Cache, TrackRef, scan_inbox, scan_labeled
```

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -q && uv run ruff check .`
Expected: PASS, 115+ testes

- [ ] **Step 7: Commit**

```bash
git add src/trackclassifier/library.py src/trackclassifier/service.py tests/test_library.py
git commit -m "perf(trackclassifier): cacheia sha1 por (path, mtime, size)"
```

---

### Task 2: Desfazer a ultima decisao

Comportamento novo. Hoje a decisao move o arquivo e nao ha volta sem ir ao Finder. Com tres teclas adjacentes e lotes de dezenas de tracks, o erro de tecla e questao de tempo. Pilha de um nivel apenas, nao persistida entre execucoes.

**Files:**
- Modify: `src/trackclassifier/apply.py`
- Modify: `src/trackclassifier/service.py`
- Test: `tests/test_apply.py`, `tests/test_service.py`

**Interfaces:**
- Consumes: `apply.move_to_folder(src, dest_dir) -> Path`, `apply.FileVanishedError`, `apply._destino_livre(dest_dir, nome) -> Path` (todos ja existem).
- Produces:
  - `apply.undo_move(atual: Path, origem_dir: Path) -> Path`
  - `service.TrackService.undo_last() -> bool` — `True` se desfez, `False` se nao havia o que desfazer

- [ ] **Step 1: Write the failing test**

Em `tests/test_apply.py`:

```python
def test_undo_move_devolve_o_arquivo_para_a_origem(tmp_path):
    from trackclassifier.apply import move_to_folder, undo_move

    origem = tmp_path / "inbox"
    destino_dir = tmp_path / "up"
    origem.mkdir()
    destino_dir.mkdir()

    arquivo = origem / "t.wav"
    arquivo.write_bytes(b"conteudo")

    movido = move_to_folder(arquivo, destino_dir)
    assert movido.is_file() and not arquivo.exists()

    voltou = undo_move(movido, origem)

    assert voltou == origem / "t.wav"
    assert voltou.read_bytes() == b"conteudo"
    assert not movido.exists()


def test_undo_move_nao_sobrescreve_homonimo_na_origem(tmp_path):
    from trackclassifier.apply import move_to_folder, undo_move

    origem = tmp_path / "inbox"
    destino_dir = tmp_path / "up"
    origem.mkdir()
    destino_dir.mkdir()

    arquivo = origem / "t.wav"
    arquivo.write_bytes(b"original")
    movido = move_to_folder(arquivo, destino_dir)

    # Um download novo com o mesmo nome caiu na inbox enquanto isso.
    (origem / "t.wav").write_bytes(b"intruso")

    voltou = undo_move(movido, origem)

    assert voltou != origem / "t.wav"
    assert voltou.read_bytes() == b"original"
    assert (origem / "t.wav").read_bytes() == b"intruso"


def test_undo_move_de_arquivo_que_sumiu_levanta_file_vanished(tmp_path):
    import pytest

    from trackclassifier.apply import FileVanishedError, undo_move

    origem = tmp_path / "inbox"
    origem.mkdir()

    with pytest.raises(FileVanishedError):
        undo_move(tmp_path / "nao_existe.wav", origem)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_apply.py -k undo -v`
Expected: FAIL com `ImportError: cannot import name 'undo_move'`

- [ ] **Step 3: Write minimal implementation**

Acrescentar ao fim de `src/trackclassifier/apply.py`:

```python
def undo_move(atual: Path, origem_dir: Path) -> Path:
    """Devolve para origem_dir um arquivo movido por move_to_folder.

    Nao e um `shutil.move` simples de volta: entre a decisao e o desfazer,
    um download novo pode ter ocupado o nome original na inbox. Reutiliza
    _destino_livre pelo mesmo motivo de move_to_folder -- a reserva do nome
    e atomica, e o desfazer pode ser disparado da thread da UI enquanto o
    scan mexe na mesma pasta.
    """
    atual = Path(atual)
    if not atual.is_file():
        raise FileVanishedError(f"Arquivo nao existe mais: {atual}")

    origem_dir = Path(origem_dir)
    origem_dir.mkdir(parents=True, exist_ok=True)
    destino = _destino_livre(origem_dir, atual.name)
    try:
        shutil.move(str(atual), str(destino))
    except BaseException:
        destino.unlink(missing_ok=True)
        raise
    return destino
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_apply.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for the service**

Em `tests/test_service.py`:

```python
def test_desfazer_devolve_a_track_para_a_fila(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.5.mp3").write_bytes(b"nova_0.5.mp3")

    servico = _servico(config)
    servico.train()

    antes = [item.sha1 for item in servico.queue()]
    assert len(antes) == 1
    sha1 = antes[0]

    servico.decide(sha1, Label.UP)
    assert servico.queue() == []

    assert servico.undo_last() is True

    depois = [item.sha1 for item in servico.queue()]
    assert depois == antes
    assert (config.inbox / "nova_0.5.mp3").is_file()
    assert not list(config.folders[Label.UP].glob("nova_0.5.mp3"))


def test_desfazer_sem_decisao_anterior_devolve_false(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    servico = _servico(config)

    assert servico.undo_last() is False


def test_desfazer_so_guarda_um_nivel(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    for nome in ("a_0.2.mp3", "b_0.8.mp3"):
        (config.inbox / nome).write_bytes(nome.encode())

    servico = _servico(config)
    servico.train()

    for item in list(servico.queue()):
        servico.decide(item.sha1, Label.UP)

    assert servico.undo_last() is True
    # A segunda chamada nao tem mais o que desfazer: a pilha e de um nivel.
    assert servico.undo_last() is False
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/test_service.py -k desfazer -v`
Expected: FAIL com `AttributeError: 'TrackService' object has no attribute 'undo_last'`

- [ ] **Step 7: Implement in the service**

Em `service.py`, acrescentar o import e o dataclass:

```python
from .apply import FileVanishedError, move_to_folder, undo_move


@dataclass(frozen=True)
class _UltimaDecisao:
    sha1: str
    origem_dir: Path
    destino: Path
    label: Label
    posicao: int
```

No `__init__`:

```python
        self._ultima_decisao: _UltimaDecisao | None = None
```

Em `decide`, gravar a decisao logo antes de remover da fila. O trecho final do metodo passa a ser:

```python
        posicao = next(i for i, r in enumerate(self._inbox) if r.sha1 == sha1)
        self._ultima_decisao = _UltimaDecisao(
            sha1=sha1,
            origem_dir=ref.path.parent,
            destino=destino,
            label=label,
            posicao=posicao,
        )
        self._inbox = [r for r in self._inbox if r.sha1 != sha1]
        self._labeled.append(TrackRef(path=destino, label=label, sha1=ref.sha1))
        self._decisions_since_train += 1
        if self._decisions_since_train >= self.config.retrain_every:
            self.train()
            return True
        return False
```

E o metodo novo:

```python
    def undo_last(self) -> bool:
        """Devolve a ultima track decidida para a fila. Um nivel apenas.

        Nao "destreina" o modelo: o exemplo sai de _labeled, mas os pesos
        ja ajustados so mudam no proximo train(). Reverter o ajuste exigiria
        guardar o modelo anterior a cada decisao, e o efeito de um unico
        exemplo em RidgeCV nao justifica esse custo.
        """
        decisao = self._ultima_decisao
        if decisao is None:
            return False

        # Consome antes de tentar mover: seja qual for o desfecho, esta
        # decisao nao pode ser desfeita duas vezes.
        self._ultima_decisao = None

        try:
            de_volta = undo_move(decisao.destino, decisao.origem_dir)
        except FileVanishedError:
            return False

        self._labeled = [ref for ref in self._labeled if ref.sha1 != decisao.sha1]
        self._inbox.insert(
            min(decisao.posicao, len(self._inbox)),
            TrackRef(path=de_volta, label=None, sha1=decisao.sha1),
        )
        self._decisions_since_train = max(0, self._decisions_since_train - 1)
        return True
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_service.py -v && uv run ruff check .`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/trackclassifier/apply.py src/trackclassifier/service.py tests/test_apply.py tests/test_service.py
git commit -m "feat(trackclassifier): desfazer a ultima decisao de rotulo"
```

---

### Task 3: viewmodel puro

A fronteira que sustenta os testes do resto da fase. `viewmodel.py` traduz `TrackService` em dataclasses e **nao importa Qt** — e o que permite testar o que aparece na linha, o que a proxima tecla faz e quando a fila esvazia com `pytest` puro, sem `QApplication` e sem audio.

**Files:**
- Create: `src/trackclassifier/ui/__init__.py`
- Create: `src/trackclassifier/ui/viewmodel.py`
- Test: `tests/test_viewmodel.py`

**Interfaces:**
- Consumes: `service.TrackService.queue() -> list[QueueItem]`, `.failures() -> list[FailedItem]`, `.model.metrics_`, `.model.low_confidence_mode`, `._labeled`, `._analysis(ref)`.
- Produces:
  - `viewmodel.TrackRow` (frozen dataclass): `sha1: str`, `filename: str`, `label: str | None`, `predicted: str | None`, `score: float | None`, `confidence: float | None`, `bpm: float`, `duration_s: float`, `energy_curve: tuple[float, ...]`, `peak_offset_s: float`
  - `viewmodel.ReviewState` (frozen): `current: TrackRow | None`, `upcoming: tuple[TrackRow, ...]`, `low_confidence: bool`, `remaining: int`
  - `viewmodel.LibraryState` (frozen): `rows: tuple[TrackRow, ...]`
  - `viewmodel.ModelState` (frozen): `accuracy: float | None`, `ordinal_mae: float | None`, `confusion: tuple[tuple[int, ...], ...] | None`, `n_examples: int`, `failures: tuple[tuple[str, str], ...]`
  - `viewmodel.review_state(service) -> ReviewState`
  - `viewmodel.library_state(service) -> LibraryState`
  - `viewmodel.model_state(service) -> ModelState`
  - `viewmodel.format_duration(seconds: float) -> str`

- [ ] **Step 1: Write the failing test**

Criar `tests/test_viewmodel.py`:

```python
"""O viewmodel nao importa Qt -- estes testes rodam sem QApplication."""

import numpy as np
import pytest
import soundfile as sf

from trackclassifier.config import Config
from trackclassifier.features import TrackAnalysis
from trackclassifier.labels import Label
from trackclassifier.service import TrackService
from trackclassifier.ui import viewmodel


class ExtratorFalso:
    name = "falso-v1"

    def extract(self, path):
        energia = float(path.stem.split("_")[-1])
        return TrackAnalysis(
            vector=np.array([energia] * 4, dtype=np.float64),
            energy_curve=[energia, energia * 2, energia],
            peak_offset_s=1.0,
            bpm=120.0 + energia,
            duration_s=180.0,
        )


def _config(tmp_path) -> Config:
    pastas = {}
    for rotulo, nome in ((Label.UP, "up"), (Label.NEUTRAL, "neutral"), (Label.DOWN, "down")):
        pasta = tmp_path / nome
        pasta.mkdir()
        pastas[rotulo] = pasta
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    dados = tmp_path / "data"
    dados.mkdir()
    return Config(
        folders=pastas, inbox=inbox, data_dir=dados, retrain_every=10, min_examples=2
    )


def _servico(config) -> TrackService:
    for rotulo, base in ((Label.DOWN, 0.1), (Label.NEUTRAL, 0.5), (Label.UP, 0.9)):
        for i in range(3):
            nome = f"r{i}_{base}.wav"
            sf.write(config.folders[rotulo] / nome, np.zeros(100), 22050)
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()
    return servico


def test_format_duration_usa_minutos_e_segundos():
    assert viewmodel.format_duration(0) == "0:00"
    assert viewmodel.format_duration(65) == "1:05"
    assert viewmodel.format_duration(3599) == "59:59"


def test_review_state_vazio_quando_a_inbox_esta_vazia(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    estado = viewmodel.review_state(servico)

    assert estado.current is None
    assert estado.upcoming == ()
    assert estado.remaining == 0


def test_review_state_traz_a_atual_e_ate_tres_proximas(tmp_path):
    config = _config(tmp_path)
    for i in range(5):
        sf.write(config.inbox / f"n{i}_0.{i}.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    estado = viewmodel.review_state(servico)

    assert estado.current is not None
    assert estado.remaining == 5
    assert len(estado.upcoming) == 3
    # A fila do servico ja vem ordenada por confianca crescente; o viewmodel
    # nao reordena -- so fatia.
    fila = servico.queue()
    assert estado.current.sha1 == fila[0].sha1
    assert [linha.sha1 for linha in estado.upcoming] == [item.sha1 for item in fila[1:4]]


def test_track_row_carrega_os_dados_de_apresentacao(tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    linha = viewmodel.review_state(servico).current

    assert linha.filename == "nova_0.7.wav"
    assert linha.bpm == pytest.approx(120.7)
    assert linha.duration_s == pytest.approx(180.0)
    assert linha.energy_curve == (0.7, 1.4, 0.7)
    assert linha.peak_offset_s == pytest.approx(1.0)
    assert linha.predicted in {"-1", "neutra", "+1"}
    assert 0.0 <= linha.confidence <= 1.0
    assert linha.label is None


def test_library_state_traz_as_rotuladas_com_o_rotulo(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    estado = viewmodel.library_state(servico)

    assert len(estado.rows) == 9
    assert {linha.label for linha in estado.rows} == {"-1", "neutra", "+1"}
    assert all(linha.predicted is None for linha in estado.rows)


def test_model_state_antes_do_treino_nao_tem_metricas(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    estado = viewmodel.model_state(servico)

    assert estado.accuracy is None
    assert estado.confusion is None
    assert estado.n_examples == 0


def test_model_state_depois_do_treino_traz_as_metricas(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    estado = viewmodel.model_state(servico)

    assert 0.0 <= estado.accuracy <= 1.0
    assert len(estado.confusion) == 3
    assert estado.n_examples == 9


def test_model_state_expoe_as_falhas(tmp_path):
    config = _config(tmp_path)
    (config.inbox / "quebrada_x.wav").write_bytes(b"nao e audio")
    servico = _servico(config)

    estado = viewmodel.model_state(servico)

    assert any(nome == "quebrada_x.wav" for nome, _motivo in estado.failures)


def test_viewmodel_nao_importa_qt():
    import pathlib

    fonte = pathlib.Path(viewmodel.__file__).read_text(encoding="utf-8")
    assert "PySide6" not in fonte
    assert "QtCore" not in fonte
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_viewmodel.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.ui'`

- [ ] **Step 3: Create the package and the module**

Criar `src/trackclassifier/ui/__init__.py` vazio.

Criar `src/trackclassifier/ui/viewmodel.py`:

```python
"""Traducao de TrackService para dados de tela.

Este modulo nao importa Qt, e isso e regra de fronteira, nao acaso: e o
que permite testar a logica de tela -- o que aparece na linha, quantas
faltam, quando a fila esvazia -- com pytest puro, sem QApplication e sem
dispositivo de audio.
"""

from dataclasses import dataclass

from ..service import TrackService

#: Quantas proximas mostrar no rodape da aba Revisao.
PROXIMAS = 3


@dataclass(frozen=True)
class TrackRow:
    sha1: str
    filename: str
    label: str | None
    predicted: str | None
    score: float | None
    confidence: float | None
    bpm: float
    duration_s: float
    energy_curve: tuple[float, ...]
    peak_offset_s: float


@dataclass(frozen=True)
class ReviewState:
    current: TrackRow | None
    upcoming: tuple[TrackRow, ...]
    low_confidence: bool
    remaining: int


@dataclass(frozen=True)
class LibraryState:
    rows: tuple[TrackRow, ...]


@dataclass(frozen=True)
class ModelState:
    accuracy: float | None
    ordinal_mae: float | None
    confusion: tuple[tuple[int, ...], ...] | None
    n_examples: int
    failures: tuple[tuple[str, str], ...]


def format_duration(seconds: float) -> str:
    total = int(max(0.0, seconds))
    return f"{total // 60}:{total % 60:02d}"


def _row_da_fila(item) -> TrackRow:
    return TrackRow(
        sha1=item.sha1,
        filename=item.filename,
        label=None,
        predicted=item.label.value,
        score=item.score,
        confidence=item.confidence,
        bpm=item.bpm,
        duration_s=item.duration_s,
        energy_curve=tuple(item.energy_curve),
        peak_offset_s=item.peak_offset_s,
    )


def review_state(service: TrackService) -> ReviewState:
    fila = service.queue()
    if not fila:
        return ReviewState(
            current=None,
            upcoming=(),
            low_confidence=service.model.low_confidence_mode,
            remaining=0,
        )
    return ReviewState(
        current=_row_da_fila(fila[0]),
        upcoming=tuple(_row_da_fila(item) for item in fila[1 : 1 + PROXIMAS]),
        low_confidence=service.model.low_confidence_mode,
        remaining=len(fila),
    )


def library_state(service: TrackService) -> LibraryState:
    linhas = []
    for ref in service._labeled:
        analise = service._analysis(ref)
        linhas.append(
            TrackRow(
                sha1=ref.sha1,
                filename=ref.path.name,
                label=ref.label.value if ref.label is not None else None,
                predicted=None,
                score=None,
                confidence=None,
                bpm=analise.bpm,
                duration_s=analise.duration_s,
                energy_curve=tuple(analise.energy_curve),
                peak_offset_s=analise.peak_offset_s,
            )
        )
    return LibraryState(rows=tuple(linhas))


def model_state(service: TrackService) -> ModelState:
    metricas = service.model.metrics_
    falhas = tuple((falha.filename, falha.reason) for falha in service.failures())
    if metricas is None:
        return ModelState(
            accuracy=None,
            ordinal_mae=None,
            confusion=None,
            n_examples=0,
            failures=falhas,
        )
    return ModelState(
        accuracy=metricas.accuracy,
        ordinal_mae=metricas.ordinal_mae,
        confusion=tuple(tuple(linha) for linha in metricas.confusion),
        n_examples=metricas.n_examples,
        failures=falhas,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_viewmodel.py -v && uv run ruff check .`
Expected: PASS, 10 testes

- [ ] **Step 5: Commit**

```bash
git add src/trackclassifier/ui/__init__.py src/trackclassifier/ui/viewmodel.py tests/test_viewmodel.py
git commit -m "feat(ui): viewmodel puro traduzindo TrackService para dados de tela"
```

---

### Task 4: Pipeline de tokens e dependencia PySide6

`design-tokens.json` e a fonte unica de verdade. QSS nao tem variaveis, entao a expansao e obrigatoria — e esquecer de regenerar e o modo de falha mais provavel do design system. O teste desta task existe para pegar exatamente isso.

**Files:**
- Create: `design/design-tokens.json` (copia de `~/Downloads/trackclassifier/design-tokens.json`)
- Create: `design/build_tokens.py`
- Create: `src/trackclassifier/ui/tokens.py` (gerado)
- Create: `src/trackclassifier/ui/app.qss` (gerado)
- Modify: `pyproject.toml`
- Test: `tests/test_tokens.py`

**Interfaces:**
- Produces: `ui.tokens` com constantes `COLOR_SURFACE_0`, `COLOR_TEXT_PRIMARY`, `COLOR_TEXT_SECONDARY`, `COLOR_TEXT_MUTED`, `COLOR_ACCENT_BASE`, `COLOR_SURFACE_WAVEFORM`, `COLOR_WAVEBAND_PLAYHEAD`, `COLOR_WAVEBAND_FLOOR`, `COLOR_CLASSIFICATION_ANIMADA_BG` (e irmas), `SIZE_ROW_COMFORTABLE`, `SIZE_WAVE_ROW`, `SIZE_WAVE_BAR`, `SIZE_WAVE_PLAYER`, `SPACE_4` etc., mais `classification_colors(label) -> tuple[str, str]`.

- [ ] **Step 1: Copy the token source and adapt the generator**

```bash
mkdir -p design
cp ~/Downloads/trackclassifier/design-tokens.json design/design-tokens.json
cp ~/Downloads/trackclassifier/build_tokens.py design/build_tokens.py
```

Em `design/build_tokens.py`, trocar os caminhos de saida e remover a geracao de CSS (nao ha web). Substituir o bloco `main()` inteiro por:

```python
ROOT = Path(__file__).parent
SRC = ROOT / "design-tokens.json"
OUT = ROOT.parent / "src" / "trackclassifier" / "ui"


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    tokens = flatten(data)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tokens.py").write_text(build_py(tokens), encoding="utf-8")
    (OUT / "app.qss").write_text(build_qss(tokens), encoding="utf-8")

    print(f"{len(tokens)} tokens -> ui/tokens.py, ui/app.qss")
```

Remover a funcao `build_css` e a linha que escrevia `tokens.css`. Remover tambem `camelot_color` e `band_rgb` do `build_py` — key e RGB sao fases 3 e 4; `classification_colors` fica.

> Atencao ao mapa de `classification_colors`: as chaves geradas sao `animada`/`neutro`/`lento`, que sao os nomes do design system. Os rotulos do dominio sao `+1`/`neutra`/`-1` (`labels.Label`). A traducao entre os dois acontece no delegate (Task 5), **nao** aqui — `tokens.py` e gerado e nao pode conhecer o dominio.

- [ ] **Step 2: Generate and inspect**

Run: `uv run python design/build_tokens.py`
Expected: `... tokens -> ui/tokens.py, ui/app.qss`

Conferir que `src/trackclassifier/ui/tokens.py` comeca com o banner de gerado e contem `SIZE_ROW_COMFORTABLE: Final = 46`.

- [ ] **Step 3: Write the regeneration test**

Criar `tests/test_tokens.py`:

```python
"""Guarda o modo de falha mais provavel do design system: editar o JSON e
esquecer de rodar build_tokens.py, deixando tokens.py e app.qss velhos."""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GERADOS = [
    RAIZ / "src" / "trackclassifier" / "ui" / "tokens.py",
    RAIZ / "src" / "trackclassifier" / "ui" / "app.qss",
]


def test_arquivos_gerados_estao_em_dia_com_o_json():
    antes = {caminho: caminho.read_text(encoding="utf-8") for caminho in GERADOS}

    subprocess.run(
        [sys.executable, str(RAIZ / "design" / "build_tokens.py")],
        check=True,
        capture_output=True,
    )

    for caminho, conteudo in antes.items():
        assert caminho.read_text(encoding="utf-8") == conteudo, (
            f"{caminho.name} esta dessincronizado de design-tokens.json. "
            "Rode: uv run python design/build_tokens.py"
        )


def test_nenhum_hex_fora_do_json():
    """Nenhum literal de cor pode existir fora dos tokens."""
    import re

    padrao = re.compile(r"#[0-9A-Fa-f]{6}\b")
    ui = RAIZ / "src" / "trackclassifier" / "ui"
    permitidos = {ui / "tokens.py", ui / "app.qss"}

    ofensores = []
    for caminho in ui.rglob("*.py"):
        if caminho in permitidos:
            continue
        for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
            if padrao.search(linha):
                ofensores.append(f"{caminho.relative_to(RAIZ)}:{numero}")

    assert ofensores == [], f"hex fora de design-tokens.json: {ofensores}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tokens.py -v`
Expected: PASS, 2 testes

- [ ] **Step 5: Add the PySide6 dependency**

Em `pyproject.toml`, acrescentar a `dependencies`:

```toml
    "PySide6-Essentials>=6.7",
```

E o extra opcional, junto de `dev`:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "soundfile>=0.12", "httpx>=0.27", "ruff>=0.6"]
audio = ["PySide6-Addons>=6.7"]
```

E a variavel de ambiente do pytest, no bloco que ja existe:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "."]
env = []
```

> `pytest-env` nao esta nas deps. Em vez de acrescentar um plugin so para isto, definir a plataforma em `tests/conftest.py` (proximo passo) — funciona sem dependencia nova e vale tambem para quem roda `pytest` direto.

- [ ] **Step 6: Force the offscreen platform for every test run**

Criar `tests/conftest.py` (ou acrescentar, se ja existir):

```python
import os

# Precisa acontecer antes de qualquer import de PySide6: o Qt le a variavel
# na criacao do QApplication e o CI nao tem display. Em conftest.py porque
# aqui roda antes da coleta dos modulos de teste.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

- [ ] **Step 7: Run the full suite and commit**

Run: `uv sync --extra dev && uv run pytest -q && uv run ruff check .`
Expected: PASS

```bash
git add design/ src/trackclassifier/ui/tokens.py src/trackclassifier/ui/app.qss pyproject.toml uv.lock tests/test_tokens.py tests/conftest.py
git commit -m "feat(ui): pipeline de design tokens e dependencia PySide6"
```

---

### Task 5: Render da waveform mono e delegates

Fase 1 desenha a onda a partir do `energy_curve` que `TrackAnalysis` ja carrega — mono, ainda nao RGB. A estrutura de cache vem do ref2, mas **com a chave corrigida**: o ref2 chaveia por `track.path`, e neste repo o arquivo muda de pasta a cada decisao, o que invalidaria o cache inteiro depois de uma sessao de revisao. A chave e o sha1.

**Files:**
- Create: `src/trackclassifier/ui/widgets/__init__.py`
- Create: `src/trackclassifier/ui/widgets/waveform_render.py`
- Create: `src/trackclassifier/ui/widgets/delegates.py`
- Test: `tests/test_waveform_render.py`

**Interfaces:**
- Consumes: `ui.tokens` (Task 4), `ui.viewmodel.TrackRow` (Task 3).
- Produces:
  - `waveform_render.render_curve(curve: tuple[float, ...], size: QSize, bar_width: int = 2, gap: int = 0, background: QColor | None = None) -> QPixmap`
  - `waveform_render.PixmapCache(capacity: int = 256)` com `get(key) -> QPixmap | None`, `put(key, pixmap) -> None`, `clear() -> None`; chave e `tuple[str, int, int]` = `(sha1, width, height)`
  - `delegates.WaveformDelegate(parent, margin: int = 4)` com `clear_cache() -> None`
  - `delegates.ClassificationDelegate(parent)`
  - `delegates.TRACK_ROLE: int`

- [ ] **Step 1: Write the failing test**

Criar `tests/test_waveform_render.py`:

```python
from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap

from trackclassifier.ui.widgets.waveform_render import PixmapCache, render_curve


def test_render_devolve_pixmap_do_tamanho_pedido():
    pixmap = render_curve((0.1, 0.5, 0.9, 0.4), QSize(120, 18))

    assert isinstance(pixmap, QPixmap)
    assert pixmap.width() == 120
    assert pixmap.height() == 18


def test_render_de_curva_vazia_nao_quebra():
    pixmap = render_curve((), QSize(50, 10))

    assert pixmap.width() == 50
    assert pixmap.height() == 10


def test_render_normaliza_pelo_maximo_da_curva():
    """Duas curvas com a mesma forma e escalas diferentes desenham igual.

    A energia absoluta varia muito entre tracks masterizadas de formas
    diferentes; sem normalizar, uma track baixa viraria uma linha reta.
    """
    baixa = render_curve((0.01, 0.02, 0.01), QSize(40, 20))
    alta = render_curve((0.5, 1.0, 0.5), QSize(40, 20))

    assert baixa.toImage() == alta.toImage()


def test_cache_devolve_o_mesmo_pixmap_para_a_mesma_chave():
    cache = PixmapCache(capacity=4)
    chave = ("abc123", 100, 18)
    pixmap = render_curve((0.5, 1.0), QSize(100, 18))

    cache.put(chave, pixmap)

    assert cache.get(chave) is pixmap
    assert cache.get(("outro", 100, 18)) is None


def test_cache_descarta_o_menos_usado_ao_estourar():
    cache = PixmapCache(capacity=2)
    pixmap = render_curve((0.5,), QSize(10, 10))

    cache.put(("a", 10, 10), pixmap)
    cache.put(("b", 10, 10), pixmap)
    cache.get(("a", 10, 10))          # 'a' passa a ser o mais recente
    cache.put(("c", 10, 10), pixmap)  # estoura: sai 'b'

    assert cache.get(("a", 10, 10)) is pixmap
    assert cache.get(("b", 10, 10)) is None
    assert cache.get(("c", 10, 10)) is pixmap


def test_cache_e_chaveado_por_sha1_e_nao_por_caminho():
    """Regressao: o arquivo muda de pasta a cada decisao de rotulo.

    Se a chave fosse o caminho, classificar uma track invalidaria a entrada
    dela e a Biblioteca repintaria tudo depois de uma sessao de revisao.
    """
    cache = PixmapCache(capacity=4)
    pixmap = render_curve((0.5, 1.0), QSize(100, 18))
    cache.put(("sha1abc", 100, 18), pixmap)

    # Mesmo sha1, arquivo agora em outra pasta: segue sendo hit.
    assert cache.get(("sha1abc", 100, 18)) is pixmap
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_waveform_render.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.ui.widgets'`

- [ ] **Step 3: Write the implementation**

Criar `src/trackclassifier/ui/widgets/__init__.py` vazio.

Criar `src/trackclassifier/ui/widgets/waveform_render.py`:

```python
"""Render da onda. Um so lugar, usado pela onda grande e pela mini.

Fase 1 desenha mono, a partir do energy_curve que TrackAnalysis ja
carrega. O render RGB por banda (graves no vermelho, medios no verde,
agudos no azul) entra na fase 3, quando existir o dado por banda.
"""

from collections import OrderedDict

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from ..tokens import COLOR_ACCENT_BASE, COLOR_SURFACE_WAVEFORM

_EPS = 1e-9


def _resample(curva: np.ndarray, barras: int) -> np.ndarray:
    """Reduz N pontos para `barras` pegando o maximo de cada bucket.

    Maximo e nao media de proposito: media achata transientes e a onda
    perde justamente a informacao de ataque que o DJ procura.
    """
    if barras <= 0 or len(curva) == 0:
        return np.zeros(max(0, barras), dtype=np.float32)
    if len(curva) <= barras:
        return np.pad(curva, (0, barras - len(curva)), mode="edge").astype(np.float32)

    bordas = np.linspace(0, len(curva), barras + 1, dtype=int)
    return np.asarray(
        [curva[bordas[i] : bordas[i + 1]].max() for i in range(barras)], dtype=np.float32
    )


def render_curve(
    curve: tuple[float, ...],
    size: QSize,
    bar_width: int = 2,
    gap: int = 0,
    background: QColor | None = None,
) -> QPixmap:
    """Desenha a curva de energia num QPixmap do tamanho pedido.

    Chame uma vez por track e guarde o resultado. Redesenhar dentro de
    paint() com dezenas de linhas visiveis derruba o scroll.
    """
    largura = max(1, size.width())
    altura = max(1, size.height())

    imagem = QImage(largura, altura, QImage.Format.Format_ARGB32_Premultiplied)
    imagem.fill(background if background is not None else QColor(COLOR_SURFACE_WAVEFORM))

    curva = np.asarray(curve, dtype=np.float32)
    if curva.size:
        passo = max(1, bar_width + gap)
        barras = max(1, largura // passo)
        amostras = _resample(curva, barras)
        # Normaliza pelo proprio maximo: a energia absoluta varia muito entre
        # masterizacoes, e sem isto uma track baixa vira uma linha reta.
        amplitude = np.clip(amostras / (float(amostras.max()) + _EPS), 0.0, 1.0)

        cor = QColor(COLOR_ACCENT_BASE)
        pintor = QPainter(imagem)
        pintor.setPen(Qt.PenStyle.NoPen)
        for i in range(barras):
            altura_barra = max(1.0, float(amplitude[i]) * altura)
            y = (altura - altura_barra) / 2.0
            pintor.fillRect(
                int(i * passo), int(y), bar_width, int(round(altura_barra)), cor
            )
        pintor.end()

    return QPixmap.fromImage(imagem)


class PixmapCache:
    """LRU de pixmaps por (sha1, largura, altura).

    A chave e o sha1, nao o caminho: decidir um rotulo MOVE o arquivo de
    pasta, e uma chave por caminho invalidaria a entrada de toda track
    classificada -- a Biblioteca repintaria tudo depois de uma sessao de
    revisao, que e exatamente o engasgo que este cache existe para evitar.
    O tamanho entra na chave porque redimensionar a coluna invalida o
    render. Capacidade baixa de proposito: so precisa cobrir o viewport
    mais a margem de scroll, nao a biblioteca inteira.
    """

    def __init__(self, capacity: int = 256) -> None:
        self._capacity = capacity
        self._items: OrderedDict[tuple[str, int, int], QPixmap] = OrderedDict()

    def get(self, key: tuple[str, int, int]) -> QPixmap | None:
        pixmap = self._items.get(key)
        if pixmap is not None:
            self._items.move_to_end(key)
        return pixmap

    def put(self, key: tuple[str, int, int], pixmap: QPixmap) -> None:
        self._items[key] = pixmap
        self._items.move_to_end(key)
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_waveform_render.py -v`
Expected: PASS, 6 testes

- [ ] **Step 5: Write the delegates**

Criar `src/trackclassifier/ui/widgets/delegates.py`:

```python
"""Delegates da tabela. Tudo que QSS nao alcanca e pintado aqui."""

from PySide6.QtCore import QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QWidget

from ..tokens import SIZE_WAVE_BAR, classification_colors
from ..viewmodel import TrackRow
from .waveform_render import PixmapCache, render_curve

#: Role customizado: os delegates pedem a TrackRow inteira por aqui, em vez
#: de reconstruir dados a partir das strings de DisplayRole.
TRACK_ROLE = Qt.ItemDataRole.UserRole + 1

#: Rotulo do dominio (labels.Label) -> nome do chip no design system.
#: A traducao mora aqui porque tokens.py e gerado e nao pode conhecer o
#: dominio, e viewmodel.py nao pode conhecer o design system.
_CHIP = {"+1": "animada", "neutra": "neutro", "-1": "lento"}
_TEXTO = {"+1": "+1", "neutra": "neutra", "-1": "-1"}


class WaveformDelegate(QStyledItemDelegate):
    """Pinta a mini onda da linha a partir da curva ja calculada.

    O pixmap e cacheado por (sha1, largura, altura). O paint() nunca
    decodifica audio nem recalcula a curva -- so faz drawPixmap.
    """

    def __init__(self, parent: QWidget | None = None, margin: int = 4) -> None:
        super().__init__(parent)
        self._cache = PixmapCache(capacity=256)
        self._margin = margin

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None or not linha.energy_curve:
            return

        rect = option.rect.adjusted(
            self._margin, self._margin, -self._margin, -self._margin
        )
        if rect.width() <= 0 or rect.height() <= 0:
            return

        chave = (linha.sha1, rect.width(), rect.height())
        pixmap = self._cache.get(chave)
        if pixmap is None:
            pixmap = render_curve(
                linha.energy_curve,
                QSize(rect.width(), rect.height()),
                bar_width=SIZE_WAVE_BAR,
                gap=0,
            )
            self._cache.put(chave, pixmap)

        painter.drawPixmap(rect.topLeft(), pixmap)

    def clear_cache(self) -> None:
        self._cache.clear()


class ClassificationDelegate(QStyledItemDelegate):
    """Chip do rotulo: fundo em tint escuro e texto claro da mesma matiz.

    Preenchimento saturado atras de texto de 11px reprova em contraste;
    tint mais texto claro passa AA com folga.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius = 4.0
        self._padding_h = 8
        self._padding_v = 3

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None:
            return
        rotulo = linha.label or linha.predicted
        if rotulo is None:
            return

        fundo, frente = classification_colors(_CHIP[rotulo])
        texto = _TEXTO[rotulo]

        metricas = QFontMetrics(option.font)
        largura = metricas.horizontalAdvance(texto) + self._padding_h * 2
        altura = metricas.height() + self._padding_v * 2

        chip = QRect(0, 0, largura, altura)
        chip.moveCenter(option.rect.center())

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(fundo))
        painter.drawRoundedRect(chip, self._radius, self._radius)
        painter.setPen(QColor(frente))
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, texto)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(96, 24)
```

- [ ] **Step 6: Run the suite and commit**

Run: `uv run pytest -q && uv run ruff check .`
Expected: PASS

```bash
git add src/trackclassifier/ui/widgets/ tests/test_waveform_render.py
git commit -m "feat(ui): render mono da onda com cache LRU chaveado por sha1"
```

---

### Task 6: Player com fallback simulado

Portado do ref2 sem mudanca de contrato. O `SimulatedPlayer` nao e so conveniencia de teste: e o que torna a UI exercitavel no CI sem `PySide6-Addons` e sem dispositivo de audio.

**Files:**
- Create: `src/trackclassifier/ui/widgets/player.py`
- Test: `tests/test_player.py`

**Interfaces:**
- Produces:
  - `player.BasePlayer` (QObject) com sinais `position_changed(int)`, `duration_changed(int)`, `playing_changed(bool)`, `track_finished()`, `error_occurred(str)`; metodos `load(path, duration_ms=None)`, `play()`, `pause()`, `stop()`, `seek(ms)`, `set_volume(float)`, `toggle()`, `seek_fraction(float)`; propriedades `is_playing`, `duration_ms`, `position_ms`
  - `player.SimulatedPlayer`, `player.QtAudioPlayer`, `player.create_player(parent=None) -> BasePlayer`, `player.MULTIMEDIA_AVAILABLE: bool`

- [ ] **Step 1: Copy the module**

```bash
cp ~/Downloads/trackclassifier2/player.py src/trackclassifier/ui/widgets/player.py
```

Ajustes obrigatorios no arquivo copiado:
- Nao ha imports relativos a corrigir (o modulo nao importa nada do projeto).
- Conferir que a docstring do topo nao tem acentos; trocar `"simulacao"`/`"reproducao"` se algum acento tiver sobrado.

- [ ] **Step 2: Write the failing test**

Criar `tests/test_player.py`:

```python
from pathlib import Path

from trackclassifier.ui.widgets.player import SimulatedPlayer, create_player


def test_create_player_devolve_um_backend(qapp):
    assert create_player() is not None


def test_simulated_player_comeca_parado_no_zero(qapp):
    player = SimulatedPlayer()
    player.load(Path("qualquer.wav"), duration_ms=10_000)

    assert player.is_playing is False
    assert player.position_ms == 0
    assert player.duration_ms == 10_000


def test_simulated_player_nao_toca_sem_duracao(qapp):
    player = SimulatedPlayer()
    player.load(Path("qualquer.wav"), duration_ms=0)
    player.play()

    assert player.is_playing is False


def test_seek_fraction_converte_proporcao_em_milissegundos(qapp):
    player = SimulatedPlayer()
    player.load(Path("qualquer.wav"), duration_ms=10_000)

    player.seek_fraction(0.25)
    assert player.position_ms == 2_500

    # Fora de [0,1] satura em vez de estourar -- a onda emite a proporcao
    # do clique, e um clique na borda pode passar de 1 por um pixel.
    player.seek_fraction(1.5)
    assert player.position_ms == 10_000
    player.seek_fraction(-0.5)
    assert player.position_ms == 0


def test_toggle_alterna_play_e_pause(qapp):
    player = SimulatedPlayer()
    player.load(Path("qualquer.wav"), duration_ms=10_000)

    player.toggle()
    assert player.is_playing is True
    player.toggle()
    assert player.is_playing is False


def test_stop_volta_para_o_inicio(qapp):
    player = SimulatedPlayer()
    player.load(Path("qualquer.wav"), duration_ms=10_000)
    player.seek(5_000)

    player.stop()

    assert player.position_ms == 0
    assert player.is_playing is False
```

- [ ] **Step 3: Add the qapp fixture**

Acrescentar a `tests/conftest.py`:

```python
import pytest


@pytest.fixture(scope="session")
def qapp():
    """QApplication unica para a sessao inteira.

    O Qt aceita apenas uma instancia por processo, e destrui-la entre
    testes deixa widgets orfaos que derrubam a coleta seguinte.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_player.py -v`
Expected: PASS, 6 testes

- [ ] **Step 5: Commit**

```bash
git add src/trackclassifier/ui/widgets/player.py tests/test_player.py tests/conftest.py
git commit -m "feat(ui): player com fallback simulado quando falta QtMultimedia"
```

---

### Task 7: Worker — a QThread dona do servico

Regra unica de concorrencia: **uma `QThread` e dona do `TrackService`**. Todo acesso acontece nela; a UI envia pedidos e recebe sinais. Consequencia: sem lock, sem servico compartilhado entre threads, sem parquet escrito de dois lugares.

**Files:**
- Create: `src/trackclassifier/ui/worker.py`
- Test: `tests/test_worker.py`

**Interfaces:**
- Consumes: `service.TrackService`, `ui.viewmodel.review_state/library_state/model_state`.
- Produces: `worker.ServiceWorker(service: TrackService)` (QObject, movido para uma QThread) com:
  - slots `scan()`, `decide(sha1: str, label: str)`, `undo()`, `train()`, `refresh()`, `bulk_approve(min_confidence: float)`, `cancel_scan()`
  - sinais `scan_progress(int, int, str)`, `scan_finished()`, `states_changed(object, object, object)` (ReviewState, LibraryState, ModelState), `error(str)`, `retrained()`
  - `worker.ServiceThread(service)` — embrulha `QThread` + `ServiceWorker`, com `start()`, `stop()` e a propriedade `worker`

- [ ] **Step 1: Write the failing test**

Criar `tests/test_worker.py`:

```python
"""O worker e testado chamando os slots direto, sem thread.

Mover para uma QThread e responsabilidade de ServiceThread; a logica dos
slots nao depende disso e testa-la sem thread evita flakiness de timing.
"""

import numpy as np
import soundfile as sf

from trackclassifier.ui.viewmodel import LibraryState, ModelState, ReviewState
from trackclassifier.ui.worker import ServiceWorker
from tests.test_viewmodel import _config, _servico


def test_refresh_emite_os_tres_estados(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    worker = ServiceWorker(servico)
    recebidos = []
    worker.states_changed.connect(lambda r, b, m: recebidos.append((r, b, m)))

    worker.refresh()

    assert len(recebidos) == 1
    revisao, biblioteca, modelo = recebidos[0]
    assert isinstance(revisao, ReviewState)
    assert isinstance(biblioteca, LibraryState)
    assert isinstance(modelo, ModelState)
    assert modelo.n_examples == 9


def test_decide_move_o_arquivo_e_reemite_os_estados(qapp, tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    worker = ServiceWorker(servico)
    recebidos = []
    worker.states_changed.connect(lambda r, b, m: recebidos.append(r))

    sha1 = servico.queue()[0].sha1
    worker.decide(sha1, "+1")

    assert recebidos[-1].current is None
    assert (config.folders_up_glob := list(config.folders[__import__(
        "trackclassifier.labels", fromlist=["Label"]).Label.UP].glob("nova_0.7.wav")))
    assert config.folders_up_glob


def test_undo_devolve_a_track_e_reemite(qapp, tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    worker = ServiceWorker(servico)
    sha1 = servico.queue()[0].sha1
    worker.decide(sha1, "+1")

    recebidos = []
    worker.states_changed.connect(lambda r, b, m: recebidos.append(r))
    worker.undo()

    assert recebidos[-1].current is not None
    assert recebidos[-1].current.sha1 == sha1


def test_scan_emite_progresso_e_fim(qapp, tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)

    worker = ServiceWorker(servico)
    progresso = []
    fim = []
    worker.scan_progress.connect(lambda feitas, total, nome: progresso.append(nome))
    worker.scan_finished.connect(lambda: fim.append(True))

    worker.scan()

    assert fim == [True]


def test_train_sem_todas_as_classes_emite_error_em_vez_de_estourar(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    # Deixa so uma classe rotulada: train() deve levantar NotEnoughClassesError
    # la dentro, e o worker precisa converter isso em sinal de erro.
    servico._labeled = [ref for ref in servico._labeled if ref.label is not None][:1]

    worker = ServiceWorker(servico)
    erros = []
    worker.error.connect(erros.append)

    worker.train()

    assert len(erros) == 1
    assert "rotulos" in erros[0].lower() or "classes" in erros[0].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_worker.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.ui.worker'`

- [ ] **Step 3: Write the implementation**

Criar `src/trackclassifier/ui/worker.py`:

```python
"""A QThread dona do TrackService.

Regra unica de concorrencia desta UI: o servico vive inteiro nesta thread.
A janela nunca chama TrackService direto -- manda um pedido por slot e
recebe o resultado por sinal. E o que dispensa lock, evita duas escritas
concorrentes no parquet e mantem o ProcessPoolExecutor rodando onde ele
sempre rodou, dentro do proprio servico.
"""

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..labels import Label
from ..model import NotEnoughClassesError
from ..service import TrackService
from .viewmodel import library_state, model_state, review_state


class ServiceWorker(QObject):
    """Slots que rodam na thread do servico. Nenhum toca em widget."""

    scan_progress = Signal(int, int, str)
    scan_finished = Signal()
    states_changed = Signal(object, object, object)
    retrained = Signal()
    error = Signal(str)

    def __init__(self, service: TrackService) -> None:
        super().__init__()
        self._service = service
        self._cancelar = False

    # ---- leitura ------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        self.states_changed.emit(
            review_state(self._service),
            library_state(self._service),
            model_state(self._service),
        )

    # ---- acoes --------------------------------------------------------

    @Slot()
    def scan(self) -> None:
        self._cancelar = False

        def _progresso(concluidas: int, total: int, nome: str) -> None:
            self.scan_progress.emit(concluidas, total, nome)

        try:
            self._service.analyze_all(on_progress=_progresso)
        except Exception as erro:
            # O servico ja contem falha de item e falha de pool; chegar aqui
            # significa algo fora disso (config quebrada, disco cheio no save).
            # Vira mensagem na status bar, nunca derruba a janela.
            self.error.emit(str(erro))
        self.refresh()
        self.scan_finished.emit()

    @Slot()
    def cancel_scan(self) -> None:
        self._cancelar = True

    @Slot(str, str)
    def decide(self, sha1: str, label: str) -> None:
        try:
            retreinou = self._service.decide(sha1, Label(label))
        except Exception as erro:
            self.error.emit(str(erro))
            self.refresh()
            return
        if retreinou:
            self.retrained.emit()
        self.refresh()

    @Slot()
    def undo(self) -> None:
        if not self._service.undo_last():
            self.error.emit("Nada para desfazer.")
        self.refresh()

    @Slot()
    def train(self) -> None:
        try:
            self._service.train()
        except NotEnoughClassesError as erro:
            self.error.emit(str(erro))
            return
        self.retrained.emit()
        self.refresh()

    @Slot(float)
    def bulk_approve(self, min_confidence: float) -> None:
        try:
            self._service.bulk_approve(min_confidence)
        except Exception as erro:
            self.error.emit(str(erro))
        self.refresh()


class ServiceThread:
    """Embrulha QThread + ServiceWorker para a janela nao lidar com os dois."""

    def __init__(self, service: TrackService) -> None:
        self._thread = QThread()
        self.worker = ServiceWorker(service)
        self.worker.moveToThread(self._thread)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._thread.quit()
        # Espera de verdade: sair com a thread viva enquanto o servico
        # escreve o parquet deixaria o arquivo pela metade.
        self._thread.wait()
```

- [ ] **Step 4: Fix the sloppy assertion in the test**

O `test_decide_move_o_arquivo_e_reemite_os_estados` do Step 1 usa um import inline ilegivel. Substituir por:

```python
def test_decide_move_o_arquivo_e_reemite_os_estados(qapp, tmp_path):
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    worker = ServiceWorker(servico)
    recebidos = []
    worker.states_changed.connect(lambda r, b, m: recebidos.append(r))

    sha1 = servico.queue()[0].sha1
    worker.decide(sha1, "+1")

    assert recebidos[-1].current is None
    assert list(config.folders[Label.UP].glob("nova_0.7.wav"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_worker.py -v && uv run ruff check .`
Expected: PASS, 5 testes

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/ui/worker.py tests/test_worker.py
git commit -m "feat(ui): QThread dona do TrackService com slots e sinais"
```

---

### Task 8: Janela, tres abas e atalhos

**Files:**
- Create: `src/trackclassifier/ui/widgets/track_model.py`
- Create: `src/trackclassifier/ui/widgets/waveform_view.py`
- Create: `src/trackclassifier/ui/review_tab.py`
- Create: `src/trackclassifier/ui/library_tab.py`
- Create: `src/trackclassifier/ui/model_tab.py`
- Create: `src/trackclassifier/ui/window.py`
- Create: `src/trackclassifier/ui/__main__.py`
- Test: `tests/test_window.py`

**Interfaces:**
- Consumes: `ui.viewmodel` (Task 3), `ui.tokens` (Task 4), `ui.widgets.delegates` e `waveform_render` (Task 5), `ui.widgets.player` (Task 6), `ui.worker.ServiceThread` (Task 7).
- Produces:
  - `widgets.track_model.Column` (IntEnum): `WAVEFORM=0`, `ARQUIVO=1`, `BPM=2`, `CLASSIFICACAO=3`, `CONFIANCA=4`, `DURACAO=5`
  - `widgets.track_model.TrackTableModel(rows: list[TrackRow] | None = None)` com `set_rows(rows)`, `row_at(i) -> TrackRow | None`, `rowCount()`, `sort(column, order)`
  - `widgets.waveform_view.WaveformView` com `set_row(row: TrackRow | None)`, `set_progress(fraction: float)`, sinal `seek_requested(float)`
  - `review_tab.ReviewTab(player)` com `set_state(state: ReviewState)`, sinais `decide_requested(str, str)`, `undo_requested()`, `skip_requested()`, `back_requested()`, `bulk_approve_requested(float)`
  - `library_tab.LibraryTab()` com `set_state(state: LibraryState)`, sinal `decide_requested(str, str)`
  - `model_tab.ModelTab()` com `set_state(state: ModelState)`, sinal `train_requested()`
  - `window.MainWindow(service: TrackService)`
  - `ui.__main__.main(config_path: str = "config.toml") -> int`

- [ ] **Step 1: Write the failing smoke test**

Criar `tests/test_window.py`:

```python
"""Fumaca da janela: abre, carrega, aperta 1/2/3, fecha.

Roda com QT_QPA_PLATFORM=offscreen (conftest) e SimulatedPlayer, entao nao
precisa de display nem de dispositivo de audio.
"""

import numpy as np
import soundfile as sf
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from trackclassifier.ui.viewmodel import library_state, model_state, review_state
from trackclassifier.ui.widgets.track_model import Column, TrackTableModel
from trackclassifier.ui.window import MainWindow
from tests.test_viewmodel import _config, _servico


def _tecla(widget, chave):
    evento = QKeyEvent(QKeyEvent.Type.KeyPress, chave, Qt.KeyboardModifier.NoModifier)
    widget.keyPressEvent(evento)


def test_table_model_expoe_as_colunas_da_fase_1(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    modelo = TrackTableModel(list(library_state(servico).rows))

    assert modelo.rowCount() == 9
    assert modelo.columnCount() == len(Column)
    cabecalhos = [
        modelo.headerData(coluna, Qt.Orientation.Horizontal) for coluna in Column
    ]
    assert cabecalhos == ["Onda", "Arquivo", "BPM", "Classificacao", "Confianca", "Duracao"]


def test_table_model_ordena_por_bpm_com_none_no_fim(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    modelo = TrackTableModel(list(library_state(servico).rows))
    modelo.sort(Column.BPM, Qt.SortOrder.AscendingOrder)

    bpms = [modelo.row_at(i).bpm for i in range(modelo.rowCount())]
    assert bpms == sorted(bpms)


def test_janela_abre_com_as_tres_abas(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        assert janela.tabs.count() == 3
        assert [janela.tabs.tabText(i) for i in range(3)] == [
            "Revisao",
            "Biblioteca",
            "Modelo",
        ]
    finally:
        janela.close()


def test_tecla_3_classifica_a_atual_como_up(qapp, tmp_path):
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        assert janela.review_tab.current_sha1 is not None

        _tecla(janela.review_tab, Qt.Key.Key_3)

        assert list(config.folders[Label.UP].glob("nova_0.7.wav"))
    finally:
        janela.close()


def test_fila_vazia_mostra_estado_orientando_a_escanear(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        assert janela.review_tab.current_sha1 is None
        assert "escanear" in janela.review_tab.empty_text().lower()
    finally:
        janela.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_window.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.ui.widgets.track_model'`

- [ ] **Step 3: Write the table model**

Criar `src/trackclassifier/ui/widgets/track_model.py`:

```python
"""Modelo da tabela. Guarda a lista, nao a apresentacao.

As colunas sao as que tem dado real por tras na fase 1. Titulo, artista,
genero e key entram nas fases 2 e 4, junto com os dados que as alimentam.
"""

from enum import IntEnum
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt

from ..viewmodel import TrackRow, format_duration
from .delegates import TRACK_ROLE


class Column(IntEnum):
    WAVEFORM = 0
    ARQUIVO = 1
    BPM = 2
    CLASSIFICACAO = 3
    CONFIANCA = 4
    DURACAO = 5

    @property
    def header(self) -> str:
        return _HEADERS[self]

    @property
    def width(self) -> int:
        return _WIDTHS[self]


_HEADERS: dict[Column, str] = {
    Column.WAVEFORM: "Onda",
    Column.ARQUIVO: "Arquivo",
    Column.BPM: "BPM",
    Column.CLASSIFICACAO: "Classificacao",
    Column.CONFIANCA: "Confianca",
    Column.DURACAO: "Duracao",
}

_WIDTHS: dict[Column, int] = {
    Column.WAVEFORM: 150,
    Column.ARQUIVO: 320,
    Column.BPM: 60,
    Column.CLASSIFICACAO: 110,
    Column.CONFIANCA: 90,
    Column.DURACAO: 70,
}

_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
_CENTER = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
_LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


class TrackTableModel(QAbstractTableModel):
    def __init__(
        self, rows: list[TrackRow] | None = None, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._rows: list[TrackRow] = rows or []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(Column)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        linha = self._rows[index.row()]
        coluna = Column(index.column())

        if role == TRACK_ROLE:
            return linha

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if coluna in (Column.BPM, Column.CONFIANCA, Column.DURACAO):
                return _RIGHT
            if coluna is Column.CLASSIFICACAO:
                return _CENTER
            return _LEFT

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if coluna is Column.ARQUIVO:
            return linha.filename
        if coluna is Column.BPM:
            return f"{linha.bpm:.0f}" if linha.bpm else "—"
        if coluna is Column.CONFIANCA:
            return "—" if linha.confidence is None else f"{linha.confidence:.2f}"
        if coluna is Column.DURACAO:
            return format_duration(linha.duration_s)
        # Onda e classificacao sao pintadas pelos delegates.
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation is not Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return Column(section).header
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if Column(column) is Column.WAVEFORM:
            return  # nao ha ordem natural para uma imagem
        self.layoutAboutToBeChanged.emit()
        self._rows.sort(
            key=_sort_key(Column(column)), reverse=order is Qt.SortOrder.DescendingOrder
        )
        self.layoutChanged.emit()

    def row_at(self, row: int) -> TrackRow | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def set_rows(self, rows: list[TrackRow]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


def _sort_key(column: Column):
    """Chave de ordenacao por coluna. None sempre vai para o fim."""
    if column is Column.ARQUIVO:
        return lambda linha: linha.filename.lower()
    if column is Column.BPM:
        return lambda linha: (linha.bpm is None, linha.bpm or 0.0)
    if column is Column.CONFIANCA:
        return lambda linha: (linha.confidence is None, linha.confidence or 0.0)
    if column is Column.DURACAO:
        return lambda linha: linha.duration_s
    if column is Column.CLASSIFICACAO:
        rotulo = lambda linha: linha.label or linha.predicted  # noqa: E731
        return lambda linha: (rotulo(linha) is None, rotulo(linha) or "")
    return lambda linha: linha.filename.lower()
```

- [ ] **Step 4: Write the waveform view**

Criar `src/trackclassifier/ui/widgets/waveform_view.py`:

```python
"""Onda grande da aba Revisao, com playhead e seek por clique."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ..tokens import COLOR_SURFACE_WAVEFORM, COLOR_WAVEBAND_PLAYHEAD, SIZE_WAVE_PLAYER
from ..viewmodel import TrackRow
from .waveform_render import render_curve


class WaveformView(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(SIZE_WAVE_PLAYER)
        self._row: TrackRow | None = None
        self._progress = 0.0
        self._pixmap = None

    def set_row(self, row: TrackRow | None) -> None:
        self._row = row
        self._pixmap = None
        self._progress = 0.0
        self.update()

    def set_progress(self, fraction: float) -> None:
        self._progress = min(1.0, max(0.0, fraction))
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(600, SIZE_WAVE_PLAYER)

    def resizeEvent(self, event) -> None:
        # Invalida o render: o pixmap e do tamanho antigo.
        self._pixmap = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        pintor = QPainter(self)
        if self._row is None or not self._row.energy_curve:
            pintor.fillRect(self.rect(), QColor(COLOR_SURFACE_WAVEFORM))
            return

        if self._pixmap is None:
            self._pixmap = render_curve(self._row.energy_curve, self.size())
        pintor.drawPixmap(0, 0, self._pixmap)

        x = int(self._progress * self.width())
        pintor.setPen(QColor(COLOR_WAVEBAND_PLAYHEAD))
        pintor.drawLine(x, 0, x, self.height())

    def mousePressEvent(self, event) -> None:
        if self.width() > 0:
            self.seek_requested.emit(event.position().x() / self.width())
        super().mousePressEvent(event)
```

- [ ] **Step 5: Write the three tabs**

Criar `src/trackclassifier/ui/review_tab.py`:

```python
"""Aba Revisao: uma track por vez, decidida pelo teclado."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .viewmodel import ReviewState, format_duration
from .widgets.waveform_view import WaveformView

VAZIO = "Fila vazia. Use Escanear para procurar tracks novas na inbox."
BULK_MIN_CONFIDENCE = 0.75

#: Tecla -> rotulo do dominio. As tres sao adjacentes de proposito: a mao
#: fica parada entre decisoes.
_TECLAS = {
    Qt.Key.Key_1: "-1",
    Qt.Key.Key_2: "neutra",
    Qt.Key.Key_3: "+1",
}


class ReviewTab(QWidget):
    decide_requested = Signal(str, str)
    undo_requested = Signal()
    skip_requested = Signal()
    back_requested = Signal()
    bulk_approve_requested = Signal(float)

    def __init__(self, player, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._player = player
        self._state: ReviewState | None = None

        self._titulo = QLabel(VAZIO)
        self._titulo.setObjectName("TrackTitle")
        self._numeros = QLabel("")
        self._numeros.setObjectName("Numeric")
        self._palpite = QLabel("")
        self._aviso = QLabel("")
        self._aviso.setObjectName("SectionLabel")
        self._legenda = QLabel(
            "1 = -1   2 = neutra   3 = +1   espaco = tocar   -> pular   <- voltar   Cmd+Z = desfazer"
        )
        self._legenda.setObjectName("SectionLabel")
        self._proximas = QLabel("")
        self._proximas.setObjectName("SectionLabel")

        self._waveform = WaveformView()
        self._waveform.seek_requested.connect(self._player.seek_fraction)

        botao_bloco = QPushButton(f"Aprovar em bloco (confianca >= {BULK_MIN_CONFIDENCE})")
        botao_bloco.clicked.connect(self._pedir_bloco)

        topo = QHBoxLayout()
        topo.addWidget(self._titulo, 1)
        topo.addWidget(self._numeros)

        layout = QVBoxLayout(self)
        layout.addLayout(topo)
        layout.addWidget(self._waveform, 1)
        layout.addWidget(self._palpite)
        layout.addWidget(self._aviso)
        layout.addWidget(self._legenda)
        layout.addWidget(self._proximas)
        layout.addWidget(botao_bloco)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def current_sha1(self) -> str | None:
        return self._state.current.sha1 if self._state and self._state.current else None

    def empty_text(self) -> str:
        return VAZIO

    def set_state(self, state: ReviewState) -> None:
        self._state = state
        atual = state.current

        if atual is None:
            self._titulo.setText(VAZIO)
            self._numeros.setText("")
            self._palpite.setText("")
            self._proximas.setText("")
            self._waveform.set_row(None)
        else:
            self._titulo.setText(atual.filename)
            self._numeros.setText(
                f"{atual.bpm:.0f} BPM   {format_duration(atual.duration_s)}   "
                f"restam {state.remaining}"
            )
            self._palpite.setText(
                f"Palpite: {atual.predicted}   confianca {atual.confidence:.2f}"
            )
            self._proximas.setText(
                "Proximas: " + "   ".join(linha.filename for linha in state.upcoming)
            )
            self._waveform.set_row(atual)
            # Carrega parada no trecho mais energetico: o usuario da play.
            # Tocar sozinho a cada avanco transforma a revisao em corrida.
            self._player.load(atual.path_hint, int(atual.duration_s * 1000))
            self._player.seek(int(atual.peak_offset_s * 1000))

        self._aviso.setText(
            "Modelo com poucos exemplos: confianca reduzida pela metade."
            if state.low_confidence
            else ""
        )

    def _pedir_bloco(self) -> None:
        if self._state is None or self._state.remaining == 0:
            return
        resposta = QMessageBox.question(
            self,
            "Aprovar em bloco",
            f"Mover todas as tracks com confianca >= {BULK_MIN_CONFIDENCE}?",
        )
        if resposta == QMessageBox.StandardButton.Yes:
            self.bulk_approve_requested.emit(BULK_MIN_CONFIDENCE)

    def keyPressEvent(self, event) -> None:
        sha1 = self.current_sha1
        chave = event.key()

        if chave in _TECLAS and sha1 is not None:
            self.decide_requested.emit(sha1, _TECLAS[chave])
            return
        if chave == Qt.Key.Key_Space:
            self._player.toggle()
            return
        if chave == Qt.Key.Key_Right:
            self.skip_requested.emit()
            return
        if chave == Qt.Key.Key_Left:
            self.back_requested.emit()
            return
        if chave == Qt.Key.Key_Z and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.undo_requested.emit()
            return
        super().keyPressEvent(event)
```

> `atual.path_hint` nao existe em `TrackRow`. Acrescente o campo em `viewmodel.TrackRow` como `path_hint: str` e preencha com `str(item.path)` em `_row_da_fila` e `str(ref.path)` em `library_state`. E o unico dado de caminho que a UI precisa, e serve so para o player abrir o arquivo — a identidade continua sendo o sha1. Atualize `tests/test_viewmodel.py` para conferir `linha.path_hint.endswith("nova_0.7.wav")`.

Criar `src/trackclassifier/ui/library_tab.py`:

```python
"""Aba Biblioteca: tabela do acervo ja rotulado, com filtro e busca."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .tokens import SIZE_ROW_COMFORTABLE
from .viewmodel import LibraryState
from .widgets.delegates import ClassificationDelegate, WaveformDelegate
from .widgets.track_model import Column, TrackTableModel

_TECLAS = {Qt.Key.Key_1: "-1", Qt.Key.Key_2: "neutra", Qt.Key.Key_3: "+1"}


class LibraryTab(QWidget):
    decide_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._todas: tuple = ()

        self._busca = QLineEdit()
        self._busca.setPlaceholderText("Buscar por nome de arquivo")
        self._busca.textChanged.connect(self._reaplica_filtros)

        self._filtro = QComboBox()
        self._filtro.addItems(["Todos", "+1", "neutra", "-1"])
        self._filtro.currentTextChanged.connect(self._reaplica_filtros)

        self._model = TrackTableModel()
        self._table = self._monta_tabela()

        barra = QHBoxLayout()
        barra.addWidget(self._busca, 1)
        barra.addWidget(self._filtro)

        layout = QVBoxLayout(self)
        layout.addLayout(barra)
        layout.addWidget(self._table, 1)

    def _monta_tabela(self) -> QTableView:
        tabela = QTableView()
        tabela.setModel(self._model)
        tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabela.setShowGrid(False)
        tabela.setSortingEnabled(True)
        tabela.setWordWrap(False)
        tabela.verticalHeader().setVisible(False)

        # Altura fixa: e o que permite ao QTableView calcular o offset do
        # scroll sem medir cada linha. Altura variavel faz o scroll tremer.
        tabela.verticalHeader().setDefaultSectionSize(SIZE_ROW_COMFORTABLE)
        tabela.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        tabela.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        cabecalho = tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        cabecalho.setSectionResizeMode(Column.ARQUIVO, QHeaderView.ResizeMode.Stretch)
        cabecalho.setHighlightSections(False)
        for coluna in Column:
            if coluna is not Column.ARQUIVO:
                tabela.setColumnWidth(coluna, coluna.width)

        # setSortingEnabled(True) dispara uma ordenacao imediata pela coluna 0,
        # que aqui e a da onda. Fixar o indicador em Arquivo evita a ordem
        # aleatoria na primeira abertura.
        cabecalho.setSortIndicator(Column.ARQUIVO, Qt.SortOrder.AscendingOrder)

        self._waveform_delegate = WaveformDelegate(tabela)
        tabela.setItemDelegateForColumn(Column.WAVEFORM, self._waveform_delegate)
        tabela.setItemDelegateForColumn(Column.CLASSIFICACAO, ClassificationDelegate(tabela))
        return tabela

    def set_state(self, state: LibraryState) -> None:
        self._todas = state.rows
        self._reaplica_filtros()

    def _reaplica_filtros(self) -> None:
        termo = self._busca.text().strip().lower()
        rotulo = self._filtro.currentText()
        linhas = [
            linha
            for linha in self._todas
            if (rotulo == "Todos" or linha.label == rotulo)
            and (not termo or termo in linha.filename.lower())
        ]
        self._model.set_rows(linhas)

    def keyPressEvent(self, event) -> None:
        chave = event.key()
        if chave not in _TECLAS:
            super().keyPressEvent(event)
            return
        linha = self._model.row_at(self._table.currentIndex().row())
        if linha is not None:
            self.decide_requested.emit(linha.sha1, _TECLAS[chave])
```

Criar `src/trackclassifier/ui/model_tab.py`:

```python
"""Aba Modelo: metricas, retreino e a lista de falhas de analise."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .labels_order import LABELS_EM_ORDEM
from .viewmodel import ModelState


class ModelTab(QWidget):
    train_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._metricas = QLabel("Modelo ainda nao treinado.")
        self._confusao = QLabel("")
        self._confusao.setObjectName("Numeric")
        self._falhas = QListWidget()

        botao = QPushButton("Retreinar")
        botao.setProperty("variant", "primary")
        botao.clicked.connect(self.train_requested)

        rotulo_falhas = QLabel("Falhas de analise")
        rotulo_falhas.setObjectName("SectionLabel")

        layout = QVBoxLayout(self)
        layout.addWidget(self._metricas)
        layout.addWidget(self._confusao)
        layout.addWidget(botao)
        layout.addWidget(rotulo_falhas)
        layout.addWidget(self._falhas, 1)

    def set_state(self, state: ModelState) -> None:
        if state.accuracy is None:
            self._metricas.setText("Modelo ainda nao treinado.")
            self._confusao.setText("")
        else:
            self._metricas.setText(
                f"Exemplos rotulados: {state.n_examples}\n"
                f"Acuracia (leave-one-out): {state.accuracy * 100:.1f}%\n"
                f"Erro ordinal medio: {state.ordinal_mae:.3f}"
            )
            cabecalho = "        " + "".join(f"{r:>8}" for r in LABELS_EM_ORDEM)
            linhas = [
                f"{rotulo:>8}" + "".join(f"{valor:>8}" for valor in linha)
                for rotulo, linha in zip(LABELS_EM_ORDEM, state.confusion, strict=True)
            ]
            self._confusao.setText(
                "Matriz de confusao (linha = real, coluna = previsto):\n"
                + "\n".join([cabecalho, *linhas])
            )

        self._falhas.clear()
        for nome, motivo in state.failures:
            self._falhas.addItem(f"{nome}: {motivo}")
```

> `labels_order` nao existe. Em vez de criar um modulo so para isso, importe de `viewmodel`: acrescente `LABELS_EM_ORDEM = tuple(rotulo.value for rotulo in LABEL_ORDER)` em `viewmodel.py` (importando `LABEL_ORDER` de `..labels`) e troque o import do `model_tab.py` para `from .viewmodel import LABELS_EM_ORDEM, ModelState`. Mantem a regra: a UI nao fala com o dominio direto, so pelo viewmodel.

- [ ] **Step 6: Write the window**

Criar `src/trackclassifier/ui/window.py`:

```python
"""Janela principal. Monta as abas e liga os sinais -- nada mais."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMainWindow, QPushButton, QTabWidget

from ..service import TrackService
from .library_tab import LibraryTab
from .model_tab import ModelTab
from .review_tab import ReviewTab
from .viewmodel import LibraryState, ModelState, ReviewState
from .widgets.player import MULTIMEDIA_AVAILABLE, create_player
from .worker import ServiceThread


class MainWindow(QMainWindow):
    def __init__(self, service: TrackService) -> None:
        super().__init__()
        self.setWindowTitle("Track classifier")
        self.resize(1180, 760)

        self._player = create_player(self)
        self._thread = ServiceThread(service)
        self._worker = self._thread.worker

        self.review_tab = ReviewTab(self._player)
        self.library_tab = LibraryTab()
        self.model_tab = ModelTab()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.review_tab, "Revisao")
        self.tabs.addTab(self.library_tab, "Biblioteca")
        self.tabs.addTab(self.model_tab, "Modelo")

        self._botao_scan = QPushButton("⟳ Escanear")
        self._botao_scan.clicked.connect(self._worker.scan)
        self.tabs.setCornerWidget(self._botao_scan, Qt.Corner.TopRightCorner)

        self.setCentralWidget(self.tabs)

        if not MULTIMEDIA_AVAILABLE:
            self.statusBar().showMessage(
                "Sem QtMultimedia: player simulado. Instale o extra audio para ouvir."
            )

        self._conecta()
        self._thread.start()
        # Dispara sozinho depois da janela aparecer: o scan sincrono do CLI
        # seriam minutos de tela morta aqui.
        QTimer.singleShot(0, self._worker.refresh)
        QTimer.singleShot(0, self._worker.scan)

    def _conecta(self) -> None:
        self.review_tab.decide_requested.connect(self._worker.decide)
        self.review_tab.undo_requested.connect(self._worker.undo)
        self.review_tab.bulk_approve_requested.connect(self._worker.bulk_approve)
        self.library_tab.decide_requested.connect(self._worker.decide)
        self.model_tab.train_requested.connect(self._worker.train)

        self._worker.states_changed.connect(self.apply_states)
        self._worker.scan_progress.connect(self._mostra_progresso)
        self._worker.scan_finished.connect(
            lambda: self.statusBar().showMessage("Scan concluido.", 4000)
        )
        self._worker.error.connect(
            lambda mensagem: self.statusBar().showMessage(mensagem, 6000)
        )
        self._worker.retrained.connect(
            lambda: self.statusBar().showMessage("Modelo retreinado.", 4000)
        )

    def apply_states(
        self, review: ReviewState, library: LibraryState, model: ModelState
    ) -> None:
        self.review_tab.set_state(review)
        self.library_tab.set_state(library)
        self.model_tab.set_state(model)

    def _mostra_progresso(self, concluidas: int, total: int, nome: str) -> None:
        self.statusBar().showMessage(f"escaneando {concluidas}/{total} · {nome}")

    def closeEvent(self, event) -> None:
        self._player.stop()
        self._thread.stop()
        super().closeEvent(event)
```

Criar `src/trackclassifier/ui/__main__.py`:

```python
"""Ponto de entrada da janela. Carrega o QSS gerado e sobe o QApplication."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ..config import load_config
from ..service import TrackService
from .window import MainWindow

QSS = Path(__file__).parent / "app.qss"


def main(config_path: str = "config.toml") -> int:
    config = load_config(Path(config_path))
    service = TrackService(config)

    app = QApplication(sys.argv)
    app.setStyleSheet(QSS.read_text(encoding="utf-8"))

    janela = MainWindow(service)
    janela.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_window.py -v && uv run ruff check .`
Expected: PASS, 5 testes

- [ ] **Step 8: Run the full suite and commit**

Run: `uv run pytest -q`
Expected: PASS

```bash
git add src/trackclassifier/ui/ tests/test_window.py tests/test_viewmodel.py
git commit -m "feat(ui): janela com abas de revisao, biblioteca e modelo"
```

---

### Task 9: Remocao da web e `dj review` abrindo a janela

Feita por ultimo de proposito: ate aqui o repo sempre teve um caminho de revisao funcionando. Agora a janela substitui a web e a web sai.

**Files:**
- Delete: `src/trackclassifier/web.py`, `src/trackclassifier/streaming.py`, `src/trackclassifier/static/`, `tests/test_web.py`, `tests/test_streaming.py`
- Modify: `src/trackclassifier/cli.py`
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Point `dj review` at the window**

Em `src/trackclassifier/cli.py`, remover os imports `uvicorn`, `from .web import create_app`, e trocar o bloco final de `main()` por:

```python
    print("Abrindo a janela de revisao...")
    from .ui.__main__ import main as abre_janela

    return abre_janela(argumentos.config)
```

> O import da UI e local de proposito: `dj scan` e `dj train` seguem headless e nao podem exigir PySide6 carregado nem `QApplication` construido.

Ainda em `cli.py`, `_servico()` roda `analyze_all()` de forma sincrona. Isso continua correto para `scan` e `train`, mas `review` agora escaneia sozinho dentro da janela. Trocar `main()` para so montar o servico sem analisar quando o comando for `review`:

```python
def _servico(caminho_config: str, analisar: bool = True) -> TrackService:
    config = load_config(Path(caminho_config))
    servico = TrackService(config)
    if analisar:
        servico.analyze_all(on_progress=_imprime_progresso)
    return servico
```

E na chamada:

```python
    try:
        servico = _servico(argumentos.config, analisar=argumentos.comando != "review")
    except ConfigError as erro:
        print(f"Erro de configuracao: {erro}", file=sys.stderr)
        return 1
```

- [ ] **Step 2: Delete the web layer**

```bash
git rm src/trackclassifier/web.py src/trackclassifier/streaming.py tests/test_web.py tests/test_streaming.py
git rm -r src/trackclassifier/static
```

- [ ] **Step 3: Drop the dependencies**

Em `pyproject.toml`, remover de `dependencies`:

```toml
    "fastapi>=0.110",
    "uvicorn>=0.29",
```

E remover `"httpx>=0.27"` de `dev` — existia para o `TestClient` do FastAPI.

- [ ] **Step 4: Add offscreen to CI**

Em `.github/workflows/ci.yml`, no step de teste:

```yaml
      - name: Test (pytest)
        env:
          QT_QPA_PLATFORM: offscreen
        run: uv run pytest
```

> `conftest.py` ja faz `setdefault`, mas declarar no workflow deixa explicito para quem le o CI que a suite tem UI e roda sem display.

- [ ] **Step 5: Run everything**

Run: `uv sync --extra dev && uv run pytest -q && uv run ruff check .`
Expected: PASS. A contagem cai em 298 linhas de teste (web e streaming) e sobe com os arquivos novos desta fase.

Verificar que nada ficou apontando para os modulos removidos:

```bash
grep -rn "fastapi\|uvicorn\|streaming\|create_app" src/ tests/ pyproject.toml
```
Expected: sem resultado.

- [ ] **Step 6: Update CLAUDE.md**

Trocar a linha do pipeline na secao Arquitetura:

```
`model` treina/prediz → `service.queue()` ordena por confianca → `ui` serve a
revisao numa janela PySide6 → `apply` move o arquivo → retreino automatico.
```

E na secao de concorrencia, substituir o paragrafo sobre o thread pool do Starlette por:

```
Ja a UI usa uma QThread unica dona do `TrackService` (`ui/worker.py`): a janela
manda pedidos por slot e recebe sinais, entao nao ha lock nem parquet escrito de
dois lugares. `apply._destino_livre` segue reservando o nome de destino
atomicamente com `os.open(O_CREAT|O_EXCL)` — o desfazer e o scan podem disputar
a mesma pasta.
```

Acrescentar aos comandos:

```bash
uv run python design/build_tokens.py   # regenera ui/tokens.py e ui/app.qss
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(ui): dj review abre a janela PySide6 e a camada web sai"
```

---

## Self-Review

**Cobertura da spec.** Todos os itens da fase 1 tem task: remocao da web (9), janela com as tres abas contra o `TrackService` real (8), waveform do `energy_curve` (5), scan global em background (7 e 8), cache de sha1 (1), desfazer (2). Dos itens transversais: tokens e regra de nenhum hex fora do JSON (4), `SimulatedPlayer` e CI sem display (6 e 9), altura de linha fixa de 46px (8), fronteira `viewmodel` sem Qt com teste que a verifica (3).

Tres pontos onde o plano **decide** algo que a spec deixou em aberto, e vale conferir antes de executar:

1. **Colunas da Biblioteca.** A spec lista `Titulo | Artista | Genero | Key`, que so existem nas fases 2 e 4. A fase 1 usa `Onda | Arquivo | BPM | Classificacao | Confianca | Duracao`.
2. **Acentos nos rotulos da UI.** A spec e o ref2 usam acentos; o repo inteiro (inclusive a saida do `cli.py` para o usuario) nao usa. O plano manda remover os acentos ao portar. Se voce quiser acentos na UI, e uma excecao explicita a convencao e o `CLAUDE.md` precisa registra-la.
3. **Cancelar o scan.** A spec pede botao Cancelar na status bar. `analyze_all` nao aceita cancelamento hoje — `ServiceWorker.cancel_scan()` existe mas so levanta a flag; interromper de verdade exigiria um parametro novo em `service._analyze` para parar de submeter ao pool. Como a spec chama isso de detalhe do progresso e nao de requisito de fase, o plano deixa o botao fora da Task 8. **Se for requisito, vira uma task nova entre a 7 e a 8**, mexendo em `service._analyze`.

**Consistencia de tipos.** `TrackRow` ganhou `path_hint: str` na Task 8 (Step 5) e o campo precisa entrar na definicao da Task 3 — quem executar a Task 3 isolada deve ja incluir `path_hint`, senao a Task 8 quebra. `LABELS_EM_ORDEM` idem: definido em `viewmodel.py`, consumido por `model_tab.py`. `TRACK_ROLE` mora em `delegates.py` e e importado por `track_model.py` — uma direcao so, sem ciclo.

**Verificacao de fim de fase.** Depois da Task 9, a fase 1 esta entregue quando:

```bash
uv run pytest -q && uv run ruff check . && uv run dj review
```

abre a janela, o scan roda em background com progresso na status bar, `1`/`2`/`3` movem o arquivo e avancam, `Cmd+Z` desfaz, a Biblioteca lista o acervo com a onda desenhada e a aba Modelo mostra as metricas e as falhas.
