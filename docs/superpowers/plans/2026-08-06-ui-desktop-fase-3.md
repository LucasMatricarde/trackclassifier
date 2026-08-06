# UI desktop fase 3 — waveform RGB por banda Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar a onda mono (derivada do `energy_curve`) por uma onda RGB estilo Rekordbox, em que a cor de cada coluna e a energia das tres bandas — graves no vermelho, medios no verde, agudos no azul.

**Architecture:** Os buckets por banda sao caros (STFT sobre a track inteira) e sao dado de APRESENTACAO, nao de ML — entao vivem no cache de apresentacao da fase 2, em `peaks/<sha1>.npy`, versionados por `PRESENTATION_VERSION`. Nao sao computados durante o scan: sao preguicosos, disparados pela tela que precisa deles, numa fila do worker thread. Enquanto nao existem, a onda cai no render mono da fase 1 — que continua vivo, nao e removido.

**Tech Stack:** Python 3.11+, `librosa` (STFT), `numpy` (buckets em float16), PySide6-Essentials (QPainter, QImage), pytest.

## Contexto: o que ja existe

Isto e a **fase 3 de 4** da spec `docs/superpowers/specs/2026-08-05-ui-desktop-design.md`. As fases 1 e 2 estao entregues e em `main`. O que ja funciona e este plano nao pode quebrar:

- `TrackAnalysis` (`features.py`) com `energy_curve: list[float]` — a curva mono que a fase 1 usa. **Continua existindo e continua sendo usada como fallback.**
- `AnalysisCache` (`cache.py`) — parquet do vetor de ML, chaveado por `(sha1, extractor.name)`. **Este plano nao toca nele.**
- `PresentationCache` (`presentation.py`) — parquet de tags + `covers/<sha1><ext>`, com `PRESENTATION_VERSION` (hoje `1`). Metodos: `get(sha1)`, `put(sha1, tags, cover)`, `cover_path(sha1)`, `save()`, `__len__()`.
- `TrackService` (`service.py`) com `analyze_all(on_progress, should_cancel) -> bool`, `presentation_for(sha1)`, `cover_path_for(sha1)`, e `_preenche_apresentacao` (le tags no fim do scan).
- `ServiceWorker`/`ServiceThread` (`ui/worker.py`) — a QThread dona do servico. `request_cancel()` e metodo normal, **nao** `@Slot`, por causa do loop de eventos bloqueado durante o scan.
- `ui/viewmodel.py` — dataclasses puras, **nao importa Qt** (teste gramatical falha se importar).
- `ui/widgets/waveform_render.py` — `render_curve(curve, size, bar_width, gap, background) -> QPixmap` (mono) e `PixmapCache` (LRU por `(sha1, largura, altura)`).
- `ui/widgets/waveform_view.py` — `WaveformView`, a onda grande da Revisao, com playhead e seek.
- `ui/widgets/delegates.py` — `TRACK_ROLE`, `_DelegateComFundo`, `WaveformDelegate`, `TitleDelegate`, `ClassificationDelegate`.
- `ui/tokens.py` — **gerado**, ja contem `COLOR_WAVEBAND_LOW_GAIN="1.00"`, `COLOR_WAVEBAND_MID_GAIN="0.92"`, `COLOR_WAVEBAND_HIGH_GAIN="1.00"`, `COLOR_WAVEBAND_FLOOR="0.06"`, `SIZE_WAVE_BUCKETS=2000`, `SIZE_WAVE_BAR=2`, `SIZE_WAVE_GAP=0`. **Nenhum token novo e necessario**, entao `design/build_tokens.py` nao precisa rodar.

## Global Constraints

- **Portugues sem acentos** em tudo interno: variaveis locais, funcoes internas, comentarios, docstrings, mensagens de erro, nomes de teste e texto de UI visivel.
- API publica (dataclasses, metodos de classe, campos de parquet, nomes de features) em **ingles**; interior das funcoes em portugues.
- Comentarios explicam **por que**, nao o que — e sao longos quando a decisao nao e obvia.
- ruff: `line-length = 100`, regras `E,F,I,UP,B`. `uv run ruff check .` e gate do CI.
- Commits: conventional commits com escopo (`feat(trackclassifier):`, `fix(ui):`).
- **`ui/viewmodel.py` nao pode importar Qt.** `tests/test_viewmodel.py::test_viewmodel_nao_importa_qt` le o modulo e falha se aparecer `PySide6`.
- **Nenhum hex fora de `design/design-tokens.json`.** Cores vem de `ui/tokens.py`.
- **`ui/tokens.py` e `ui/app.qss` sao gerados** — nunca editar a mao.
- **Nao alterar `FEATURE_NAMES` nem `HandcraftedExtractor.name`.** Qualquer mudanca ali invalida o cache de ML da biblioteca inteira. Esta fase nao tem motivo nenhum para tocar nisso — os buckets sao apresentacao, nao features.
- Todo estado em disco fica sob `config.data_dir` (default `.trackclassifier/`, gitignored).
- Escrita de arquivo de estado e **atomica**: grava em `.tmp` no mesmo diretorio e `os.replace`.
- Erros degradam e sao reportados, nunca derrubam o comando.
- Python `>=3.11,<3.14`.

## Fatos verificados antes de escrever este plano

Estes foram **executados neste repositorio**. Nao sao suposicoes.

1. **`Path.with_suffix(p.suffix + ".tmp")` produz `abc.npy.tmp`** — e `np.save("abc.npy.tmp")` grava **`abc.npy.tmp.npy`**, porque `np.save` anexa `.npy` quando o caminho nao termina nisso. O `os.replace` seguinte falharia com `FileNotFoundError`.
   **A forma correta**, verificada:
   ```python
   tmp = destino.with_name(destino.stem + ".tmp" + destino.suffix)   # abc.tmp.npy
   np.save(tmp, arr)      # grava abc.tmp.npy, sem duplicar extensao
   os.replace(tmp, destino)
   ```
2. **`np.load` de um arquivo invalido levanta `ValueError`** (mensagem sobre "pickled (object) data"), nao `OSError`. Um `except OSError` nao contem esse caso.
3. **STFT com `n_fft=2048`, `hop_length=512` a 22050 Hz** distribui os bins assim: **24 bins abaixo de 250 Hz**, **348 entre 250 e 4000**, **653 acima de 4000**. As tres bandas tem cobertura real; nenhuma fica vazia.
4. **1 segundo de audio produz 44 frames de STFT** — bem abaixo dos 2000 buckets. O caminho de padding (`np.pad(..., mode="edge")`) e exercitado por qualquer track curta, nao e teorico.
5. **A matematica de cor do ref2 funciona** com os tokens reais: um sinal bass-heavy (80 Hz forte, 8 kHz fraco) produz medias por canal `[0.93, 0.03, 0.08]` e cor `[231, 37, 27]` — vermelho dominante, como esperado. Um sinal treble-heavy produz `[0.03, 0.02, 0.75]`.
6. **`float(COLOR_WAVEBAND_LOW_GAIN)` funciona**: os ganhos em `tokens.py` sao strings (`"1.00"`, `"0.92"`, `"0.06"`), nao floats. Precisam de conversao explicita no ponto de uso.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/trackclassifier/peaks.py` | **NOVO.** `compute_bands(path) -> np.ndarray` (N,3) float16. STFT, tres bandas, resample para `SIZE_WAVE_BUCKETS`, normalizacao. Sem Qt. |
| `src/trackclassifier/presentation.py` | Modificar: `PeaksStore` — grava/le `peaks/<sha1>.npy`, versionado. |
| `src/trackclassifier/service.py` | Modificar: `peaks_for(sha1)`, `ensure_peaks(sha1, path)`. |
| `src/trackclassifier/ui/viewmodel.py` | Modificar: `TrackRow.peaks_path: str \| None`. |
| `src/trackclassifier/ui/worker.py` | Modificar: slot `compute_peaks(sha1, path)` + sinal `peaks_ready`. |
| `src/trackclassifier/ui/widgets/waveform_render.py` | Modificar: `render_bands(...)` e `load_peaks(...)`. `render_curve` **fica**. |
| `src/trackclassifier/ui/widgets/waveform_view.py` | Modificar: usa RGB quando ha buckets, mono quando nao. |
| `src/trackclassifier/ui/widgets/delegates.py` | Modificar: `WaveformDelegate` idem, e pede computo do que falta. |
| `src/trackclassifier/ui/review_tab.py` | Modificar: pede os buckets da track atual. |
| `src/trackclassifier/ui/window.py` | Modificar: liga o pedido de buckets ao worker. |
| `CLAUDE.md` | Modificar: documentar os buckets e a regra de versao. |
| `tests/test_peaks.py` | **NOVO.** |

### Decisao de escopo: como o "preguicoso" e implementado

A spec diz "preguicoso e priorizado pelo que esta visivel, em vez de backfill da biblioteca inteira". Este plano implementa a **forma simplificada**, decidida com o usuario:

- **Revisao**: sempre pede os buckets da track atual ao trocar de track. E a prioridade real — e onde o DJ decide.
- **Biblioteca**: `WaveformDelegate.paint()` pede o computo quando pinta uma linha cujos buckets ainda nao existem. Uma fila simples no worker, sem recomputar o que ja foi pedido.
- **Fora de escopo**: rastrear scroll da `QTableView`, fila de prioridade por viewport, cancelar pedidos que saem da tela, pool dedicado separado do scan. Isso dobraria o tamanho do plano em infra de scroll-tracking.

Consequencia aceita e registrada: rolar rapido por 500 linhas enfileira 500 pedidos que serao processados em ordem de chegada, nao de visibilidade. Como cada computo custa ~1-3s e o fallback mono aparece imediatamente, a tela nunca fica vazia — so demora a ficar colorida. Se isso incomodar na pratica, e a hora de implementar a fila priorizada.

### Divergencia consciente da spec: o fallback e a onda mono, nao um placeholder liso

A spec diz, em dois lugares, que enquanto os buckets nao existem "a linha mostra um placeholder liso" / "Waveform mostra placeholder liso". **Este plano nao faz isso**, e a divergencia e deliberada:

a spec foi escrita antes da fase 1 existir, quando nao havia onda nenhuma para mostrar. Hoje a fase 1 ja entrega a onda mono derivada do `energy_curve`, que vem de graca com o scan. Trocar isso por uma barra lisa seria uma **regressao visivel** — o usuario perderia informacao que ja tem hoje, durante os segundos em que o computo roda.

Entao a regra desta fase e: **RGB quando ha buckets, mono quando nao ha, e nada so quando nem `energy_curve` existe.** Quem revisar nao deve tratar a ausencia do "placeholder liso" como descumprimento de spec.

## Ordem das tarefas

Tarefas 1-2 sao backend puro, testaveis sem Qt. A 3 liga no servico. A 4 e a fronteira. As 5-7 sao UI.

---

### Task 1: Computo dos buckets por banda

**Files:**
- Create: `src/trackclassifier/peaks.py`
- Create: `tests/test_peaks.py`

**Interfaces:**
- Consumes: `audio_io.decode(path, sample_rate) -> np.ndarray` e `audio_io.ANALYSIS_SR` (ja existem).
- Produces:
  - `PEAKS_BUCKETS: int` — importado de `ui.tokens.SIZE_WAVE_BUCKETS`, valor `2000`
  - `compute_bands(path: Path, buckets: int = PEAKS_BUCKETS) -> np.ndarray` — shape `(buckets, 3)`, dtype `float16`, valores em `[0, 1]`

- [ ] **Step 1: Escrever os testes**

Crie `tests/test_peaks.py`:

```python
"""Buckets por banda. Sinais sinteticos com conteudo espectral conhecido.

Um seno de 80 Hz TEM que sair vermelho-dominante e um de 8 kHz azul-dominante
-- e o unico jeito de provar que as mascaras de frequencia estao nas bandas
certas, e nao trocadas entre si.
"""

import numpy as np
import pytest
import soundfile as sf

from trackclassifier.peaks import PEAKS_BUCKETS, compute_bands

SR = 22050
DURACAO = 12.0


def _tom(tmp_path, frequencias_e_amplitudes, nome="t.wav", duracao=DURACAO):
    t = np.linspace(0, duracao, int(SR * duracao), endpoint=False)
    sinal = np.zeros_like(t)
    for frequencia, amplitude in frequencias_e_amplitudes:
        sinal = sinal + amplitude * np.sin(2 * np.pi * frequencia * t)
    caminho = tmp_path / nome
    sf.write(caminho, sinal.astype(np.float32), SR)
    return caminho


def test_forma_e_tipo_do_resultado(tmp_path):
    caminho = _tom(tmp_path, [(440.0, 0.5)])

    bandas = compute_bands(caminho)

    assert bandas.shape == (PEAKS_BUCKETS, 3)
    assert bandas.dtype == np.float16


def test_valores_ficam_entre_zero_e_um(tmp_path):
    caminho = _tom(tmp_path, [(440.0, 0.9)])

    bandas = compute_bands(caminho)

    assert float(bandas.min()) >= 0.0
    assert float(bandas.max()) <= 1.0


def test_grave_domina_o_canal_vermelho(tmp_path):
    # 80 Hz forte + 8 kHz fraco. Se as mascaras estiverem trocadas, este
    # teste pega na hora.
    caminho = _tom(tmp_path, [(80.0, 0.8), (8000.0, 0.05)])

    medias = compute_bands(caminho).astype(np.float32).mean(axis=0)

    assert medias[0] > medias[1]
    assert medias[0] > medias[2]


def test_agudo_domina_o_canal_azul(tmp_path):
    caminho = _tom(tmp_path, [(8000.0, 0.8), (80.0, 0.05)])

    medias = compute_bands(caminho).astype(np.float32).mean(axis=0)

    assert medias[2] > medias[0]
    assert medias[2] > medias[1]


def test_track_curta_e_preenchida_ate_o_numero_de_buckets(tmp_path):
    # 1s de audio da ~44 frames de STFT, bem abaixo dos 2000 buckets. O
    # padding tem que completar sem quebrar a forma.
    caminho = _tom(tmp_path, [(440.0, 0.5)], duracao=1.0)

    bandas = compute_bands(caminho)

    assert bandas.shape == (PEAKS_BUCKETS, 3)


def test_numero_de_buckets_e_configuravel(tmp_path):
    caminho = _tom(tmp_path, [(440.0, 0.5)])

    bandas = compute_bands(caminho, buckets=64)

    assert bandas.shape == (64, 3)


def test_silencio_nao_gera_nan(tmp_path):
    # Divisao pelo maximo, que aqui e zero: sem o epsilon, tudo vira NaN e a
    # onda inteira some sem erro nenhum.
    caminho = tmp_path / "silencio.wav"
    sf.write(caminho, np.zeros(int(SR * DURACAO), dtype=np.float32), SR)

    bandas = compute_bands(caminho)

    assert np.isfinite(bandas.astype(np.float32)).all()
    assert float(bandas.max()) == 0.0


def test_arquivo_inexistente_propaga_audio_decode_error(tmp_path):
    # Contencao e responsabilidade de quem chama (service/worker), nao deste
    # modulo: aqui a falha precisa ser visivel.
    from trackclassifier.audio_io import AudioDecodeError

    with pytest.raises(AudioDecodeError):
        compute_bands(tmp_path / "nao_existe.wav")
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_peaks.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.peaks'`

- [ ] **Step 3: Implementar `compute_bands`**

Crie `src/trackclassifier/peaks.py`:

```python
"""Buckets de energia por banda, para o render RGB da onda.

Graves no vermelho, medios no verde, agudos no azul -- a cor de cada coluna
E a energia das tres bandas, nao um gradiente aplicado sobre uma envoltoria.

Isto e dado de APRESENTACAO, nao de ML: nao entra em FEATURE_NAMES e nao
influencia o modelo. Se entrasse, acrescentar uma banda mudaria
`extractor.name` e re-analisaria a biblioteca inteira.

Nao importa Qt.
"""

from pathlib import Path

import librosa
import numpy as np

from .audio_io import ANALYSIS_SR, decode
from .ui.tokens import SIZE_WAVE_BUCKETS

#: Quantas colunas o render tem disponiveis. Vem do design system.
PEAKS_BUCKETS: int = int(SIZE_WAVE_BUCKETS)

_N_FFT = 2048
_HOP = 512
_EPS = 1e-9

#: Cortes das tres bandas, em Hz. Os mesmos limites que descriptors.py ja usa
#: para low_band_ratio/high_band_ratio -- manter os dois alinhados evita que a
#: onda mostre uma coisa e o modelo enxergue outra.
_CORTE_GRAVE = 250.0
_CORTE_AGUDO = 4000.0


def _resample_max(bandas: np.ndarray, buckets: int) -> np.ndarray:
    """Reduz (N, 3) para (buckets, 3) pegando o maximo de cada balde.

    Maximo e nao media de proposito: media achata transientes, e a onda perde
    justamente a informacao de ataque que o DJ procura. Mesma regra do
    _resample mono em waveform_render.py.
    """
    if buckets <= 0:
        return np.zeros((0, 3), dtype=np.float32)
    if len(bandas) == 0:
        return np.zeros((buckets, 3), dtype=np.float32)
    if len(bandas) <= buckets:
        # Track curta: repete a ultima coluna ate encher. Um segundo de audio
        # da ~44 frames de STFT contra 2000 buckets, entao este ramo e o caso
        # comum de qualquer coisa abaixo de ~45s, nao uma borda rara.
        return np.pad(
            bandas, ((0, buckets - len(bandas)), (0, 0)), mode="edge"
        ).astype(np.float32)

    bordas = np.linspace(0, len(bandas), buckets + 1, dtype=int)
    return np.stack(
        [bandas[bordas[i] : bordas[i + 1]].max(axis=0) for i in range(buckets)]
    ).astype(np.float32)


def compute_bands(path: Path, buckets: int = PEAKS_BUCKETS) -> np.ndarray:
    """Devolve (buckets, 3) float16 em [0, 1]: energia de grave, medio, agudo.

    float16 porque sao 2000x3 valores por track que so alimentam cores de 8
    bits -- float32 dobraria o disco sem mudar um pixel.

    Levanta AudioDecodeError se o arquivo nao decodifica. A contencao e de
    quem chama: o servico precisa distinguir "esta track nao tem onda" de
    "o scan inteiro falhou".
    """
    y = decode(Path(path), sample_rate=ANALYSIS_SR)

    espectro = np.abs(librosa.stft(y, n_fft=_N_FFT, hop_length=_HOP))
    frequencias = librosa.fft_frequencies(sr=ANALYSIS_SR, n_fft=_N_FFT)

    grave = espectro[frequencias < _CORTE_GRAVE].sum(axis=0)
    medio = espectro[
        (frequencias >= _CORTE_GRAVE) & (frequencias < _CORTE_AGUDO)
    ].sum(axis=0)
    agudo = espectro[frequencias >= _CORTE_AGUDO].sum(axis=0)

    bandas = _resample_max(np.stack([grave, medio, agudo], axis=1), buckets)

    # Normaliza pelo maximo GLOBAL das tres bandas, nao por banda: normalizar
    # cada canal em separado faria toda track parecer ter agudo forte, porque
    # o canal mais fraco seria esticado ate 1.0 e a cor perderia o sentido.
    # O epsilon segura o caso do silencio absoluto, onde o maximo e zero e a
    # divisao produziria NaN em toda a onda, sem erro nenhum.
    pico = float(bandas.max()) + _EPS
    return np.clip(bandas / pico, 0.0, 1.0).astype(np.float16)
```

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_peaks.py -v`
Expected: PASS nos oito.

- [ ] **Step 5: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS. Nada fora do modulo novo foi tocado.

> Se o ruff reclamar do import `from .ui.tokens import SIZE_WAVE_BUCKETS`
> (dominio importando de `ui/`), NAO mova o token: `tokens.py` e um modulo
> gerado de constantes puras, sem Qt, e duplicar o `2000` aqui criaria duas
> fontes de verdade para o mesmo numero. Se preferir evitar a direcao do
> import, o certo e mover o valor para `design-tokens.json` e reexporta-lo —
> mas isso e mudanca de design system, fora do escopo desta fase. Registre a
> duvida no relatorio em vez de decidir sozinho.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/peaks.py tests/test_peaks.py
git commit -m "feat(trackclassifier): computo dos buckets de energia por banda"
```

---

### Task 2: Armazenamento dos buckets em disco

**Files:**
- Modify: `src/trackclassifier/presentation.py`
- Modify: `tests/test_presentation.py`

**Interfaces:**
- Consumes: `PRESENTATION_VERSION` (ja existe em `presentation.py`, valor `1`).
- Produces:
  - `PeaksStore(peaks_dir: Path)` com:
    - `path_for(sha1: str) -> Path | None` — caminho do `.npy` se existir no disco, senao `None`
    - `put(sha1: str, bands: np.ndarray) -> Path` — grava atomicamente, devolve o caminho
    - `has(sha1: str) -> bool`

> **Atencao:** `presentation.py` hoje NAO importa `numpy`. Acrescente o import
> no bloco de terceiros, junto de `mutagen` e `pandas` (ruff `I` exige a ordem
> `import mutagen`, `import numpy as np`, `import pandas as pd`).

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_presentation.py`:

```python
def _peaks_store(tmp_path):
    from trackclassifier.presentation import PeaksStore

    return PeaksStore(tmp_path / "peaks")


def _bandas_falsas(buckets=8):
    import numpy as np

    return np.linspace(0.0, 1.0, buckets * 3, dtype=np.float16).reshape(buckets, 3)


def test_peaks_store_grava_e_devolve_o_caminho(tmp_path):
    store = _peaks_store(tmp_path)

    caminho = store.put("abc123", _bandas_falsas())

    assert caminho.name == "abc123.npy"
    assert caminho.is_file()
    assert store.path_for("abc123") == caminho


def test_peaks_store_sha1_desconhecida_devolve_none(tmp_path):
    store = _peaks_store(tmp_path)

    assert store.path_for("nunca-visto") is None
    assert store.has("nunca-visto") is False


def test_peaks_store_roundtrip_preserva_os_valores(tmp_path):
    import numpy as np

    store = _peaks_store(tmp_path)
    original = _bandas_falsas()

    caminho = store.put("abc123", original)
    carregado = np.load(caminho)

    assert carregado.shape == original.shape
    assert carregado.dtype == np.float16
    assert np.array_equal(carregado, original)


def test_peaks_store_nao_deixa_tmp_para_tras(tmp_path):
    # np.save anexa ".npy" quando o caminho nao termina nisso -- um tmp
    # chamado "abc.npy.tmp" viraria "abc.npy.tmp.npy" e o os.replace
    # seguinte falharia com FileNotFoundError. O tmp precisa JA terminar
    # em .npy.
    store = _peaks_store(tmp_path)

    store.put("abc123", _bandas_falsas())

    arquivos = sorted(p.name for p in (tmp_path / "peaks").iterdir())
    assert arquivos == ["abc123.npy"]


def test_peaks_store_sobrescreve_entrada_existente(tmp_path):
    import numpy as np

    store = _peaks_store(tmp_path)
    store.put("abc123", np.zeros((4, 3), dtype=np.float16))

    store.put("abc123", np.ones((4, 3), dtype=np.float16))

    assert float(np.load(store.path_for("abc123")).max()) == 1.0


def test_peaks_store_arquivo_corrompido_nao_e_oferecido(tmp_path):
    # np.load de um arquivo invalido levanta ValueError (nao OSError). Um
    # .npy truncado por interrupcao nao pode virar excecao na tela.
    store = _peaks_store(tmp_path)
    store.put("abc123", _bandas_falsas())
    store.path_for("abc123").write_bytes(b"isto nao e um npy")

    assert store.path_for("abc123") is None
    assert store.has("abc123") is False
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_presentation.py -v -k peaks`
Expected: FAIL com `ImportError: cannot import name 'PeaksStore'`

- [ ] **Step 3: Implementar `PeaksStore`**

Acrescente `import numpy as np` ao bloco de imports de terceiros de
`src/trackclassifier/presentation.py` (a ordem final e `import mutagen`,
`import numpy as np`, `import pandas as pd`), e a classe ao fim do arquivo:

```python
class PeaksStore:
    """Buckets de energia por banda, um .npy por track.

    Fora do parquet pelo mesmo motivo das capas: sao 2000x3 float16 por
    track, e um acervo de centenas viraria dezenas de MB que o pandas leria
    inteiros para a memoria no boot da janela, para desenhar as ~20 linhas
    visiveis. Em arquivo, o numpy carrega so o que a tela pediu.

    A validade e por PRESENTATION_VERSION, igual ao resto da apresentacao:
    quem bumpar a versao precisa limpar este diretorio (ver a nota em
    CLAUDE.md), porque um .npy sozinho nao carrega a versao dentro dele.
    """

    def __init__(self, peaks_dir: Path):
        self.peaks_dir = Path(peaks_dir)

    def _caminho(self, sha1: str) -> Path:
        return self.peaks_dir / f"{sha1}.npy"

    def path_for(self, sha1: str) -> Path | None:
        """Caminho do .npy, ou None se nao existe ou nao e legivel."""
        caminho = self._caminho(sha1)
        if not caminho.is_file():
            return None
        try:
            np.load(caminho, mmap_mode="r")
        except Exception:
            # np.load levanta ValueError (nao OSError) num arquivo invalido:
            # um .npy truncado por interrupcao no meio da escrita chega aqui.
            # Tratar como ausente faz a onda cair no render mono, que e o
            # comportamento certo -- melhor uma onda simples que um traceback.
            return None
        return caminho

    def has(self, sha1: str) -> bool:
        return self.path_for(sha1) is not None

    def put(self, sha1: str, bands: np.ndarray) -> Path:
        self.peaks_dir.mkdir(parents=True, exist_ok=True)
        destino = self._caminho(sha1)
        # O tmp precisa JA terminar em .npy: np.save anexa a extensao quando
        # o caminho nao a tem, entao um "abc.npy.tmp" viraria
        # "abc.npy.tmp.npy" e o os.replace abaixo nao acharia o arquivo.
        tmp = destino.with_name(destino.stem + ".tmp" + destino.suffix)
        np.save(tmp, bands)
        os.replace(tmp, destino)
        return destino
```

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_presentation.py -v`
Expected: PASS em todos (os da fase 2 e os seis novos).

- [ ] **Step 5: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/presentation.py tests/test_presentation.py
git commit -m "feat(trackclassifier): armazenamento dos buckets de banda em disco"
```

---

### Task 3: `ensure_peaks` e `peaks_for` no servico

**Files:**
- Modify: `src/trackclassifier/service.py`
- Modify: `tests/test_service.py`

**Interfaces:**
- Consumes: `PeaksStore` (Task 2), `compute_bands` (Task 1).
- Produces:
  - `TrackService.peaks: PeaksStore` (atributo publico)
  - `TrackService.peaks_for(sha1: str) -> Path | None`
  - `TrackService.ensure_peaks(sha1: str, path: Path) -> Path | None` — computa se faltar, devolve o caminho ou `None` se falhou

> **Atencao:** importe os nomes **direto** (`from .peaks import compute_bands`),
> nao `from . import peaks`. Os testes fazem monkey-patch de
> `trackclassifier.service.compute_bands`, que so funciona com o import direto —
> mesmo padrao que `tests/test_library.py` usa para `file_sha1` e que a fase 2
> usa para `read_tags`.

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_service.py`:

```python
def _com_audio_real(config, nome="real_0.500.wav"):
    """Grava um .wav DECODIFICAVEL numa pasta rotulada e devolve o caminho.

    `_povoa` grava `b"-10"` em arquivos `.mp3` -- suficiente para o
    ExtratorFalso (que le o vetor do NOME do arquivo, sem tocar no conteudo),
    mas o ffmpeg nao decodifica nada disso. `compute_bands` decodifica de
    verdade, entao todo teste do caminho de SUCESSO precisa de audio real.
    O nome segue o padrao `<algo>_<energia>.wav` porque o ExtratorFalso faz
    `float(stem.split("_")[-1])`.
    """
    from trackclassifier.labels import Label

    sr = 22050
    t = np.linspace(0, 12.0, int(sr * 12), endpoint=False)
    sinal = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    caminho = config.folders[Label.UP] / nome
    sf.write(caminho, sinal, sr)
    return caminho


def test_ensure_peaks_computa_e_grava_na_primeira_chamada(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    alvo = _com_audio_real(config)
    servico = _servico(config)

    ref = next(r for r in servico._labeled if r.path.name == alvo.name)
    caminho = servico.ensure_peaks(ref.sha1, ref.path)

    assert caminho is not None
    assert caminho.is_file()
    assert servico.peaks_for(ref.sha1) == caminho


def test_ensure_peaks_nao_recomputa_o_que_ja_existe(tmp_path):
    import trackclassifier.service as modulo

    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    alvo = _com_audio_real(config)
    servico = _servico(config)
    ref = next(r for r in servico._labeled if r.path.name == alvo.name)
    assert servico.ensure_peaks(ref.sha1, ref.path) is not None

    chamadas = {"n": 0}
    original = modulo.compute_bands

    def _espiao(caminho, buckets=None):
        chamadas["n"] += 1
        return original(caminho)

    modulo.compute_bands = _espiao
    try:
        servico.ensure_peaks(ref.sha1, ref.path)
    finally:
        modulo.compute_bands = original

    assert chamadas["n"] == 0


def test_ensure_peaks_de_arquivo_ilegivel_devolve_none_sem_estourar(tmp_path):
    # _povoa grava bytes que nao sao audio de verdade -- o ffmpeg falha, e
    # isso NAO pode derrubar a janela nem entrar em failures(): a track
    # continua classificavel, so fica sem onda colorida.
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    servico = _servico(config)
    ref = servico._labeled[0]

    assert servico.ensure_peaks(ref.sha1, ref.path) is None
    assert servico.failures() == []


def test_peaks_for_sem_computo_previo_devolve_none(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)
    servico = _servico(config)

    assert servico.peaks_for(servico._labeled[0].sha1) is None


def test_scan_nao_computa_buckets(tmp_path):
    # Os buckets sao preguicosos por design: o scan ja custa 5-15s por track
    # so com as features, e somar a STFT completa da onda a isso dobraria o
    # tempo de um scan grande para dado que talvez nunca apareca na tela.
    import trackclassifier.service as modulo

    config = _config(tmp_path)
    _povoa(config, n_por_classe=2)

    chamadas = {"n": 0}
    original = modulo.compute_bands

    def _espiao(caminho, buckets=None):
        chamadas["n"] += 1
        return original(caminho)

    modulo.compute_bands = _espiao
    try:
        TrackService(config, extractor=ExtratorFalso(), max_workers=1).analyze_all()
    finally:
        modulo.compute_bands = original

    assert chamadas["n"] == 0
```

> **A divisao entre `_com_audio_real` e `_povoa` e proposital**, nao descuido:
> os testes do caminho de SUCESSO precisam de audio que o ffmpeg decodifique,
> e o teste do caminho de FALHA (`..._de_arquivo_ilegivel_...`) usa justamente
> os `.mp3` falsos do `_povoa` para provar que uma track indecodificavel
> devolve `None` sem derrubar nada. Nao unifique as duas fixtures.

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_service.py -v -k peaks`
Expected: FAIL com `AttributeError: 'TrackService' object has no attribute 'ensure_peaks'`

- [ ] **Step 3: Importar e instanciar**

Em `src/trackclassifier/service.py`, acrescente ao bloco de imports locais:

```python
from .peaks import compute_bands
```

e acrescente `PeaksStore` ao import existente de `.presentation`, que passa a ser:

```python
from .presentation import (
    VAZIO,
    PeaksStore,
    PresentationCache,
    PresentationRecord,
    extract_cover,
    read_tags,
)
```

Em `TrackService.__init__`, logo depois da linha que cria `self.presentation`:

```python
        self.peaks = PeaksStore(config.data_dir / "peaks")
```

- [ ] **Step 4: Implementar os dois metodos**

Acrescente a `TrackService`, logo depois de `cover_path_for`:

```python
    def peaks_for(self, sha1: str) -> Path | None:
        """Caminho dos buckets ja computados, ou None. Nunca computa."""
        return self.peaks.path_for(sha1)

    def ensure_peaks(self, sha1: str, path: Path) -> Path | None:
        """Computa os buckets se ainda nao existirem. Devolve o caminho ou None.

        Chamado sob demanda pela tela, nunca pelo scan: a STFT da track
        inteira custa alguns segundos, e paga-la durante o scan dobraria o
        tempo de uma biblioteca grande para produzir dado que talvez nunca
        apareca na tela.

        Falha vira None, nao excecao e nao FailedItem: uma track sem onda
        colorida continua perfeitamente classificavel, e poluir a aba Modelo
        com isso esconderia as falhas de analise, que sao as que importam.
        """
        existente = self.peaks.path_for(sha1)
        if existente is not None:
            return existente

        try:
            bandas = compute_bands(Path(path))
        except Exception:
            # AudioDecodeError (arquivo sumiu, formato quebrado, ffmpeg
            # travado) ou qualquer falha do librosa. A onda cai no render
            # mono e o usuario nem percebe.
            return None

        try:
            return self.peaks.put(sha1, bandas)
        except OSError:
            # Disco cheio ou permissao: o computo foi em vao, mas a tela
            # segue funcionando com o fallback mono.
            return None
```

- [ ] **Step 5: Rodar os testes**

Run: `uv run pytest tests/test_service.py -v`
Expected: PASS. Os testes de cancelamento e de apresentacao da fase 2 continuam passando — `ensure_peaks` nao e chamado por `analyze_all`.

- [ ] **Step 6: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/trackclassifier/service.py tests/test_service.py
git commit -m "feat(trackclassifier): computo sob demanda dos buckets de banda"
```

---

### Task 4: `TrackRow.peaks_path`

**Files:**
- Modify: `src/trackclassifier/ui/viewmodel.py`
- Modify: `tests/test_viewmodel.py`

**Interfaces:**
- Consumes: `TrackService.peaks_for(sha1) -> Path | None` (Task 3).
- Produces: `TrackRow.peaks_path: str | None` (default `None`).

> **Atencao:** `TrackRow` e construida em DOIS lugares de `viewmodel.py` —
> `_row_da_fila(item, service)` e o laco de `library_state(service)`. Os dois
> precisam preencher o campo novo, lendo de `service.peaks_for(sha1)`.

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_viewmodel.py`:

```python
def test_track_row_traz_o_caminho_dos_buckets_quando_existem(tmp_path):
    import numpy as np

    config = _config(tmp_path)
    servico = _servico(config)

    ref = servico._labeled[0]
    servico.peaks.put(ref.sha1, np.zeros((8, 3), dtype=np.float16))

    linha = next(
        linha for linha in viewmodel.library_state(servico).rows if linha.sha1 == ref.sha1
    )
    assert linha.peaks_path is not None
    assert linha.peaks_path.endswith(f"{ref.sha1}.npy")


def test_track_row_sem_buckets_tem_peaks_path_none(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    linha = viewmodel.library_state(servico).rows[0]

    assert linha.peaks_path is None


def test_row_da_fila_tambem_traz_o_caminho_dos_buckets(tmp_path):
    import numpy as np

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    sha1 = servico.queue()[0].sha1
    servico.peaks.put(sha1, np.zeros((8, 3), dtype=np.float16))

    estado = viewmodel.review_state(servico)
    assert estado.current is not None
    assert estado.current.peaks_path is not None
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_viewmodel.py -v -k buckets`
Expected: FAIL com `AttributeError: 'TrackRow' object has no attribute 'peaks_path'`

- [ ] **Step 3: Acrescentar o campo**

Em `src/trackclassifier/ui/viewmodel.py`, acrescente ao final da dataclass
`TrackRow`, depois de `cover_path`:

```python
    #: Caminho de peaks/<sha1>.npy quando os buckets por banda ja foram
    #: computados; None enquanto nao foram. Enquanto e None, a onda cai no
    #: render mono derivado de energy_curve -- por isso energy_curve nao pode
    #: sumir da TrackRow, mesmo depois do RGB existir. String (nao Path) pelo
    #: mesmo motivo de path_hint e cover_path: este modulo e a fronteira de
    #: dados puros.
    peaks_path: str | None = None
```

- [ ] **Step 4: Preencher nos dois construtores**

Em `_row_da_fila`, acrescente antes do `return`:

```python
    picos = service.peaks_for(item.sha1)
```

e o campo, ao final da construcao da `TrackRow`:

```python
        peaks_path=str(picos) if picos is not None else None,
```

Em `library_state`, dentro do laco, acrescente junto de `capa`:

```python
        picos = service.peaks_for(ref.sha1)
```

e o campo, ao final da construcao da `TrackRow`:

```python
                peaks_path=str(picos) if picos is not None else None,
```

- [ ] **Step 5: Rodar os testes**

Run: `uv run pytest tests/test_viewmodel.py -v`
Expected: PASS, inclusive `test_viewmodel_nao_importa_qt`.

- [ ] **Step 6: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/trackclassifier/ui/viewmodel.py tests/test_viewmodel.py
git commit -m "feat(ui): TrackRow carrega o caminho dos buckets de banda"
```

---

### Task 5: `render_bands` e `load_peaks`

**Files:**
- Modify: `src/trackclassifier/ui/widgets/waveform_render.py`
- Modify: `tests/test_waveform_render.py`

**Interfaces:**
- Consumes: tokens `COLOR_WAVEBAND_LOW_GAIN`, `COLOR_WAVEBAND_MID_GAIN`, `COLOR_WAVEBAND_HIGH_GAIN`, `COLOR_WAVEBAND_FLOOR`, `COLOR_SURFACE_WAVEFORM` (ja existem em `ui/tokens.py`).
- Produces:
  - `load_peaks(path: str | None) -> np.ndarray | None`
  - `render_bands(peaks: np.ndarray, size: QSize, bar_width: int = 2, gap: int = 0, background: QColor | None = None) -> QPixmap`

> **`render_curve` continua existindo e nao muda.** E o fallback de toda track
> sem buckets. Remove-la quebraria a Biblioteca inteira no primeiro boot depois
> de um bump de `PRESENTATION_VERSION`.

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_waveform_render.py`:

```python
def _bandas(low, mid, high, buckets=64):
    import numpy as np

    banda = np.zeros((buckets, 3), dtype=np.float16)
    banda[:, 0] = low
    banda[:, 1] = mid
    banda[:, 2] = high
    return banda


def test_render_bands_devolve_pixmap_do_tamanho_pedido(qapp):
    from PySide6.QtCore import QSize

    from trackclassifier.ui.widgets.waveform_render import render_bands

    pixmap = render_bands(_bandas(0.5, 0.5, 0.5), QSize(120, 18))

    assert pixmap.width() == 120
    assert pixmap.height() == 18


def test_render_bands_de_grave_sai_vermelho_dominante(qapp):
    from PySide6.QtCore import QSize

    from trackclassifier.ui.widgets.waveform_render import render_bands

    imagem = render_bands(_bandas(1.0, 0.05, 0.05), QSize(60, 20)).toImage()

    # Coluna central, na altura do meio: onde a barra com certeza foi pintada.
    cor = imagem.pixelColor(30, 10)
    assert cor.red() > cor.green()
    assert cor.red() > cor.blue()


def test_render_bands_de_agudo_sai_azul_dominante(qapp):
    from PySide6.QtCore import QSize

    from trackclassifier.ui.widgets.waveform_render import render_bands

    imagem = render_bands(_bandas(0.05, 0.05, 1.0), QSize(60, 20)).toImage()

    cor = imagem.pixelColor(30, 10)
    assert cor.blue() > cor.red()
    assert cor.blue() > cor.green()


def test_render_bands_com_array_vazio_nao_quebra(qapp):
    import numpy as np
    from PySide6.QtCore import QSize

    from trackclassifier.ui.widgets.waveform_render import render_bands

    pixmap = render_bands(np.zeros((0, 3), dtype=np.float16), QSize(50, 10))

    assert pixmap.width() == 50


def test_load_peaks_le_o_arquivo_gravado(tmp_path):
    import numpy as np

    from trackclassifier.ui.widgets.waveform_render import load_peaks

    caminho = tmp_path / "abc.npy"
    np.save(caminho, _bandas(0.3, 0.4, 0.5))

    carregado = load_peaks(str(caminho))

    assert carregado is not None
    assert carregado.shape == (64, 3)


def test_load_peaks_de_none_devolve_none(tmp_path):
    from trackclassifier.ui.widgets.waveform_render import load_peaks

    assert load_peaks(None) is None


def test_load_peaks_de_arquivo_corrompido_devolve_none(tmp_path):
    # np.load levanta ValueError num arquivo invalido -- a onda tem que cair
    # no fallback mono em vez de derrubar o paint().
    from trackclassifier.ui.widgets.waveform_render import load_peaks

    caminho = tmp_path / "ruim.npy"
    caminho.write_bytes(b"isto nao e um npy")

    assert load_peaks(str(caminho)) is None


def test_load_peaks_de_arquivo_inexistente_devolve_none(tmp_path):
    from trackclassifier.ui.widgets.waveform_render import load_peaks

    assert load_peaks(str(tmp_path / "nao_existe.npy")) is None
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_waveform_render.py -v -k "bands or peaks"`
Expected: FAIL com `ImportError: cannot import name 'render_bands'`

- [ ] **Step 3: Implementar**

Em `src/trackclassifier/ui/widgets/waveform_render.py`, atualize o import de
tokens para incluir os ganhos:

```python
from ..tokens import (
    COLOR_ACCENT_BASE,
    COLOR_SURFACE_WAVEFORM,
    COLOR_WAVEBAND_FLOOR,
    COLOR_WAVEBAND_HIGH_GAIN,
    COLOR_WAVEBAND_LOW_GAIN,
    COLOR_WAVEBAND_MID_GAIN,
)
```

E acrescente, depois de `render_curve`:

```python
#: Os ganhos em tokens.py sao STRINGS ("1.00", "0.92"), nao floats -- o
#: build_tokens.py emite tudo do JSON como string. A conversao explicita
#: aqui e o que evita um TypeError na multiplicacao com o array numpy.
_GANHOS = np.array(
    [
        float(COLOR_WAVEBAND_LOW_GAIN),
        float(COLOR_WAVEBAND_MID_GAIN),
        float(COLOR_WAVEBAND_HIGH_GAIN),
    ],
    dtype=np.float32,
)
_PISO = float(COLOR_WAVEBAND_FLOOR)

#: Peso de cada banda na ALTURA da barra (a cor vem do RGB direto). Graves
#: pesam mais porque e o que da a silhueta reconhecivel de uma track -- uma
#: onda ponderada igualmente vira um bloco sem forma. O 1.5 compensa o fato
#: de os tres pesos somarem 1.0 e a maioria das tracks nunca saturar as tres
#: bandas ao mesmo tempo.
_PESOS_ALTURA = np.array([0.55, 0.30, 0.15], dtype=np.float32)
_GANHO_ALTURA = 1.5


def load_peaks(path: str | None) -> np.ndarray | None:
    """Le um .npy de buckets. Devolve None em qualquer problema.

    Chamado de dentro de paint(): nao pode levantar. Um .npy truncado por
    interrupcao faz a onda cair no render mono, que e o comportamento certo.
    """
    if path is None:
        return None
    try:
        return np.load(path)
    except Exception:
        # np.load levanta ValueError (nao OSError) num arquivo invalido, e
        # FileNotFoundError se o arquivo sumiu entre o viewmodel montar a
        # linha e o paint acontecer.
        return None


def _cores(bandas: np.ndarray) -> np.ndarray:
    """(barras, 3) normalizado -> (barras, 3) uint8 pronto para QColor.

    O piso existe para uma banda zerada nao virar preto absoluto: uma coluna
    so de graves ficaria vermelho puro sobre fundo escuro e sumiria nas
    bordas. Com o piso ela mantem um minimo de presenca nos outros canais.
    """
    escalado = _PISO + (1.0 - _PISO) * np.clip(bandas, 0.0, 1.0) * _GANHOS
    return (np.clip(escalado, 0.0, 1.0) * 255).astype(np.uint8)


def _resample_bandas(picos: np.ndarray, barras: int) -> np.ndarray:
    """Reduz (N, 3) para (barras, 3) pelo maximo, igual ao mono."""
    if barras <= 0 or len(picos) == 0:
        return np.zeros((max(0, barras), 3), dtype=np.float32)
    if len(picos) <= barras:
        return np.pad(
            picos.astype(np.float32), ((0, barras - len(picos)), (0, 0)), mode="edge"
        )

    bordas = np.linspace(0, len(picos), barras + 1, dtype=int)
    return np.stack(
        [picos[bordas[i] : bordas[i + 1]].max(axis=0) for i in range(barras)]
    ).astype(np.float32)


def render_bands(
    peaks: np.ndarray,
    size: QSize,
    bar_width: int = 2,
    gap: int = 0,
    background: QColor | None = None,
) -> QPixmap:
    """Desenha a onda RGB: a cor de cada coluna E a energia das tres bandas.

    Nao e um gradiente aplicado sobre uma envoltoria -- graves viram vermelho,
    medios verde, agudos azul, e a mistura resultante e a cor da coluna.

    Chame uma vez por track e guarde o resultado, igual ao render_curve:
    redesenhar dentro de paint() com dezenas de linhas visiveis derruba o
    scroll.
    """
    largura = max(1, size.width())
    altura = max(1, size.height())

    imagem = QImage(largura, altura, QImage.Format.Format_ARGB32_Premultiplied)
    imagem.fill(background if background is not None else QColor(COLOR_SURFACE_WAVEFORM))

    picos = np.asarray(peaks, dtype=np.float32)
    if picos.size:
        passo = max(1, bar_width + gap)
        barras = max(1, largura // passo)
        bandas = _resample_bandas(picos, barras)
        cores = _cores(bandas)
        amplitude = np.clip(bandas @ _PESOS_ALTURA * _GANHO_ALTURA, 0.0, 1.0)

        pintor = QPainter(imagem)
        pintor.setPen(Qt.PenStyle.NoPen)
        for i in range(barras):
            altura_barra = max(1.0, float(amplitude[i]) * altura)
            y = (altura - altura_barra) / 2.0
            r, g, b = cores[i]
            pintor.fillRect(
                int(i * passo),
                int(y),
                bar_width,
                int(round(altura_barra)),
                QColor(int(r), int(g), int(b)),
            )
        pintor.end()

    return QPixmap.fromImage(imagem)
```

Atualize tambem a docstring do modulo, que hoje diz que o RGB "entra na fase 3":

```python
"""Render da onda. Um so lugar, usado pela onda grande e pela mini.

Dois modos coexistem de proposito: `render_bands` desenha o RGB por banda
(graves no vermelho, medios no verde, agudos no azul) quando os buckets ja
foram computados, e `render_curve` desenha o mono derivado do energy_curve
quando ainda nao foram. O mono nao e legado -- e o fallback que mantem a
tela util enquanto o computo preguicoso nao chegou naquela track.
"""
```

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_waveform_render.py -v`
Expected: PASS em todos (os da fase 1 e os oito novos).

- [ ] **Step 5: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/ui/widgets/waveform_render.py tests/test_waveform_render.py
git commit -m "feat(ui): render RGB por banda, com o mono como fallback"
```

---

### Task 6: Onda RGB na Revisao e na Biblioteca

**Files:**
- Modify: `src/trackclassifier/ui/widgets/waveform_view.py`
- Modify: `src/trackclassifier/ui/widgets/delegates.py`
- Modify: `tests/test_window.py`
- Modify: `tests/test_delegates.py`

**Interfaces:**
- Consumes: `render_bands`, `load_peaks` (Task 5); `TrackRow.peaks_path` (Task 4).
- Produces: nada consumido por outra tarefa.

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_delegates.py`:

```python
def test_delegate_da_onda_usa_rgb_quando_ha_buckets(qapp, tmp_path):
    # Prova que o ramo RGB e distinto do mono: as duas imagens da MESMA
    # track precisam diferir quando so o peaks_path muda.
    from dataclasses import replace

    import numpy as np

    from trackclassifier.ui.widgets.delegates import WaveformDelegate

    modelo = _modelo(tmp_path)
    linha = modelo.row_at(0)

    caminho = tmp_path / f"{linha.sha1}.npy"
    bandas = np.zeros((64, 3), dtype=np.float16)
    bandas[:, 0] = 1.0  # grave puro: bem diferente do accent do render mono
    np.save(caminho, bandas)

    modelo.set_rows([replace(linha, peaks_path=str(caminho))])
    com_rgb = _pinta(WaveformDelegate(), modelo.index(0, Column.WAVEFORM), False)

    modelo.set_rows([replace(linha, peaks_path=None)])
    com_mono = _pinta(WaveformDelegate(), modelo.index(0, Column.WAVEFORM), False)

    assert com_rgb != com_mono


def test_delegate_da_onda_cai_no_mono_com_npy_corrompido(qapp, tmp_path):
    # O paint() nao pode levantar por causa de um arquivo truncado.
    from dataclasses import replace

    from trackclassifier.ui.widgets.delegates import WaveformDelegate

    modelo = _modelo(tmp_path)
    linha = modelo.row_at(0)

    caminho = tmp_path / f"{linha.sha1}.npy"
    caminho.write_bytes(b"isto nao e um npy")
    modelo.set_rows([replace(linha, peaks_path=str(caminho))])

    imagem = _pinta(WaveformDelegate(), modelo.index(0, Column.WAVEFORM), False)

    assert not imagem.isNull()


def test_delegate_pede_computo_de_quem_nao_tem_buckets(qapp, tmp_path):
    # E o gatilho preguicoso: pintar uma linha sem buckets enfileira o
    # computo, e a mesma linha nao pode pedir duas vezes.
    from trackclassifier.ui.widgets.delegates import WaveformDelegate

    modelo = _modelo(tmp_path)
    delegate = WaveformDelegate()
    pedidos = []
    delegate.peaks_requested.connect(lambda sha1, caminho: pedidos.append(sha1))

    index = modelo.index(0, Column.WAVEFORM)
    _pinta(delegate, index, False)
    _pinta(delegate, index, False)

    assert pedidos == [modelo.row_at(0).sha1]
```

Acrescente a `tests/test_window.py`:

```python
def test_waveform_view_desenha_rgb_quando_ha_buckets(qapp, tmp_path):
    """Testa o WaveformView direto, nao pela ReviewTab.

    Renderizar atraves da aba faria o tamanho do widget depender do layout
    ja ter rodado, e um widget de 0x0 produziria duas imagens vazias iguais
    -- o teste passaria sem provar nada. Com resize() direto no widget, o
    tamanho e deterministico.
    """
    from dataclasses import replace

    import numpy as np

    from trackclassifier.ui.widgets.waveform_view import WaveformView

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    estado = review_state(servico)
    assert estado.current is not None
    assert estado.current.energy_curve  # senao o fallback mono nao desenha nada

    caminho = tmp_path / "picos.npy"
    bandas = np.zeros((64, 3), dtype=np.float16)
    bandas[:, 2] = 1.0  # agudo puro: azul, bem longe do accent do mono
    np.save(caminho, bandas)

    view = WaveformView()
    view.resize(200, 40)

    view.set_row(estado.current)
    mono = view.grab().toImage()

    view.set_row(replace(estado.current, peaks_path=str(caminho)))
    rgb = view.grab().toImage()

    assert rgb != mono


def test_waveform_view_cai_no_mono_com_npy_corrompido(qapp, tmp_path):
    from dataclasses import replace

    import numpy as np

    from trackclassifier.ui.widgets.waveform_view import WaveformView

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    estado = review_state(servico)
    ruim = tmp_path / "ruim.npy"
    ruim.write_bytes(b"isto nao e um npy")

    view = WaveformView()
    view.resize(200, 40)

    view.set_row(estado.current)
    mono = view.grab().toImage()

    view.set_row(replace(estado.current, peaks_path=str(ruim)))
    apos_corrompido = view.grab().toImage()

    # Identicas: o .npy invalido some e sobra exatamente o render mono.
    assert apos_corrompido == mono


def test_revisao_pede_computo_dos_buckets_da_track_atual(qapp, tmp_path):
    import numpy as np

    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    pedidos = []
    aba.peaks_requested.connect(lambda sha1, caminho: pedidos.append(sha1))

    estado = review_state(servico)
    aba.set_state(estado)

    assert pedidos == [estado.current.sha1]
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_delegates.py tests/test_window.py -v -k "rgb or buckets or computo"`
Expected: FAIL com `AttributeError: 'WaveformDelegate' object has no attribute 'peaks_requested'`

- [ ] **Step 3: `WaveformView` escolhe o render**

Em `src/trackclassifier/ui/widgets/waveform_view.py`, troque o import:

```python
from .waveform_render import load_peaks, render_bands, render_curve
```

E substitua `paintEvent` por:

```python
    def paintEvent(self, event) -> None:
        pintor = QPainter(self)
        if self._row is None:
            pintor.fillRect(self.rect(), QColor(COLOR_SURFACE_WAVEFORM))
            return

        if self._pixmap is None:
            self._pixmap = self._monta_pixmap()
        if self._pixmap is None:
            pintor.fillRect(self.rect(), QColor(COLOR_SURFACE_WAVEFORM))
            return
        pintor.drawPixmap(0, 0, self._pixmap)

        x = int(self._progress * self.width())
        pintor.setPen(QColor(COLOR_WAVEBAND_PLAYHEAD))
        pintor.drawLine(x, 0, x, self.height())

    def _monta_pixmap(self):
        """RGB quando ha buckets, mono quando nao ha, nada quando nao ha dado.

        A ordem importa: os buckets sao o dado melhor, mas so existem depois
        do computo preguicoso rodar naquela track. Ate la, energy_curve ja
        veio do scan e da uma onda util.
        """
        assert self._row is not None
        picos = load_peaks(self._row.peaks_path)
        if picos is not None:
            return render_bands(picos, self.size())
        if self._row.energy_curve:
            return render_curve(self._row.energy_curve, self.size())
        return None
```

- [ ] **Step 4: `WaveformDelegate` escolhe o render e pede o computo**

Em `src/trackclassifier/ui/widgets/delegates.py`, troque o import:

```python
from .waveform_render import PixmapCache, load_peaks, render_bands, render_curve
```

Acrescente `Signal` ao import de `PySide6.QtCore`:

```python
from PySide6.QtCore import QModelIndex, QRect, QSize, Qt, Signal
```

E substitua a classe `WaveformDelegate` por:

```python
class WaveformDelegate(_DelegateComFundo):
    """Pinta a mini onda da linha. RGB quando ha buckets, mono quando nao.

    O pixmap e cacheado por (sha1, largura, altura). O paint() nunca
    decodifica audio nem recalcula a curva -- so faz drawPixmap.

    Quando a linha ainda nao tem buckets, emite peaks_requested uma vez por
    sha1: e o gatilho do computo preguicoso. Uma vez so, porque paint() roda
    dezenas de vezes por segundo durante o scroll e enfileirar o mesmo
    computo a cada quadro afogaria o worker.
    """

    #: (sha1, caminho do arquivo de audio)
    peaks_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None, margin: int = 4) -> None:
        super().__init__(parent)
        self._cache = PixmapCache(capacity=256)
        self._margin = margin
        self._pedidos: set[str] = set()

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        # Sempre antes de qualquer `return`: uma celula sem onda para desenhar
        # continua sendo uma celula selecionavel.
        self._pinta_fundo(painter, option, index)

        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None:
            return

        rect = option.rect.adjusted(self._margin, self._margin, -self._margin, -self._margin)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        picos = load_peaks(linha.peaks_path)
        if picos is None:
            self._pede_computo(linha)
            if not linha.energy_curve:
                return

        # A chave inclui se o render e RGB ou mono: sem isso, o pixmap mono
        # cacheado continuaria sendo servido depois de os buckets chegarem, e
        # a linha so viraria colorida ao ser redimensionada.
        modo = "rgb" if picos is not None else "mono"
        chave = (f"{linha.sha1}:{modo}", rect.width(), rect.height())
        pixmap = self._cache.get(chave)
        if pixmap is None:
            if picos is not None:
                pixmap = render_bands(
                    picos, QSize(rect.width(), rect.height()), bar_width=SIZE_WAVE_BAR, gap=0
                )
            else:
                pixmap = render_curve(
                    linha.energy_curve,
                    QSize(rect.width(), rect.height()),
                    bar_width=SIZE_WAVE_BAR,
                    gap=0,
                )
            self._cache.put(chave, pixmap)

        painter.drawPixmap(rect.topLeft(), pixmap)

    def _pede_computo(self, linha: TrackRow) -> None:
        if linha.sha1 in self._pedidos:
            return
        self._pedidos.add(linha.sha1)
        self.peaks_requested.emit(linha.sha1, linha.path_hint)

    def clear_cache(self) -> None:
        self._cache.clear()
        # Os pedidos tambem: um refresh completo pode significar que o
        # computo anterior falhou e vale tentar de novo.
        self._pedidos.clear()
```

> A chave do `PixmapCache` e `tuple[str, int, int]`; usar `f"{sha1}:{modo}"`
> como primeiro elemento mantem o tipo e resolve a invalidacao sem mudar a
> classe.

- [ ] **Step 5: `ReviewTab` repassa o pedido**

Em `src/trackclassifier/ui/review_tab.py`, acrescente o sinal a `ReviewTab`,
junto dos existentes:

```python
    #: (sha1, caminho do arquivo de audio) -- gatilho do computo preguicoso
    #: dos buckets da track atual.
    peaks_requested = Signal(str, str)
```

E, em `_atualiza_exibicao`, logo depois de `self._waveform.set_row(atual)`:

```python
        if atual.peaks_path is None:
            # A track exibida e a prioridade real: e onde o DJ decide, e onde
            # a onda grande ocupa a tela inteira. Pede sempre que trocar de
            # track sem buckets -- o servico ignora o pedido duplicado.
            self.peaks_requested.emit(atual.sha1, atual.path_hint)
```

- [ ] **Step 6: Rodar os testes**

Run: `uv run pytest tests/test_delegates.py tests/test_window.py -v`
Expected: PASS.

- [ ] **Step 7: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/trackclassifier/ui/widgets/waveform_view.py src/trackclassifier/ui/widgets/delegates.py src/trackclassifier/ui/review_tab.py tests/
git commit -m "feat(ui): onda RGB na Revisao e na Biblioteca, com fallback mono"
```

---

### Task 7: Ligar o computo ao worker

**Files:**
- Modify: `src/trackclassifier/ui/worker.py`
- Modify: `src/trackclassifier/ui/window.py`
- Modify: `src/trackclassifier/ui/library_tab.py`
- Modify: `tests/test_worker.py`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `TrackService.ensure_peaks(sha1, path)` (Task 3); `peaks_requested` de `WaveformDelegate` e `ReviewTab` (Task 6).
- Produces: nada consumido por outra tarefa. Esta e a ultima.

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_worker.py`:

```python
def test_compute_peaks_computa_e_reemite_os_estados(qapp, tmp_path):
    import numpy as np
    import soundfile as sf

    from tests.test_viewmodel import ExtratorFalso
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    # Audio de verdade: compute_bands roda ffmpeg + librosa, entao um arquivo
    # de bytes falsos falharia por decode, nao por logica.
    t = np.linspace(0, 12.0, int(22050 * 12), endpoint=False)
    sinal = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(config.inbox / "real_0.5.wav", sinal, 22050)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()
    sha1 = servico._inbox[0].sha1
    caminho = servico._inbox[0].path

    worker = ServiceWorker(servico)
    estados = []
    worker.states_changed.connect(lambda r, b, m: estados.append(r))

    worker.compute_peaks(sha1, str(caminho))

    assert servico.peaks_for(sha1) is not None
    assert len(estados) == 1


def test_compute_peaks_de_arquivo_ruim_nao_emite_error(qapp, tmp_path):
    # Ficar sem onda colorida nao e um erro que mereca a status bar: a track
    # continua classificavel e o fallback mono ja aparece.
    config = _config(tmp_path)
    servico = _servico(config)
    ref = servico._labeled[0]

    worker = ServiceWorker(servico)
    erros = []
    worker.error.connect(erros.append)

    worker.compute_peaks(ref.sha1, str(ref.path))

    assert erros == []


def test_compute_peaks_de_sha1_ja_computada_nao_recomputa(qapp, tmp_path):
    import numpy as np

    config = _config(tmp_path)
    servico = _servico(config)
    ref = servico._labeled[0]
    servico.peaks.put(ref.sha1, np.zeros((8, 3), dtype=np.float16))

    import trackclassifier.service as modulo

    chamadas = {"n": 0}
    original = modulo.compute_bands

    def _espiao(caminho, buckets=None):
        chamadas["n"] += 1
        return original(caminho)

    modulo.compute_bands = _espiao
    try:
        ServiceWorker(servico).compute_peaks(ref.sha1, str(ref.path))
    finally:
        modulo.compute_bands = original

    assert chamadas["n"] == 0
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_worker.py -v -k peaks`
Expected: FAIL com `AttributeError: 'ServiceWorker' object has no attribute 'compute_peaks'`

- [ ] **Step 3: Slot no worker**

Em `src/trackclassifier/ui/worker.py`, acrescente a `ServiceWorker`, depois de
`bulk_approve`:

```python
    @Slot(str, str)
    def compute_peaks(self, sha1: str, path: str) -> None:
        """Computa os buckets de uma track e reemite os estados.

        Roda na thread do servico como qualquer outro slot -- uma STFT de
        alguns segundos na thread da GUI congelaria a janela inteira.

        Falha nao emite error(): ficar sem onda colorida nao merece a status
        bar, porque o fallback mono ja aparece e a track continua
        classificavel. Emitir aqui encheria a barra de mensagens durante um
        scroll numa biblioteca com arquivos problematicos.
        """
        try:
            self._service.ensure_peaks(sha1, Path(path))
        except Exception:
            # ensure_peaks ja contem o que sabe conter; chegar aqui e algo
            # fora dele. Silencioso pelo mesmo motivo acima.
            return
        self.refresh()
```

E acrescente o import de `Path` ao topo do arquivo:

```python
from pathlib import Path
```

- [ ] **Step 4: Ligar os sinais na janela**

Em `src/trackclassifier/ui/window.py`, dentro de `_conecta`, acrescente:

```python
        self.review_tab.peaks_requested.connect(self._worker.compute_peaks)
        self.library_tab.peaks_requested.connect(self._worker.compute_peaks)
```

- [ ] **Step 5: Repassar o sinal na `LibraryTab`**

Em `src/trackclassifier/ui/library_tab.py`, acrescente o sinal a `LibraryTab`:

```python
    #: Repassado do WaveformDelegate: (sha1, caminho do arquivo de audio).
    peaks_requested = Signal(str, str)
```

E, em `_monta_tabela`, logo depois de criar `self._waveform_delegate`:

```python
        self._waveform_delegate.peaks_requested.connect(self.peaks_requested)
```

- [ ] **Step 6: Rodar os testes**

Run: `uv run pytest tests/test_worker.py -v`
Expected: PASS.

- [ ] **Step 7: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 8: Documentar em `CLAUDE.md`**

Na secao **Estado em disco**, depois do paragrafo do `presentation.parquet`,
acrescente:

```markdown
`peaks/<sha1>.npy` guarda os buckets de energia por banda (`peaks.py`,
`presentation.PeaksStore`): `(2000, 3)` float16 em `[0,1]`, graves/medios/agudos,
que alimentam a onda RGB. **Nao sao computados durante o scan** — a STFT da
track inteira custa alguns segundos e dobraria o tempo de um scan grande para
dado que talvez nunca apareca na tela. Sao preguicosos: a aba Revisao pede os
da track atual, e o `WaveformDelegate` pede os de uma linha ao pinta-la sem
eles. Enquanto nao existem, a onda cai no render mono derivado de
`energy_curve` — **por isso `energy_curve` nao pode sair de `TrackAnalysis`
nem de `TrackRow`**, mesmo agora que o RGB existe.

Um `.npy` nao carrega a versao dentro dele, entao **bumpar
`PRESENTATION_VERSION` nao invalida os buckets sozinho**: apague `peaks/` a mao
quando mudar o formato ou o calculo em `peaks.py`.
```

- [ ] **Step 9: Commit**

```bash
git add src/trackclassifier/ui/worker.py src/trackclassifier/ui/window.py src/trackclassifier/ui/library_tab.py tests/test_worker.py CLAUDE.md
git commit -m "feat(ui): computo preguicoso dos buckets pela thread do servico"
```

---

## Verificacao final da fase

Depois da Task 7, antes de fechar a branch:

- [ ] `uv run ruff check .` — sem achado.
- [ ] `uv run pytest` — tudo verde.
- [ ] `uv run dj review` numa pasta real: a Revisao mostra a onda colorida da track atual depois de 1-3s (mono antes disso), e rolar a Biblioteca vai colorindo as linhas conforme o computo chega.
- [ ] Confirmar que `.trackclassifier/peaks/` aparece e enche conforme as tracks sao vistas — e que um `dj scan` **nao** cria nada la.
- [ ] Apagar `peaks/` com a janela aberta e rolar a Biblioteca: as ondas voltam ao mono e sao recomputadas, sem erro na tela.

## Fora do escopo desta fase

Registrado para nao virar decisao silenciosa de quem implementa:

- **Key / Camelot / `KeyChip`** — fase 4.
- **Fila de prioridade por viewport**: rastrear o scroll real da `QTableView`, cancelar pedidos que saem da tela, pool dedicado. Ver "Decisao de escopo" acima — a forma simplificada foi escolhida deliberadamente.
- **Invalidacao automatica de `peaks/` no bump de `PRESENTATION_VERSION`** — documentada como passo manual em `CLAUDE.md`.
- **Remover `render_curve` ou `energy_curve`** — sao o fallback, nao legado.
- **Waveform com zoom ou scroll horizontal na Revisao** — a onda continua sendo a track inteira numa tela so.
