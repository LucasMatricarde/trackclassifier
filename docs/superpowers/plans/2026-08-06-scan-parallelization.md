# Scan Parallelization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Paralelizar a extração de features entre núcleos de CPU e adicionar progresso visível durante `dj scan`/`dj train`, cortando o tempo de um scan grande de dezenas de minutos para uma fração disso.

**Architecture:** Uma função de topo de módulo (`extract_one`) roda em processos worker via `ProcessPoolExecutor`, sempre devolvendo resultado por valor (nunca escrevendo no cache diretamente) para preservar o escritor único do parquet. `TrackService._analyze` é reescrito para unificar as duas fases do scan (rotuladas + inbox) num lote só, decidir entre execução sequencial ou paralela conforme `max_workers` e o tamanho do lote pendente, e emitir progresso via callback opcional.

**Tech Stack:** `concurrent.futures.ProcessPoolExecutor` (biblioteca padrão), `threadpoolctl` (já é dependência transitiva via `scikit-learn`).

## Global Constraints

- **Versão de Python:** `requires-python = ">=3.11,<3.14"`, inalterado.
- **Raiz do projeto:** `/Users/lucasmatricarde/ProjetosPessoais/AnaliseTracks/trackclassifier/`. Todo comando roda de lá com `uv run`.
- **`extract_one` deve ser importável no nível de módulo** (não uma closure, não um método) — é o requisito do `pickle` para `ProcessPoolExecutor` conseguir enviar a chamada a um processo filho.
- **O pool só é usado quando `max_workers > 1` E há mais de 1 arquivo pendente.** Com `max_workers=1`, a extração roda sempre no processo principal, mesmo com muitos pendentes — nunca instancia `ProcessPoolExecutor`. Essa condição dupla é obrigatória: `max_workers=1` sozinho não bastaria, porque ainda assim subiria um processo filho (só que com um worker), que no macOS (`spawn`) reimporta tudo do zero e não herda o `pythonpath` extra que o pytest injeta para tornar `tests/` importável — quebraria qualquer teste que use `ExtratorFalso` (definido em `tests/test_service.py`, nunca instalado como pacote).
- **Nenhum worker escreve no `AnalysisCache` diretamente.** Só o processo principal chama `cache.put()`/`cache.save()`.
- **Testes existentes de `TrackService` passam `max_workers=1` explicitamente** em toda construção — preserva velocidade, determinismo e evita o risco de import entre processos acima.
- **Textos de interface em português**, seguindo o padrão já estabelecido no projeto.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/trackclassifier/extraction.py` | Nova. Função de topo de módulo `extract_one`, picklable, com limite de threads BLAS por chamada. |
| `src/trackclassifier/service.py` | Modificado. `analyze_all`/`_analyze` reescritos: fases unificadas, callback de progresso, decisão sequencial/paralela. |
| `src/trackclassifier/cli.py` | Modificado. `_servico` passa uma função de impressão de progresso pra `analyze_all`. |
| `tests/test_extraction.py` | Nova. Testes de `extract_one`. |
| `tests/test_service.py` | Modificado. Todas as construções de `TrackService` ganham `max_workers=1`; testes novos para o limiar de paralelização e para o save periódico com contador unificado. |

---

### Task 1: `extraction.py` — função de extração picklable

**Files:**
- Create: `src/trackclassifier/extraction.py`
- Test: `tests/test_extraction.py`

**Interfaces:**
- Consumes: `FeatureExtractor` (Protocol), `TrackAnalysis` de `features.py`
- Produces: `extract_one(extractor: FeatureExtractor, path: Path) -> tuple[TrackAnalysis | None, str | None]` — exatamente um dos dois elementos é `None`. Sucesso: `(analise, None)`. Falha: `(None, mensagem_de_erro)`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_extraction.py`:

```python
from pathlib import Path

import numpy as np

from trackclassifier.extraction import extract_one
from trackclassifier.features import TrackAnalysis


class _ExtratorSucesso:
    name = "sucesso-v1"

    def extract(self, path: Path) -> TrackAnalysis:
        return TrackAnalysis(
            vector=np.zeros(44, dtype=np.float64),
            energy_curve=[0.1, 0.2],
            peak_offset_s=1.0,
            bpm=120.0,
            duration_s=30.0,
        )


class _ExtratorFalha:
    name = "falha-v1"

    def extract(self, path: Path) -> TrackAnalysis:
        raise ValueError(f"nao consegui decodificar {path.name}")


def test_sucesso_devolve_analise_e_erro_none(tmp_path):
    caminho = tmp_path / "t.mp3"

    analise, erro = extract_one(_ExtratorSucesso(), caminho)

    assert isinstance(analise, TrackAnalysis)
    assert erro is None


def test_falha_devolve_none_e_mensagem_de_erro(tmp_path):
    caminho = tmp_path / "quebrado.mp3"

    analise, erro = extract_one(_ExtratorFalha(), caminho)

    assert analise is None
    assert "quebrado.mp3" in erro


def test_limita_threads_de_blas_durante_a_chamada(tmp_path, monkeypatch):
    chamadas = []

    class _LimiteEspiao:
        def __init__(self, *args, **kwargs):
            chamadas.append((args, kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr("trackclassifier.extraction.threadpool_limits", _LimiteEspiao)

    extract_one(_ExtratorSucesso(), tmp_path / "t.mp3")

    assert len(chamadas) == 1
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_extraction.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.extraction'`.

- [ ] **Step 3: Implementar `extraction.py`**

```python
from pathlib import Path

from threadpoolctl import threadpool_limits

from .features import FeatureExtractor, TrackAnalysis


def extract_one(
    extractor: FeatureExtractor, path: Path
) -> tuple[TrackAnalysis | None, str | None]:
    with threadpool_limits(limits=1):
        try:
            return extractor.extract(path), None
        except Exception as erro:
            return None, str(erro)
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_extraction.py -v
```

Esperado: 3 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add src/trackclassifier/extraction.py tests/test_extraction.py
git commit -m "feat(trackclassifier): funcao de extracao picklable com limite de threads BLAS"
```

---

### Task 2: Reescrever `TrackService.analyze_all`/`_analyze`

**Files:**
- Modify: `src/trackclassifier/service.py`
- Modify: `tests/test_service.py`

**Interfaces:**
- Consumes: `extract_one` de `extraction.py`
- Produces (mudanças no `TrackService`):
  - `__init__(self, config, extractor=None, max_workers: int | None = None)` — novo parâmetro opcional, padrão `os.cpu_count() or 1`
  - `analyze_all(self, on_progress: Callable[[int, int, str], None] | None = None) -> None`
  - `_analyze` reescrito internamente (não é interface pública, mas seu comportamento observável muda: fases unificadas, save periódico sobre o lote combinado)

**Nota:** este passo modifica um arquivo já coberto por testes existentes. Todos os testes de `tests/test_service.py` continuam validos, mas toda construção de `TrackService` precisa ganhar `max_workers=1` — sem isso, os testes que hoje têm mais de 1 arquivo pendente (a maioria, já que `_povoa` cria 18 tracks rotuladas) tentariam usar `ProcessPoolExecutor` com `ExtratorFalso`, que não é importável num processo filho.

- [ ] **Step 1: Adicionar `max_workers=1` em toda construção de `TrackService` em `tests/test_service.py`**

Editar a função `_servico` (linha ~54):

```python
def _servico(config, falhar_em=None) -> TrackService:
    servico = TrackService(config, extractor=ExtratorFalso(falhar_em), max_workers=1)
    servico.analyze_all()
    return servico
```

E as três construções diretas de `TrackService` que não passam por `_servico` — em `test_falhas_de_analise_nao_derrubam_a_fila`, `test_modelo_corrompido_nao_derruba_a_construcao_do_servico` e `test_cache_e_salvo_periodicamente_durante_um_scan_grande` — cada uma ganha `max_workers=1`:

```python
    servico = TrackService(config, extractor=ExtratorFalso(falhar_em={"ruim_0.5.mp3"}), max_workers=1)
```

```python
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
```

```python
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
```

- [ ] **Step 2: Escrever os dois testes novos que falham**

Acrescentar ao final de `tests/test_service.py`:

```python
def test_um_unico_pendente_nao_aciona_o_pool_mesmo_com_max_workers_alto(tmp_path):
    config = _config(tmp_path)
    (config.inbox / "unica_0.5.mp3").write_bytes(b"unica")

    # ExtratorFalso nao e importavel num processo filho (spawn). Se o pool
    # fosse usado aqui, esta chamada falharia com erro de pickle/import.
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=4)
    servico.analyze_all()

    assert len(servico.cache) == 1


def test_save_periodico_soma_as_duas_fases_do_scan(tmp_path, monkeypatch):
    config = _config(tmp_path)
    for rotulo in (Label.DOWN, Label.NEUTRAL, Label.UP):
        for i in range(2):
            (config.folders[rotulo] / f"r{i}_{rotulo.value}.mp3").write_bytes(
                f"{rotulo.value}{i}".encode()
            )
    for i in range(6):
        (config.inbox / f"n{i}_0.{i:02d}.mp3").write_bytes(f"n{i}".encode())

    # 6 rotuladas + 6 na inbox = 12 pendentes no total. Nenhuma das duas fases
    # sozinha cruza o limiar de 10 do save periodico -- so o contador
    # unificado sobre o lote combinado deve disparar o save.
    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)

    chamadas = []
    original_save = servico.cache.save

    def _save_espiao():
        chamadas.append(1)
        original_save()

    monkeypatch.setattr(servico.cache, "save", _save_espiao)

    servico.analyze_all()

    assert len(chamadas) > 1
```

- [ ] **Step 3: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_service.py -v
```

Esperado: `test_um_unico_pendente_nao_aciona_o_pool_mesmo_com_max_workers_alto` FAIL com `TypeError: __init__() got an unexpected keyword argument 'max_workers'` (o parâmetro ainda não existe). `test_save_periodico_soma_as_duas_fases_do_scan` também falha pelo mesmo motivo.

- [ ] **Step 4: Reescrever `service.py`**

Substituir o topo do arquivo (imports e constante) por:

```python
import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .apply import FileVanishedError, move_to_folder
from .cache import AnalysisCache
from .config import Config
from .extraction import extract_one
from .features import FeatureExtractor, HandcraftedExtractor, TrackAnalysis
from .labels import Label
from .library import TrackRef, scan_inbox, scan_labeled
from .model import Metrics, TrackModel

_CACHE_SAVE_EVERY = 10

ProgressCallback = Callable[[int, int, str], None]
```

Substituir `__init__` por:

```python
    def __init__(
        self,
        config: Config,
        extractor: FeatureExtractor | None = None,
        max_workers: int | None = None,
    ):
        self.config = config
        self.extractor = extractor or HandcraftedExtractor()
        self.cache = AnalysisCache(config.data_dir / "analyses.parquet")
        self.model_path = config.data_dir / "model.joblib"
        self.model = self._load_model()
        self._labeled: list[TrackRef] = []
        self._inbox: list[TrackRef] = []
        self._failures: list[FailedItem] = []
        self._decisions_since_train = 0
        self._max_workers = max_workers or (os.cpu_count() or 1)
```

Substituir `analyze_all` e `_analyze` por:

```python
    def analyze_all(self, on_progress: ProgressCallback | None = None) -> None:
        self._failures = []
        candidatos = scan_labeled(self.config) + scan_inbox(self.config)
        aceitos = self._analyze(candidatos, on_progress)
        self._labeled = [ref for ref in aceitos if ref.label is not None]
        self._inbox = [ref for ref in aceitos if ref.label is None]
        self.cache.save()

    def _analyze(
        self, refs: list[TrackRef], on_progress: ProgressCallback | None = None
    ) -> list[TrackRef]:
        aceitos: list[TrackRef] = []
        pendentes: list[TrackRef] = []
        for ref in refs:
            if self.cache.get(ref.sha1, self.extractor.name) is not None:
                aceitos.append(ref)
            else:
                pendentes.append(ref)

        if not pendentes:
            return aceitos

        total = len(pendentes)
        estado = {"concluidas": 0, "desde_o_ultimo_save": 0}

        def _processa_resultado(ref: TrackRef, analise, erro: str | None) -> None:
            estado["concluidas"] += 1
            if erro is not None:
                self._failures.append(FailedItem(filename=ref.path.name, reason=erro))
            else:
                self.cache.put(ref.sha1, ref.path.name, self.extractor.name, analise)
                aceitos.append(ref)
                estado["desde_o_ultimo_save"] += 1
                if estado["desde_o_ultimo_save"] >= _CACHE_SAVE_EVERY:
                    self.cache.save()
                    estado["desde_o_ultimo_save"] = 0
            if on_progress is not None:
                on_progress(estado["concluidas"], total, ref.path.name)

        usa_pool = self._max_workers > 1 and total > 1

        if not usa_pool:
            for ref in pendentes:
                analise, erro = extract_one(self.extractor, ref.path)
                _processa_resultado(ref, analise, erro)
        else:
            with ProcessPoolExecutor(max_workers=self._max_workers) as executor:
                futuros = {
                    executor.submit(extract_one, self.extractor, ref.path): ref
                    for ref in pendentes
                }
                for futuro in as_completed(futuros):
                    ref = futuros[futuro]
                    try:
                        analise, erro = futuro.result()
                    except Exception as falha_do_worker:
                        # extract_one ja captura excecoes da propria extracao,
                        # entao chegar aqui significa que o worker morreu
                        # (segfault em ffmpeg/librosa, OOM, BrokenProcessPool).
                        # Contem a falha como qualquer outra em vez de derrubar
                        # o scan inteiro: o cache ja salvo e preservado, e uma
                        # re-execucao tenta de novo so o que falhou.
                        analise, erro = None, f"worker falhou: {falha_do_worker}"
                    _processa_resultado(ref, analise, erro)

        # as_completed devolve em ordem de conclusao, nao de entrada. Reordena
        # pela ordem original de `refs` para que _labeled/_inbox fiquem
        # deterministicos entre execucoes -- library.py ja ordena de forma
        # estavel, e essa garantia nao pode se perder aqui.
        posicao = {ref.sha1: i for i, ref in enumerate(refs)}
        return sorted(aceitos, key=lambda ref: posicao[ref.sha1])
```

Nada mais no arquivo muda — `_analysis`, `train`, `failures`, `queue`, `path_for`, `decide`, `bulk_approve` continuam exatamente como estão hoje.

- [ ] **Step 5: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_service.py -v
```

Esperado: todos os testes PASS, incluindo os dois novos.

- [ ] **Step 6: Rodar a suíte inteira**

```bash
uv run pytest -v
```

Esperado: nenhuma regressão em nenhum outro módulo.

- [ ] **Step 7: Commit**

```bash
git add src/trackclassifier/service.py tests/test_service.py
git commit -m "feat(trackclassifier): paraleliza extracao entre processos, unifica fases do scan e progresso"
```

---

### Task 3: Testes do caminho paralelo — pool real e worker morto

**Files:**
- Modify: `tests/test_service.py`

**Interfaces:**
- Consumes: `HandcraftedExtractor` de `features.py`, `soundfile` (já é dependência de dev do projeto)

**Nota:** `ExtratorFalso` não funciona aqui — não é importável num processo filho gerado via `spawn`. Este teste usa o extrator de verdade (`HandcraftedExtractor`, que é parte do pacote `trackclassifier` instalado, e portanto importável em qualquer processo filho) sobre áudio sintético real, seguindo o mesmo padrão de `tests/test_integration.py`.

- [ ] **Step 1: Escrever os dois testes**

Acrescentar ao final de `tests/test_service.py` (adicionar `import soundfile as sf` no topo se ainda não estiver lá):

```python
def _escreve_wav_curto(caminho, duracao_s=15.0, sr=22050, seed=0):
    import numpy as np
    import soundfile as sf

    gerador = np.random.default_rng(seed)
    sinal = (0.2 * gerador.standard_normal(int(sr * duracao_s))).astype(np.float32)
    sf.write(caminho, sinal, sr)
    return caminho


def test_pool_de_verdade_processa_multiplos_arquivos_em_paralelo(tmp_path):
    from trackclassifier.features import HandcraftedExtractor

    config = _config(tmp_path)
    for rotulo, seed in ((Label.DOWN, 1), (Label.NEUTRAL, 2), (Label.UP, 3)):
        _escreve_wav_curto(config.folders[rotulo] / f"r_{rotulo.value}.wav", seed=seed)
    _escreve_wav_curto(config.inbox / "nova1.wav", seed=10)
    _escreve_wav_curto(config.inbox / "nova2.wav", seed=11)

    servico = TrackService(config, extractor=HandcraftedExtractor(), max_workers=2)
    servico.analyze_all()

    assert len(servico.cache) == 5
    assert servico.failures() == []
    assert len(servico._labeled) == 3
    assert len(servico._inbox) == 2


def test_worker_morto_vira_falha_contida_e_nao_derruba_o_scan(tmp_path, monkeypatch):
    config = _config(tmp_path)
    for i in range(3):
        (config.inbox / f"n{i}_0.{i}.mp3").write_bytes(f"n{i}".encode())

    class _FuturoMorto:
        def result(self):
            raise RuntimeError("processo worker morreu")

    class _ExecutorFalso:
        def __init__(self, max_workers=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def submit(self, fn, *args):
            return _FuturoMorto()

    # Troca o pool de verdade por um cujos futuros sempre estouram na coleta
    # do resultado, simulando worker morto (segfault/OOM/BrokenProcessPool).
    # Como nenhum processo real e criado, ExtratorFalso segue seguro aqui.
    monkeypatch.setattr("trackclassifier.service.ProcessPoolExecutor", _ExecutorFalso)
    monkeypatch.setattr("trackclassifier.service.as_completed", list)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=2)
    servico.analyze_all()

    assert len(servico.failures()) == 3
    assert all("worker falhou" in falha.reason for falha in servico.failures())
    assert len(servico.cache) == 0
```

- [ ] **Step 2: Rodar os dois testes para confirmar que passam**

```bash
uv run pytest tests/test_service.py -k "pool_de_verdade or worker_morto" -v
```

Esperado: 2 testes PASS. Estes não seguem RED→GREEN clássico porque não introduzem interface nova (a Task 2 já implementou tudo que eles exercitam) — eles validam que a implementação da Task 2 funciona com processos de verdade e sob worker morto, dois caminhos que os testes com `max_workers=1` não tocam.

Se `test_pool_de_verdade...` falhar com erro de pickle/import, é sinal de que algo em `HandcraftedExtractor` ou em `extract_one` não é picklable — investigar antes de prosseguir, não silenciar o teste.

- [ ] **Step 3: Rodar a suíte inteira**

```bash
uv run pytest -v
```

Esperado: todos os testes PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_service.py
git commit -m "test(trackclassifier): cobre pool real e worker morto no caminho paralelo"
```

---

### Task 4: Progresso no CLI

**Files:**
- Modify: `src/trackclassifier/cli.py`

**Interfaces:**
- Consumes: `TrackService.analyze_all(on_progress=...)` da Task 2

**Nota:** não há teste dedicado para esta task — é fiação de apresentação (igual à Task 13 do plano original, que também não tinha suíte automatizada). A suíte completa deve continuar verde, e a verificação real é rodar `dj scan` manualmente contra um acervo de verdade e ver as linhas de progresso aparecerem.

- [ ] **Step 1: Adicionar a função de impressão de progresso e ligá-la em `_servico`**

Em `src/trackclassifier/cli.py`, logo antes da definição de `_servico`:

```python
def _imprime_progresso(concluidas: int, total: int, nome: str) -> None:
    print(f"[{concluidas}/{total}] {nome}")
```

E alterar `_servico`:

```python
def _servico(caminho_config: str) -> TrackService:
    config = load_config(Path(caminho_config))
    servico = TrackService(config)
    servico.analyze_all(on_progress=_imprime_progresso)
    return servico
```

- [ ] **Step 2: Rodar a suíte inteira**

```bash
uv run pytest -v
```

Esperado: todos os testes PASS. Já verificado: todos os testes de `tests/test_cli.py` usam `"substring" in capsys.readouterr().out` (ou `.err`), nunca igualdade exata de `stdout` — as novas linhas de progresso não quebram nenhuma asserção existente.

- [ ] **Step 3: Verificação manual**

Depois de mergeado, rodar `uv run dj scan` (ou `dj train`) contra o `config.toml` real e confirmar:

1. Linhas `[N/total] nome_do_arquivo` aparecem conforme cada track termina.
2. O scan como um todo fica visivelmente mais rápido que a rodada sequencial anterior (base de comparação: ~40 minutos para 341 tracks).

- [ ] **Step 4: Commit**

```bash
git add src/trackclassifier/cli.py
git commit -m "feat(trackclassifier): imprime progresso do scan no CLI"
```

---

## Verificação final

- [ ] `uv run pytest -v` — suíte inteira verde
- [ ] `uv run dj scan` num acervo real — progresso aparece, tempo total cai perceptivelmente frente à linha de base sequencial
