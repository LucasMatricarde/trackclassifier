# TrackClassifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir um sistema que aprende o critério pessoal de energia de um DJ (`+1` / `neutra` / `-1`) a partir das pastas já organizadas e pré-classifica novos downloads, com revisão humana num player web local.

**Architecture:** As pastas do disco são a fonte da verdade dos rótulos. Descritores de áudio são extraídos em janelas deslizantes e agregados em um vetor de 44 dimensões por track; uma regressão Ridge prevê um escore ordinal contínuo em `[0, 1]`, cortado em três faixas por limiares calibrados nos próprios dados. A extração fica atrás de um `Protocol` para permitir troca futura por embeddings. Cada correção humana move o arquivo para a pasta rotulada, o que aumenta o dataset e dispara retreino.

**Tech Stack:** Python (gerenciado por `uv`), `librosa` + `numpy` + `scipy` para análise de áudio, `pyloudnorm` para LUFS, `ffmpeg` para decodificação, `scikit-learn` para o modelo, `pandas` + `pyarrow` para cache, `FastAPI` + `uvicorn` para o servidor, HTML e JavaScript sem framework para a interface, `pytest` para testes.

## Global Constraints

- **Versão de Python:** `requires-python = ">=3.11,<3.14"`. `librosa` depende de `numba`, que não suporta Python 3.14. `uv` baixa o interpretador correto automaticamente.
- **`ffmpeg` é dependência externa obrigatória** e não está instalado nesta máquina. Instalar com `brew install ffmpeg` antes da Task 2.
- **Arquivos de áudio nunca são modificados.** Sem reescrita de tag ID3, sem recodificação do original. Movimentação preserva os bytes.
- **Mover, nunca copiar.** Colisão de nome gera sufixo. Nunca sobrescrever.
- **Taxa de amostragem interna de análise:** 22050 Hz, mono. Constante `ANALYSIS_SR`.
- **Vetor de features tem exatamente 44 dimensões:** 10 descritores × 4 estatísticas + 4 descritores globais.
- **Rótulos internos** são o enum `Label` com valores `"+1"`, `"neutra"`, `"-1"`. Ordem ordinal: `DOWN < NEUTRAL < UP`.
- **Textos de interface em português.** Mensagens de exceção também.
- **Raiz do projeto:** `ProjetosPessoais/TrackClassifier/`. Todos os caminhos abaixo são relativos a ela.
- **Todo comando é executado da raiz do projeto** com `uv run`.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `pyproject.toml` | Dependências e configuração do pytest |
| `config.example.toml` | Modelo de configuração para o usuário copiar |
| `src/trackclassifier/labels.py` | Enum `Label`, ordem ordinal, mapa rótulo → alvo numérico |
| `src/trackclassifier/config.py` | Leitura e validação do `config.toml` |
| `src/trackclassifier/audio_io.py` | Decodificação via ffmpeg, classificação de formato |
| `src/trackclassifier/descriptors.py` | Os 10 descritores de uma janela de áudio (funções puras) |
| `src/trackclassifier/features.py` | Janelamento, agregação estatística, descritores globais, `FeatureExtractor` |
| `src/trackclassifier/cache.py` | SHA1 de arquivo e persistência de análises em parquet |
| `src/trackclassifier/library.py` | Varredura das pastas rotuladas e da inbox |
| `src/trackclassifier/model.py` | Ridge, calibração de limiares, confiança, métricas, persistência |
| `src/trackclassifier/apply.py` | Movimentação de arquivos entre pastas |
| `src/trackclassifier/service.py` | Orquestração: analisar, prever, decidir, retreinar |
| `src/trackclassifier/web.py` | Endpoints HTTP da fila e das decisões |
| `src/trackclassifier/streaming.py` | Endpoint de áudio com HTTP range e transcodificação |
| `src/trackclassifier/static/index.html` | Interface de revisão |
| `src/trackclassifier/static/app.js` | Lógica da interface, sparkline, atalhos |
| `src/trackclassifier/cli.py` | Comandos `scan`, `review`, `train` |
| `tests/` | Um arquivo de teste por módulo |

---

### Task 1: Scaffolding, rótulos e configuração

**Files:**
- Create: `pyproject.toml`
- Create: `config.example.toml`
- Create: `.gitignore`
- Create: `src/trackclassifier/__init__.py`
- Create: `src/trackclassifier/labels.py`
- Create: `src/trackclassifier/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nada
- Produces:
  - `Label` (enum `str`) com membros `UP = "+1"`, `NEUTRAL = "neutra"`, `DOWN = "-1"`
  - `LABEL_ORDER: list[Label]` — `[DOWN, NEUTRAL, UP]`
  - `LABEL_TARGET: dict[Label, float]` — `{DOWN: 0.0, NEUTRAL: 0.5, UP: 1.0}`
  - `Config` (dataclass congelada) com campos `folders: dict[Label, Path]`, `inbox: Path`, `data_dir: Path`, `retrain_every: int`, `min_examples: int`
  - `load_config(path: Path) -> Config`
  - `ConfigError(Exception)`

- [ ] **Step 1: Criar `pyproject.toml`**

```toml
[project]
name = "trackclassifier"
version = "0.1.0"
description = "Classificacao automatica de tracks por energia para DJ"
requires-python = ">=3.11,<3.14"
dependencies = [
    "librosa>=0.10.2",
    "numpy>=1.26",
    "scipy>=1.11",
    "pyloudnorm>=0.1.1",
    "scikit-learn>=1.4",
    "pandas>=2.2",
    "pyarrow>=15.0",
    "joblib>=1.3",
    "fastapi>=0.110",
    "uvicorn>=0.29",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "soundfile>=0.12", "httpx>=0.27"]

[project.scripts]
dj = "trackclassifier.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/trackclassifier"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "."]
```

A raiz entra no `pythonpath` porque tasks posteriores reaproveitam fixtures entre
arquivos de teste via `from tests.test_service import ...`.

- [ ] **Step 2: Criar `.gitignore` e `config.example.toml`**

`.gitignore`:

```
__pycache__/
*.pyc
.venv/
.trackclassifier/
config.toml
```

`config.example.toml`:

```toml
# Copie para config.toml e ajuste os caminhos.

[folders]
up = "/Users/SEU_USUARIO/Music/Tracks +1"
neutral = "/Users/SEU_USUARIO/Music/Tracks"
down = "/Users/SEU_USUARIO/Music/Tracks -1"
inbox = "/Users/SEU_USUARIO/Downloads/DJ"

[model]
retrain_every = 10
min_examples = 15

[paths]
data_dir = ".trackclassifier"
```

- [ ] **Step 3: Criar `src/trackclassifier/__init__.py`, `tests/__init__.py` e `labels.py`**

`src/trackclassifier/__init__.py` e `tests/__init__.py` ficam vazios. O segundo é
obrigatório: sem ele, os imports `from tests.test_service import ...` das tasks
posteriores falham.

`labels.py`:

```python
from enum import Enum


class Label(str, Enum):
    UP = "+1"
    NEUTRAL = "neutra"
    DOWN = "-1"


LABEL_ORDER: list[Label] = [Label.DOWN, Label.NEUTRAL, Label.UP]

LABEL_TARGET: dict[Label, float] = {
    Label.DOWN: 0.0,
    Label.NEUTRAL: 0.5,
    Label.UP: 1.0,
}
```

- [ ] **Step 4: Escrever os testes que falham**

`tests/test_config.py`:

```python
import pytest

from trackclassifier.config import Config, ConfigError, load_config
from trackclassifier.labels import Label


def _write_config(tmp_path, folders_exist=True, extra=""):
    for name in ("up", "neutral", "down", "inbox"):
        if folders_exist:
            (tmp_path / name).mkdir()
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        f"""
[folders]
up = "{tmp_path / 'up'}"
neutral = "{tmp_path / 'neutral'}"
down = "{tmp_path / 'down'}"
inbox = "{tmp_path / 'inbox'}"

[model]
retrain_every = 10
min_examples = 15

[paths]
data_dir = "{tmp_path / 'data'}"
{extra}
""",
        encoding="utf-8",
    )
    return cfg


def test_carrega_configuracao_valida(tmp_path):
    config = load_config(_write_config(tmp_path))

    assert isinstance(config, Config)
    assert config.folders[Label.UP] == tmp_path / "up"
    assert config.folders[Label.NEUTRAL] == tmp_path / "neutral"
    assert config.folders[Label.DOWN] == tmp_path / "down"
    assert config.inbox == tmp_path / "inbox"
    assert config.retrain_every == 10
    assert config.min_examples == 15


def test_cria_data_dir_se_nao_existir(tmp_path):
    config = load_config(_write_config(tmp_path))

    assert config.data_dir.is_dir()


def test_erro_quando_pasta_rotulada_nao_existe(tmp_path):
    cfg = _write_config(tmp_path, folders_exist=False)

    with pytest.raises(ConfigError) as exc:
        load_config(cfg)

    assert "up" in str(exc.value)


def test_erro_quando_arquivo_de_config_nao_existe(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "inexistente.toml")
```

- [ ] **Step 5: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_config.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.config'`.

- [ ] **Step 6: Implementar `config.py`**

```python
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .labels import Label


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    folders: dict[Label, Path]
    inbox: Path
    data_dir: Path
    retrain_every: int
    min_examples: int


_KEY_TO_LABEL = {"up": Label.UP, "neutral": Label.NEUTRAL, "down": Label.DOWN}


def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Arquivo de configuracao nao encontrado: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    folders_raw = raw.get("folders", {})
    folders: dict[Label, Path] = {}
    for key, label in _KEY_TO_LABEL.items():
        if key not in folders_raw:
            raise ConfigError(f"Chave obrigatoria ausente em [folders]: {key}")
        folder = Path(folders_raw[key]).expanduser()
        if not folder.is_dir():
            raise ConfigError(f"Pasta configurada em [folders].{key} nao existe: {folder}")
        folders[label] = folder

    if "inbox" not in folders_raw:
        raise ConfigError("Chave obrigatoria ausente em [folders]: inbox")
    inbox = Path(folders_raw["inbox"]).expanduser()
    if not inbox.is_dir():
        raise ConfigError(f"Pasta configurada em [folders].inbox nao existe: {inbox}")

    data_dir = Path(raw.get("paths", {}).get("data_dir", ".trackclassifier")).expanduser()
    if not data_dir.is_absolute():
        data_dir = path.parent / data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    model_raw = raw.get("model", {})
    return Config(
        folders=folders,
        inbox=inbox,
        data_dir=data_dir,
        retrain_every=int(model_raw.get("retrain_every", 10)),
        min_examples=int(model_raw.get("min_examples", 15)),
    )
```

- [ ] **Step 7: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_config.py -v
```

Esperado: 4 testes PASS.

- [ ] **Step 8: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): scaffolding, rotulos e leitura de configuracao"
```

---

### Task 2: Decodificação de áudio via ffmpeg

**Files:**
- Create: `src/trackclassifier/audio_io.py`
- Test: `tests/test_audio_io.py`

**Interfaces:**
- Consumes: nada
- Produces:
  - `ANALYSIS_SR: int = 22050`
  - `SUPPORTED_SUFFIXES: set[str]`
  - `BROWSER_NATIVE_SUFFIXES: set[str]`
  - `AudioDecodeError(Exception)`
  - `decode(path: Path, sample_rate: int = ANALYSIS_SR) -> np.ndarray` — mono, `float32`, 1-D
  - `probe_duration(path: Path) -> float` — segundos
  - `needs_transcode(path: Path) -> bool`

- [ ] **Step 1: Instalar o ffmpeg**

```bash
brew install ffmpeg
```

Confirmar com `ffmpeg -version`. Sem isso, nada nesta task funciona.

- [ ] **Step 2: Escrever os testes que falham**

`tests/test_audio_io.py`:

```python
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from trackclassifier.audio_io import (
    ANALYSIS_SR,
    AudioDecodeError,
    decode,
    needs_transcode,
    probe_duration,
)


@pytest.fixture
def wav_estereo(tmp_path) -> Path:
    sr = 44100
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
    tom = 0.5 * np.sin(2 * np.pi * 440 * t)
    estereo = np.stack([tom, tom], axis=1)
    caminho = tmp_path / "tom.wav"
    sf.write(caminho, estereo, sr)
    return caminho


def test_decodifica_para_mono_float32_na_taxa_de_analise(wav_estereo):
    y = decode(wav_estereo)

    assert y.ndim == 1
    assert y.dtype == np.float32
    assert abs(len(y) - ANALYSIS_SR * 2) < ANALYSIS_SR * 0.05


def test_respeita_taxa_de_amostragem_solicitada(wav_estereo):
    y = decode(wav_estereo, sample_rate=8000)

    assert abs(len(y) - 8000 * 2) < 8000 * 0.05


def test_mede_duracao(wav_estereo):
    assert probe_duration(wav_estereo) == pytest.approx(2.0, abs=0.05)


def test_arquivo_corrompido_levanta_erro(tmp_path):
    ruim = tmp_path / "quebrado.mp3"
    ruim.write_bytes(b"isto nao e audio")

    with pytest.raises(AudioDecodeError):
        decode(ruim)


def test_arquivo_inexistente_levanta_erro(tmp_path):
    with pytest.raises(AudioDecodeError):
        decode(tmp_path / "sumiu.wav")


def test_identifica_formatos_que_precisam_de_transcodificacao():
    assert needs_transcode(Path("a.flac")) is True
    assert needs_transcode(Path("a.aiff")) is True
    assert needs_transcode(Path("a.AIF")) is True
    assert needs_transcode(Path("a.mp3")) is False
    assert needs_transcode(Path("a.wav")) is False
```

- [ ] **Step 3: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_audio_io.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.audio_io'`.

- [ ] **Step 4: Implementar `audio_io.py`**

```python
import shutil
import subprocess
from pathlib import Path

import numpy as np

ANALYSIS_SR = 22050

SUPPORTED_SUFFIXES = {".mp3", ".wav", ".aiff", ".aif", ".flac", ".m4a", ".ogg"}
BROWSER_NATIVE_SUFFIXES = {".mp3", ".wav", ".m4a", ".ogg"}


class AudioDecodeError(Exception):
    pass


def _require_ffmpeg(binary: str) -> str:
    caminho = shutil.which(binary)
    if caminho is None:
        raise AudioDecodeError(
            f"{binary} nao encontrado no PATH. Instale com: brew install ffmpeg"
        )
    return caminho


def decode(path: Path, sample_rate: int = ANALYSIS_SR) -> np.ndarray:
    path = Path(path)
    if not path.is_file():
        raise AudioDecodeError(f"Arquivo nao encontrado: {path}")

    comando = [
        _require_ffmpeg("ffmpeg"),
        "-v", "error",
        "-i", str(path),
        "-f", "f32le",
        "-acodec", "pcm_f32le",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-",
    ]
    proc = subprocess.run(comando, capture_output=True)
    if proc.returncode != 0:
        detalhe = proc.stderr.decode("utf-8", errors="replace").strip()
        raise AudioDecodeError(f"Falha ao decodificar {path.name}: {detalhe}")

    y = np.frombuffer(proc.stdout, dtype=np.float32)
    if y.size == 0:
        raise AudioDecodeError(f"Arquivo sem audio decodificavel: {path.name}")
    return np.ascontiguousarray(y)


def probe_duration(path: Path) -> float:
    path = Path(path)
    if not path.is_file():
        raise AudioDecodeError(f"Arquivo nao encontrado: {path}")

    comando = [
        _require_ffmpeg("ffprobe"),
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    proc = subprocess.run(comando, capture_output=True)
    if proc.returncode != 0:
        raise AudioDecodeError(f"Falha ao medir duracao de {path.name}")
    try:
        return float(proc.stdout.decode().strip())
    except ValueError as exc:
        raise AudioDecodeError(f"Duracao invalida para {path.name}") from exc


def needs_transcode(path: Path) -> bool:
    return Path(path).suffix.lower() not in BROWSER_NATIVE_SUFFIXES
```

- [ ] **Step 5: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_audio_io.py -v
```

Esperado: 6 testes PASS.

- [ ] **Step 6: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): decodificacao de audio via ffmpeg"
```

---

### Task 3: Descritores de janela

**Files:**
- Create: `src/trackclassifier/descriptors.py`
- Test: `tests/test_descriptors.py`

**Interfaces:**
- Consumes: nada
- Produces:
  - `DESCRIPTOR_NAMES: list[str]` — 10 nomes, nesta ordem exata: `rms`, `onset_rate`, `spectral_flux`, `spectral_centroid`, `percussive_ratio`, `low_band_ratio`, `high_band_ratio`, `spectral_rolloff`, `spectral_bandwidth`, `zero_crossing_rate`
  - `describe_window(y: np.ndarray, sr: int) -> dict[str, float]` — chaves iguais a `DESCRIPTOR_NAMES`

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_descriptors.py`:

```python
import numpy as np
import pytest

from trackclassifier.audio_io import ANALYSIS_SR
from trackclassifier.descriptors import DESCRIPTOR_NAMES, describe_window

DURACAO = 4.0


def _tempo(sr=ANALYSIS_SR):
    return np.linspace(0, DURACAO, int(sr * DURACAO), endpoint=False)


def _seno(freq, sr=ANALYSIS_SR):
    return (0.5 * np.sin(2 * np.pi * freq * _tempo(sr))).astype(np.float32)


def _ruido_branco(sr=ANALYSIS_SR):
    gerador = np.random.default_rng(seed=42)
    return (0.5 * gerador.standard_normal(int(sr * DURACAO))).astype(np.float32)


def _silencio(sr=ANALYSIS_SR):
    return np.zeros(int(sr * DURACAO), dtype=np.float32)


def test_retorna_exatamente_os_descritores_esperados():
    resultado = describe_window(_seno(440), ANALYSIS_SR)

    assert list(resultado.keys()) == DESCRIPTOR_NAMES
    assert len(DESCRIPTOR_NAMES) == 10
    assert all(isinstance(v, float) for v in resultado.values())


def test_todos_os_valores_sao_finitos_mesmo_em_silencio():
    resultado = describe_window(_silencio(), ANALYSIS_SR)

    assert all(np.isfinite(v) for v in resultado.values())
    assert resultado["rms"] == pytest.approx(0.0, abs=1e-9)


def test_rms_cresce_com_amplitude():
    fraco = describe_window(_seno(440) * 0.1, ANALYSIS_SR)
    forte = describe_window(_seno(440), ANALYSIS_SR)

    assert forte["rms"] > fraco["rms"] * 5


def test_ruido_branco_e_mais_brilhante_que_seno_grave():
    grave = describe_window(_seno(100), ANALYSIS_SR)
    ruido = describe_window(_ruido_branco(), ANALYSIS_SR)

    assert ruido["spectral_centroid"] > grave["spectral_centroid"]
    assert ruido["high_band_ratio"] > grave["high_band_ratio"]
    assert ruido["zero_crossing_rate"] > grave["zero_crossing_rate"]


def test_seno_grave_concentra_energia_na_banda_baixa():
    grave = describe_window(_seno(100), ANALYSIS_SR)
    agudo = describe_window(_seno(6000), ANALYSIS_SR)

    assert grave["low_band_ratio"] > 0.5
    assert agudo["low_band_ratio"] < grave["low_band_ratio"]


def test_razoes_de_banda_ficam_entre_zero_e_um():
    resultado = describe_window(_ruido_branco(), ANALYSIS_SR)

    for chave in ("low_band_ratio", "high_band_ratio", "percussive_ratio"):
        assert 0.0 <= resultado[chave] <= 1.0
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_descriptors.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.descriptors'`.

- [ ] **Step 3: Implementar `descriptors.py`**

```python
import librosa
import numpy as np

DESCRIPTOR_NAMES: list[str] = [
    "rms",
    "onset_rate",
    "spectral_flux",
    "spectral_centroid",
    "percussive_ratio",
    "low_band_ratio",
    "high_band_ratio",
    "spectral_rolloff",
    "spectral_bandwidth",
    "zero_crossing_rate",
]

_N_FFT = 2048
_HOP = 512
_EPS = 1e-9
_LOW_BAND = (20.0, 250.0)
_HIGH_BAND_FLOOR = 4000.0


def describe_window(y: np.ndarray, sr: int) -> dict[str, float]:
    y = np.asarray(y, dtype=np.float32)
    duracao = max(len(y) / sr, _EPS)

    espectro = np.abs(librosa.stft(y, n_fft=_N_FFT, hop_length=_HOP))
    frequencias = librosa.fft_frequencies(sr=sr, n_fft=_N_FFT)
    energia_total = float(espectro.sum()) + _EPS

    mascara_grave = (frequencias >= _LOW_BAND[0]) & (frequencias < _LOW_BAND[1])
    mascara_aguda = frequencias >= _HIGH_BAND_FLOOR

    if espectro.shape[1] > 1:
        fluxo = float(np.mean(np.maximum(np.diff(espectro, axis=1), 0.0)))
    else:
        fluxo = 0.0

    harmonico, percussivo = librosa.decompose.hpss(espectro)
    soma_percussiva = float(percussivo.sum())
    soma_harmonica = float(harmonico.sum())

    onsets = librosa.onset.onset_detect(y=y, sr=sr, hop_length=_HOP, units="time")

    return {
        "rms": float(np.sqrt(np.mean(np.square(y, dtype=np.float64)))),
        "onset_rate": float(len(onsets) / duracao),
        "spectral_flux": fluxo,
        "spectral_centroid": float(
            np.mean(librosa.feature.spectral_centroid(S=espectro, sr=sr))
        ),
        "percussive_ratio": float(
            soma_percussiva / (soma_percussiva + soma_harmonica + _EPS)
        ),
        "low_band_ratio": float(espectro[mascara_grave].sum() / energia_total),
        "high_band_ratio": float(espectro[mascara_aguda].sum() / energia_total),
        "spectral_rolloff": float(
            np.mean(librosa.feature.spectral_rolloff(S=espectro, sr=sr))
        ),
        "spectral_bandwidth": float(
            np.mean(librosa.feature.spectral_bandwidth(S=espectro, sr=sr))
        ),
        "zero_crossing_rate": float(
            np.mean(librosa.feature.zero_crossing_rate(y, hop_length=_HOP))
        ),
    }
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_descriptors.py -v
```

Esperado: 6 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): descritores espectrais e ritmicos de janela"
```

---

### Task 4: Janelamento, agregação e extrator de features

**Files:**
- Create: `src/trackclassifier/features.py`
- Test: `tests/test_features.py`

**Interfaces:**
- Consumes: `decode`, `ANALYSIS_SR`, `AudioDecodeError` de `audio_io`; `DESCRIPTOR_NAMES`, `describe_window` de `descriptors`
- Produces:
  - `MAX_WINDOW_SECONDS: float = 10.0`
  - `MIN_TRACK_SECONDS: float = 10.0`
  - `STAT_SUFFIXES: list[str]` — `["median", "p90", "p10", "ratio"]`
  - `GLOBAL_NAMES: list[str]` — `["bpm", "lufs", "dynamic_range_db", "duration_s"]`
  - `FEATURE_NAMES: list[str]` — 44 nomes
  - `TrackTooShortError(Exception)`
  - `TrackAnalysis` (dataclass congelada): `vector: np.ndarray` (44,), `energy_curve: list[float]`, `peak_offset_s: float`, `bpm: float`, `duration_s: float`
  - `FeatureExtractor(Protocol)` com atributo `name: str` e método `extract(self, path: Path) -> TrackAnalysis`
  - `HandcraftedExtractor` com `name = "handcrafted-v1"`

**Nota de resolução de ambiguidade da spec:** a spec diz "janela de 10 s" e também "track mais curta que uma janela usa janela reduzida", o que se sobrepõe ao corte de 10 s. Resolução adotada: `window = min(10.0, duration / 3)` e `hop = window / 2`, garantindo pelo menos 5 janelas em qualquer track aceita; abaixo de `MIN_TRACK_SECONDS = 10.0` a track é rejeitada com `TrackTooShortError`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_features.py`:

```python
import numpy as np
import pytest
import soundfile as sf

from trackclassifier.audio_io import ANALYSIS_SR
from trackclassifier.features import (
    FEATURE_NAMES,
    HandcraftedExtractor,
    TrackAnalysis,
    TrackTooShortError,
)


def _escreve_wav(caminho, sinal, sr=ANALYSIS_SR):
    sf.write(caminho, sinal.astype(np.float32), sr)
    return caminho


def _clicks(bpm, duracao_s, sr=ANALYSIS_SR):
    import librosa

    tempos = np.arange(0, duracao_s, 60.0 / bpm)
    return librosa.clicks(times=tempos, sr=sr, length=int(sr * duracao_s))


def _track_com_pico(duracao_s=60.0, inicio_pico=30.0, sr=ANALYSIS_SR):
    gerador = np.random.default_rng(seed=7)
    sinal = 0.05 * gerador.standard_normal(int(sr * duracao_s))
    a = int(sr * inicio_pico)
    b = int(sr * (inicio_pico + 10.0))
    sinal[a:b] *= 12.0
    return sinal


def test_nomes_de_features_sao_44_e_unicos():
    assert len(FEATURE_NAMES) == 44
    assert len(set(FEATURE_NAMES)) == 44
    assert FEATURE_NAMES[0] == "rms_median"
    assert FEATURE_NAMES[-4:] == ["bpm", "lufs", "dynamic_range_db", "duration_s"]


def test_extrai_vetor_com_dimensao_correta(tmp_path):
    caminho = _escreve_wav(tmp_path / "t.wav", _track_com_pico())

    analise = HandcraftedExtractor().extract(caminho)

    assert isinstance(analise, TrackAnalysis)
    assert analise.vector.shape == (44,)
    assert np.all(np.isfinite(analise.vector))


def test_curva_de_energia_acompanha_as_janelas(tmp_path):
    caminho = _escreve_wav(tmp_path / "t.wav", _track_com_pico())

    analise = HandcraftedExtractor().extract(caminho)

    assert len(analise.energy_curve) >= 5
    assert all(np.isfinite(v) for v in analise.energy_curve)


def test_offset_do_pico_aponta_para_o_trecho_mais_energetico(tmp_path):
    caminho = _escreve_wav(tmp_path / "t.wav", _track_com_pico(inicio_pico=30.0))

    analise = HandcraftedExtractor().extract(caminho)

    assert 28.0 <= analise.peak_offset_s <= 40.0


def test_detecta_bpm_de_um_trem_de_cliques(tmp_path):
    caminho = _escreve_wav(tmp_path / "click.wav", _clicks(128, 30.0))

    analise = HandcraftedExtractor().extract(caminho)

    assert analise.bpm == pytest.approx(128, rel=0.05)


def test_reporta_duracao(tmp_path):
    caminho = _escreve_wav(tmp_path / "t.wav", _track_com_pico(duracao_s=45.0))

    analise = HandcraftedExtractor().extract(caminho)

    assert analise.duration_s == pytest.approx(45.0, abs=1.0)


def test_track_curta_demais_e_rejeitada(tmp_path):
    gerador = np.random.default_rng(seed=1)
    curta = 0.2 * gerador.standard_normal(int(ANALYSIS_SR * 6.0))
    caminho = _escreve_wav(tmp_path / "curta.wav", curta)

    with pytest.raises(TrackTooShortError):
        HandcraftedExtractor().extract(caminho)


def test_track_de_15_segundos_usa_janela_reduzida_e_funciona(tmp_path):
    gerador = np.random.default_rng(seed=2)
    curta = 0.2 * gerador.standard_normal(int(ANALYSIS_SR * 15.0))
    caminho = _escreve_wav(tmp_path / "media.wav", curta)

    analise = HandcraftedExtractor().extract(caminho)

    assert analise.vector.shape == (44,)
    assert len(analise.energy_curve) >= 5


def test_extrator_declara_nome_de_versao():
    assert HandcraftedExtractor().name == "handcrafted-v1"
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_features.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.features'`.

- [ ] **Step 3: Implementar `features.py`**

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import librosa
import numpy as np
import pyloudnorm

from .audio_io import ANALYSIS_SR, decode
from .descriptors import DESCRIPTOR_NAMES, describe_window

MAX_WINDOW_SECONDS = 10.0
MIN_TRACK_SECONDS = 10.0

STAT_SUFFIXES = ["median", "p90", "p10", "ratio"]
GLOBAL_NAMES = ["bpm", "lufs", "dynamic_range_db", "duration_s"]

FEATURE_NAMES: list[str] = [
    f"{descritor}_{sufixo}" for descritor in DESCRIPTOR_NAMES for sufixo in STAT_SUFFIXES
] + GLOBAL_NAMES

_EPS = 1e-9


class TrackTooShortError(Exception):
    pass


@dataclass(frozen=True)
class TrackAnalysis:
    vector: np.ndarray
    energy_curve: list[float]
    peak_offset_s: float
    bpm: float
    duration_s: float


class FeatureExtractor(Protocol):
    name: str

    def extract(self, path: Path) -> TrackAnalysis: ...


def _stats(valores: list[float]) -> list[float]:
    arr = np.asarray(valores, dtype=np.float64)
    mediana = float(np.median(arr))
    p90 = float(np.percentile(arr, 90))
    p10 = float(np.percentile(arr, 10))
    razao = float(p90 / (abs(mediana) + _EPS))
    return [mediana, p90, p10, razao]


def _window_plan(duracao: float) -> tuple[float, float]:
    janela = min(MAX_WINDOW_SECONDS, duracao / 3.0)
    return janela, janela / 2.0


class HandcraftedExtractor:
    name = "handcrafted-v1"

    def extract(self, path: Path) -> TrackAnalysis:
        y = decode(path, sample_rate=ANALYSIS_SR)
        duracao = len(y) / ANALYSIS_SR
        if duracao < MIN_TRACK_SECONDS:
            raise TrackTooShortError(
                f"Track de {duracao:.1f}s e curta demais (minimo {MIN_TRACK_SECONDS:.0f}s): "
                f"{Path(path).name}"
            )

        janela_s, salto_s = _window_plan(duracao)
        tamanho = int(janela_s * ANALYSIS_SR)
        salto = max(int(salto_s * ANALYSIS_SR), 1)

        por_descritor: dict[str, list[float]] = {nome: [] for nome in DESCRIPTOR_NAMES}
        curva_energia: list[float] = []
        offsets: list[float] = []

        for inicio in range(0, len(y) - tamanho + 1, salto):
            trecho = y[inicio : inicio + tamanho]
            medidas = describe_window(trecho, ANALYSIS_SR)
            for nome, valor in medidas.items():
                por_descritor[nome].append(valor)
            curva_energia.append(medidas["rms"])
            offsets.append(inicio / ANALYSIS_SR)

        vetor_janelas: list[float] = []
        for nome in DESCRIPTOR_NAMES:
            vetor_janelas.extend(_stats(por_descritor[nome]))

        energia = np.asarray(curva_energia, dtype=np.float64)
        faixa_db = 20.0 * np.log10(
            (float(np.percentile(energia, 95)) + _EPS) / (float(np.percentile(energia, 10)) + _EPS)
        )

        tempo = librosa.beat.beat_track(y=y, sr=ANALYSIS_SR)[0]
        bpm = float(np.atleast_1d(tempo)[0])

        medidor = pyloudnorm.Meter(ANALYSIS_SR)
        lufs = float(medidor.integrated_loudness(y.astype(np.float64)))
        if not np.isfinite(lufs):
            lufs = -70.0

        globais = [bpm, lufs, float(faixa_db), float(duracao)]
        vetor = np.asarray(vetor_janelas + globais, dtype=np.float64)

        return TrackAnalysis(
            vector=vetor,
            energy_curve=[float(v) for v in curva_energia],
            peak_offset_s=float(offsets[int(np.argmax(energia))]),
            bpm=bpm,
            duration_s=float(duracao),
        )
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_features.py -v
```

Esperado: 9 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): janelamento, agregacao estatistica e extrator de features"
```

---

### Task 5: Cache de análises

**Files:**
- Create: `src/trackclassifier/cache.py`
- Test: `tests/test_cache.py`

**Interfaces:**
- Consumes: `TrackAnalysis`, `FEATURE_NAMES` de `features`
- Produces:
  - `file_sha1(path: Path) -> str`
  - `AnalysisCache` com `__init__(self, path: Path)`, `get(self, sha1: str) -> TrackAnalysis | None`, `put(self, sha1: str, filename: str, extractor: str, analysis: TrackAnalysis) -> None`, `save(self) -> None`, `__len__(self) -> int`

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_cache.py`:

```python
import numpy as np

from trackclassifier.cache import AnalysisCache, file_sha1
from trackclassifier.features import TrackAnalysis


def _analise(valor=1.0):
    return TrackAnalysis(
        vector=np.full(44, valor, dtype=np.float64),
        energy_curve=[0.1, 0.4, 0.2],
        peak_offset_s=5.0,
        bpm=128.0,
        duration_s=300.0,
    )


def test_sha1_e_estavel_e_sensivel_ao_conteudo(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"conteudo")
    b.write_bytes(b"conteudo")

    assert file_sha1(a) == file_sha1(b)

    b.write_bytes(b"outro conteudo")
    assert file_sha1(a) != file_sha1(b)


def test_get_retorna_none_para_chave_ausente(tmp_path):
    cache = AnalysisCache(tmp_path / "cache.parquet")

    assert cache.get("inexistente") is None


def test_grava_e_le_analise(tmp_path):
    cache = AnalysisCache(tmp_path / "cache.parquet")
    cache.put("abc", "track.mp3", "handcrafted-v1", _analise(2.5))

    recuperada = cache.get("abc")

    assert recuperada is not None
    assert np.allclose(recuperada.vector, 2.5)
    assert recuperada.energy_curve == [0.1, 0.4, 0.2]
    assert recuperada.peak_offset_s == 5.0
    assert recuperada.bpm == 128.0
    assert recuperada.duration_s == 300.0


def test_persiste_entre_instancias(tmp_path):
    caminho = tmp_path / "cache.parquet"
    primeira = AnalysisCache(caminho)
    primeira.put("abc", "track.mp3", "handcrafted-v1", _analise(3.0))
    primeira.save()

    segunda = AnalysisCache(caminho)

    assert len(segunda) == 1
    assert np.allclose(segunda.get("abc").vector, 3.0)


def test_put_sobrescreve_a_mesma_chave(tmp_path):
    cache = AnalysisCache(tmp_path / "cache.parquet")
    cache.put("abc", "track.mp3", "handcrafted-v1", _analise(1.0))
    cache.put("abc", "track.mp3", "handcrafted-v1", _analise(9.0))

    assert len(cache) == 1
    assert np.allclose(cache.get("abc").vector, 9.0)
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_cache.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.cache'`.

- [ ] **Step 3: Implementar `cache.py`**

```python
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURE_NAMES, TrackAnalysis

_COLUNAS_META = ["sha1", "filename", "extractor", "energy_curve", "peak_offset_s", "bpm", "duration_s"]
_CHUNK = 1024 * 1024


def file_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with Path(path).open("rb") as handle:
        for bloco in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(bloco)
    return digest.hexdigest()


class AnalysisCache:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._linhas: dict[str, dict] = {}
        if self.path.is_file():
            frame = pd.read_parquet(self.path)
            for registro in frame.to_dict(orient="records"):
                self._linhas[registro["sha1"]] = registro

    def __len__(self) -> int:
        return len(self._linhas)

    def get(self, sha1: str) -> TrackAnalysis | None:
        registro = self._linhas.get(sha1)
        if registro is None:
            return None
        return TrackAnalysis(
            vector=np.asarray([registro[nome] for nome in FEATURE_NAMES], dtype=np.float64),
            energy_curve=json.loads(registro["energy_curve"]),
            peak_offset_s=float(registro["peak_offset_s"]),
            bpm=float(registro["bpm"]),
            duration_s=float(registro["duration_s"]),
        )

    def put(self, sha1: str, filename: str, extractor: str, analysis: TrackAnalysis) -> None:
        registro = {
            "sha1": sha1,
            "filename": filename,
            "extractor": extractor,
            "energy_curve": json.dumps(analysis.energy_curve),
            "peak_offset_s": float(analysis.peak_offset_s),
            "bpm": float(analysis.bpm),
            "duration_s": float(analysis.duration_s),
        }
        registro.update(
            {nome: float(valor) for nome, valor in zip(FEATURE_NAMES, analysis.vector)}
        )
        self._linhas[sha1] = registro

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        frame = pd.DataFrame(list(self._linhas.values()), columns=_COLUNAS_META + FEATURE_NAMES)
        frame.to_parquet(self.path, index=False)
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_cache.py -v
```

Esperado: 5 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): cache de analises em parquet indexado por sha1"
```

---

### Task 6: Varredura de biblioteca

**Files:**
- Create: `src/trackclassifier/library.py`
- Test: `tests/test_library.py`

**Interfaces:**
- Consumes: `Config` de `config`, `Label` de `labels`, `SUPPORTED_SUFFIXES` de `audio_io`, `file_sha1` de `cache`
- Produces:
  - `TrackRef` (dataclass congelada): `path: Path`, `label: Label | None`, `sha1: str`
  - `scan_labeled(config: Config) -> list[TrackRef]`
  - `scan_inbox(config: Config) -> list[TrackRef]`

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_library.py`:

```python
from pathlib import Path

from trackclassifier.config import Config
from trackclassifier.labels import Label
from trackclassifier.library import scan_inbox, scan_labeled


def _config(tmp_path) -> Config:
    pastas = {}
    for chave, rotulo in (("up", Label.UP), ("neutral", Label.NEUTRAL), ("down", Label.DOWN)):
        destino = tmp_path / chave
        destino.mkdir()
        pastas[rotulo] = destino
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    return Config(folders=pastas, inbox=inbox, data_dir=data, retrain_every=10, min_examples=15)


def _cria(caminho: Path, conteudo: bytes = b"audio"):
    caminho.write_bytes(conteudo)
    return caminho


def test_mapeia_pasta_para_rotulo(tmp_path):
    config = _config(tmp_path)
    _cria(config.folders[Label.UP] / "a.mp3", b"1")
    _cria(config.folders[Label.NEUTRAL] / "b.wav", b"2")
    _cria(config.folders[Label.DOWN] / "c.flac", b"3")

    refs = scan_labeled(config)

    por_nome = {ref.path.name: ref.label for ref in refs}
    assert por_nome == {"a.mp3": Label.UP, "b.wav": Label.NEUTRAL, "c.flac": Label.DOWN}


def test_ignora_arquivos_que_nao_sao_audio(tmp_path):
    config = _config(tmp_path)
    _cria(config.folders[Label.UP] / "a.mp3")
    _cria(config.folders[Label.UP] / "capa.jpg")
    _cria(config.folders[Label.UP] / ".DS_Store")

    refs = scan_labeled(config)

    assert [ref.path.name for ref in refs] == ["a.mp3"]


def test_varre_subpastas(tmp_path):
    config = _config(tmp_path)
    sub = config.folders[Label.UP] / "2026"
    sub.mkdir()
    _cria(sub / "a.mp3")

    refs = scan_labeled(config)

    assert len(refs) == 1
    assert refs[0].label == Label.UP


def test_inbox_vem_sem_rotulo_e_com_sha1(tmp_path):
    config = _config(tmp_path)
    _cria(config.inbox / "nova.mp3", b"conteudo")

    refs = scan_inbox(config)

    assert len(refs) == 1
    assert refs[0].label is None
    assert len(refs[0].sha1) == 40


def test_resultado_e_ordenado_de_forma_estavel(tmp_path):
    config = _config(tmp_path)
    for nome in ("c.mp3", "a.mp3", "b.mp3"):
        _cria(config.inbox / nome, nome.encode())

    nomes = [ref.path.name for ref in scan_inbox(config)]

    assert nomes == ["a.mp3", "b.mp3", "c.mp3"]
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_library.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.library'`.

- [ ] **Step 3: Implementar `library.py`**

```python
from dataclasses import dataclass
from pathlib import Path

from .audio_io import SUPPORTED_SUFFIXES
from .cache import file_sha1
from .config import Config
from .labels import Label


@dataclass(frozen=True)
class TrackRef:
    path: Path
    label: Label | None
    sha1: str


def _arquivos_de_audio(raiz: Path) -> list[Path]:
    encontrados = [
        caminho
        for caminho in raiz.rglob("*")
        if caminho.is_file()
        and not caminho.name.startswith(".")
        and caminho.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(encontrados, key=lambda caminho: str(caminho).lower())


def scan_labeled(config: Config) -> list[TrackRef]:
    refs: list[TrackRef] = []
    for rotulo, pasta in config.folders.items():
        for caminho in _arquivos_de_audio(pasta):
            refs.append(TrackRef(path=caminho, label=rotulo, sha1=file_sha1(caminho)))
    return sorted(refs, key=lambda ref: str(ref.path).lower())


def scan_inbox(config: Config) -> list[TrackRef]:
    return [
        TrackRef(path=caminho, label=None, sha1=file_sha1(caminho))
        for caminho in _arquivos_de_audio(config.inbox)
    ]
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_library.py -v
```

Esperado: 5 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): varredura das pastas rotuladas e da inbox"
```

---

### Task 7: Núcleo do modelo — Ridge e escore

**Files:**
- Create: `src/trackclassifier/model.py`
- Test: `tests/test_model_core.py`

**Interfaces:**
- Consumes: `Label`, `LABEL_TARGET` de `labels`
- Produces:
  - `NotEnoughClassesError(Exception)`
  - `NotFittedError(Exception)`
  - `TrackModel` com `fit(self, X: np.ndarray, labels: list[Label]) -> None`, `score(self, X: np.ndarray) -> np.ndarray`, `save(self, path: Path) -> None`, `load(cls, path: Path) -> TrackModel`, atributos `alpha_: float`, `n_examples_: int`, `is_fitted: bool`

**Nota:** a calibração de limiares, a confiança e as métricas entram na Task 8, no mesmo arquivo.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_model_core.py`:

```python
import numpy as np
import pytest

from trackclassifier.labels import Label
from trackclassifier.model import NotEnoughClassesError, NotFittedError, TrackModel


def dataset_sintetico(n_por_classe=25, ruido=0.15, seed=3):
    """Feature 0 codifica energia; as outras 43 sao ruido puro."""
    gerador = np.random.default_rng(seed)
    linhas, rotulos = [], []
    for rotulo, centro in ((Label.DOWN, 0.0), (Label.NEUTRAL, 0.5), (Label.UP, 1.0)):
        for _ in range(n_por_classe):
            vetor = gerador.standard_normal(44)
            vetor[0] = centro + gerador.normal(0.0, ruido)
            linhas.append(vetor)
            rotulos.append(rotulo)
    return np.asarray(linhas), rotulos


def test_treina_e_produz_escores_ordenados_por_classe():
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)

    escores = modelo.score(X)
    media = {
        rotulo: float(np.mean([e for e, r in zip(escores, y) if r == rotulo]))
        for rotulo in (Label.DOWN, Label.NEUTRAL, Label.UP)
    }

    assert media[Label.DOWN] < media[Label.NEUTRAL] < media[Label.UP]


def test_escore_fica_no_intervalo_fechado():
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)

    escores = modelo.score(X)

    assert escores.min() >= 0.0
    assert escores.max() <= 1.0


def test_recusa_treinar_sem_as_tres_classes():
    X, y = dataset_sintetico()
    sem_up = [(vetor, rotulo) for vetor, rotulo in zip(X, y) if rotulo != Label.UP]
    Xs = np.asarray([v for v, _ in sem_up])
    ys = [r for _, r in sem_up]

    with pytest.raises(NotEnoughClassesError) as exc:
        TrackModel().fit(Xs, ys)

    assert "+1" in str(exc.value)


def test_score_antes_de_treinar_levanta_erro():
    with pytest.raises(NotFittedError):
        TrackModel().score(np.zeros((1, 44)))


def test_registra_alpha_escolhido_e_tamanho_do_dataset():
    X, y = dataset_sintetico(n_por_classe=10)
    modelo = TrackModel()
    modelo.fit(X, y)

    assert modelo.alpha_ > 0
    assert modelo.n_examples_ == 30
    assert modelo.is_fitted is True


def test_persiste_e_recarrega_produzindo_os_mesmos_escores(tmp_path):
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)
    esperado = modelo.score(X)

    destino = tmp_path / "modelo.joblib"
    modelo.save(destino)
    recarregado = TrackModel.load(destino)

    assert np.allclose(recarregado.score(X), esperado)
    assert recarregado.n_examples_ == modelo.n_examples_
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_model_core.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.model'`.

- [ ] **Step 3: Implementar o núcleo de `model.py`**

```python
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

from .labels import LABEL_ORDER, LABEL_TARGET, Label

ALPHAS = np.logspace(-3, 3, 13)


class NotEnoughClassesError(Exception):
    pass


class NotFittedError(Exception):
    pass


class TrackModel:
    def __init__(self) -> None:
        self._scaler: StandardScaler | None = None
        self._ridge: RidgeCV | None = None
        self.alpha_: float = 0.0
        self.n_examples_: int = 0

    @property
    def is_fitted(self) -> bool:
        return self._ridge is not None

    def fit(self, X: np.ndarray, labels: list[Label]) -> None:
        presentes = set(labels)
        faltando = [rotulo.value for rotulo in LABEL_ORDER if rotulo not in presentes]
        if faltando:
            raise NotEnoughClassesError(
                "Nao da para treinar sem exemplos de todas as classes. "
                f"Faltam rotulos: {', '.join(faltando)}"
            )

        X = np.asarray(X, dtype=np.float64)
        y = np.asarray([LABEL_TARGET[rotulo] for rotulo in labels], dtype=np.float64)

        self._scaler = StandardScaler().fit(X)
        self._ridge = RidgeCV(alphas=ALPHAS).fit(self._scaler.transform(X), y)
        self.alpha_ = float(self._ridge.alpha_)
        self.n_examples_ = int(len(labels))

    def score(self, X: np.ndarray) -> np.ndarray:
        if self._ridge is None or self._scaler is None:
            raise NotFittedError("Modelo ainda nao treinado. Rode: dj train")
        bruto = self._ridge.predict(self._scaler.transform(np.asarray(X, dtype=np.float64)))
        return np.clip(bruto, 0.0, 1.0)

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, Path(path))

    @classmethod
    def load(cls, path: Path) -> "TrackModel":
        return joblib.load(Path(path))
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_model_core.py -v
```

Esperado: 6 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): regressao Ridge com escore ordinal continuo"
```

---

### Task 8: Calibração de limiares, confiança e métricas

**Files:**
- Modify: `src/trackclassifier/model.py`
- Test: `tests/test_model_calibration.py`

**Interfaces:**
- Consumes: `TrackModel` da Task 7
- Produces (adições ao `TrackModel`):
  - `Metrics` (dataclass congelada): `accuracy: float`, `ordinal_mae: float`, `confusion: list[list[int]]`, `n_examples: int`
  - `Prediction` (dataclass congelada): `label: Label`, `score: float`, `confidence: float`
  - Atributos `thresholds_: tuple[float, float]`, `metrics_: Metrics | None`, `low_confidence_mode: bool`
  - `predict(self, X: np.ndarray) -> list[Prediction]`
  - `fit` passa a aceitar `min_examples: int = 15` e a preencher `thresholds_`, `metrics_` e `low_confidence_mode`

**Como funciona a calibração:** `fit` gera escores fora-de-amostra por leave-one-out (`cross_val_predict`), evitando viés otimista. Os candidatos a limiar são os pontos médios entre escores fora-de-amostra consecutivos e ordenados. Uma busca em grade sobre todos os pares `(t1, t2)` com `t1 < t2` escolhe o par de maior acurácia; empates são desempatados pelo menor erro ordinal médio.

**Confiança:** `margem = max((t2 - t1) / 2, 0.05)`; `confianca = min(1.0, distancia_ao_limiar_mais_proximo / margem)`. Quando `n_examples < min_examples`, `low_confidence_mode` fica `True` e toda confiança é multiplicada por `0.5`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_model_calibration.py`:

```python
import numpy as np
import pytest

from trackclassifier.labels import Label
from trackclassifier.model import Metrics, Prediction, TrackModel
from tests.test_model_core import dataset_sintetico


def test_limiares_ficam_ordenados_e_dentro_do_intervalo():
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)

    t1, t2 = modelo.thresholds_

    assert 0.0 < t1 < t2 < 1.0


def test_predicao_recupera_os_rotulos_de_um_dataset_separavel():
    X, y = dataset_sintetico(n_por_classe=25, ruido=0.08)
    modelo = TrackModel()
    modelo.fit(X, y)

    previstos = [predicao.label for predicao in modelo.predict(X)]
    acertos = sum(1 for p, real in zip(previstos, y) if p == real)

    assert acertos / len(y) > 0.85


def test_predicao_retorna_estrutura_completa():
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)

    predicao = modelo.predict(X[:1])[0]

    assert isinstance(predicao, Prediction)
    assert predicao.label in (Label.DOWN, Label.NEUTRAL, Label.UP)
    assert 0.0 <= predicao.score <= 1.0
    assert 0.0 <= predicao.confidence <= 1.0


def test_confianca_cai_perto_do_limiar():
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)
    t1, _ = modelo.thresholds_

    escores = modelo.score(X)
    indice_proximo = int(np.argmin(np.abs(escores - t1)))
    indice_extremo = int(np.argmax(escores))

    predicoes = modelo.predict(X)

    assert predicoes[indice_proximo].confidence < predicoes[indice_extremo].confidence


def test_metricas_sao_reportadas():
    X, y = dataset_sintetico(n_por_classe=25, ruido=0.08)
    modelo = TrackModel()
    modelo.fit(X, y)

    metricas = modelo.metrics_

    assert isinstance(metricas, Metrics)
    assert 0.0 <= metricas.accuracy <= 1.0
    assert metricas.accuracy > 0.8
    assert metricas.ordinal_mae >= 0.0
    assert np.asarray(metricas.confusion).shape == (3, 3)
    assert sum(sum(linha) for linha in metricas.confusion) == metricas.n_examples
    assert metricas.n_examples == 75


def test_erro_ordinal_penaliza_confusao_entre_extremos():
    X, y = dataset_sintetico(n_por_classe=25, ruido=0.08)
    modelo = TrackModel()
    modelo.fit(X, y)

    assert modelo.metrics_.ordinal_mae < 0.5


def test_modo_de_baixa_confianca_com_poucos_exemplos():
    X, y = dataset_sintetico(n_por_classe=3)
    modelo = TrackModel()
    modelo.fit(X, y, min_examples=15)

    assert modelo.low_confidence_mode is True
    assert max(p.confidence for p in modelo.predict(X)) <= 0.5


def test_dataset_grande_nao_entra_em_baixa_confianca():
    X, y = dataset_sintetico(n_por_classe=25)
    modelo = TrackModel()
    modelo.fit(X, y, min_examples=15)

    assert modelo.low_confidence_mode is False


def test_calibracao_sobrevive_ao_ciclo_de_persistencia(tmp_path):
    X, y = dataset_sintetico()
    modelo = TrackModel()
    modelo.fit(X, y)
    destino = tmp_path / "modelo.joblib"
    modelo.save(destino)

    recarregado = TrackModel.load(destino)

    assert recarregado.thresholds_ == modelo.thresholds_
    assert recarregado.metrics_.accuracy == pytest.approx(modelo.metrics_.accuracy)
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_model_calibration.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'Metrics' from 'trackclassifier.model'`.

- [ ] **Step 3: Estender `model.py`**

Acrescentar os imports no topo do arquivo:

```python
from dataclasses import dataclass

from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
```

Acrescentar as dataclasses logo depois de `ALPHAS`:

```python
@dataclass(frozen=True)
class Metrics:
    accuracy: float
    ordinal_mae: float
    confusion: list[list[int]]
    n_examples: int


@dataclass(frozen=True)
class Prediction:
    label: Label
    score: float
    confidence: float


MIN_MARGIN = 0.05


def _labels_from_scores(scores: np.ndarray, t1: float, t2: float) -> list[Label]:
    return [
        Label.DOWN if s < t1 else (Label.NEUTRAL if s < t2 else Label.UP) for s in scores
    ]


def _threshold_candidates(scores: np.ndarray) -> list[float]:
    ordenados = np.unique(np.round(scores, 6))
    if len(ordenados) < 2:
        return [0.33, 0.66]
    return [float((a + b) / 2.0) for a, b in zip(ordenados[:-1], ordenados[1:])]


def _evaluate(previstos: list[Label], reais: list[Label]) -> tuple[float, float, list[list[int]]]:
    indice = {rotulo: posicao for posicao, rotulo in enumerate(LABEL_ORDER)}
    confusao = [[0, 0, 0] for _ in range(3)]
    acertos = 0
    erro_ordinal = 0.0
    for previsto, real in zip(previstos, reais):
        confusao[indice[real]][indice[previsto]] += 1
        acertos += int(previsto == real)
        erro_ordinal += abs(indice[previsto] - indice[real])
    total = max(len(reais), 1)
    return acertos / total, erro_ordinal / total, confusao
```

Substituir o corpo de `__init__` e de `fit`, e acrescentar `predict`:

```python
    def __init__(self) -> None:
        self._scaler: StandardScaler | None = None
        self._ridge: RidgeCV | None = None
        self.alpha_: float = 0.0
        self.n_examples_: int = 0
        self.thresholds_: tuple[float, float] = (0.33, 0.66)
        self.metrics_: Metrics | None = None
        self.low_confidence_mode: bool = True

    def fit(self, X: np.ndarray, labels: list[Label], min_examples: int = 15) -> None:
        presentes = set(labels)
        faltando = [rotulo.value for rotulo in LABEL_ORDER if rotulo not in presentes]
        if faltando:
            raise NotEnoughClassesError(
                "Nao da para treinar sem exemplos de todas as classes. "
                f"Faltam rotulos: {', '.join(faltando)}"
            )

        X = np.asarray(X, dtype=np.float64)
        y = np.asarray([LABEL_TARGET[rotulo] for rotulo in labels], dtype=np.float64)

        self._scaler = StandardScaler().fit(X)
        self._ridge = RidgeCV(alphas=ALPHAS).fit(self._scaler.transform(X), y)
        self.alpha_ = float(self._ridge.alpha_)
        self.n_examples_ = int(len(labels))
        self.low_confidence_mode = self.n_examples_ < min_examples

        fora_de_amostra = np.clip(
            cross_val_predict(
                make_pipeline(StandardScaler(), Ridge(alpha=self.alpha_)),
                X,
                y,
                cv=LeaveOneOut(),
            ),
            0.0,
            1.0,
        )
        self.thresholds_ = self._calibrate(fora_de_amostra, labels)

        t1, t2 = self.thresholds_
        acuracia, erro_ordinal, confusao = _evaluate(
            _labels_from_scores(fora_de_amostra, t1, t2), labels
        )
        self.metrics_ = Metrics(
            accuracy=acuracia,
            ordinal_mae=erro_ordinal,
            confusion=confusao,
            n_examples=self.n_examples_,
        )

    @staticmethod
    def _calibrate(scores: np.ndarray, labels: list[Label]) -> tuple[float, float]:
        candidatos = _threshold_candidates(scores)
        melhor = (0.33, 0.66)
        melhor_acuracia = -1.0
        melhor_erro = float("inf")
        for i, t1 in enumerate(candidatos):
            for t2 in candidatos[i + 1 :]:
                acuracia, erro_ordinal, _ = _evaluate(
                    _labels_from_scores(scores, t1, t2), labels
                )
                if acuracia > melhor_acuracia or (
                    acuracia == melhor_acuracia and erro_ordinal < melhor_erro
                ):
                    melhor, melhor_acuracia, melhor_erro = (t1, t2), acuracia, erro_ordinal
        return melhor

    def predict(self, X: np.ndarray) -> list[Prediction]:
        escores = self.score(X)
        t1, t2 = self.thresholds_
        margem = max((t2 - t1) / 2.0, MIN_MARGIN)
        fator = 0.5 if self.low_confidence_mode else 1.0

        predicoes: list[Prediction] = []
        for escore, rotulo in zip(escores, _labels_from_scores(escores, t1, t2)):
            distancia = min(abs(escore - t1), abs(escore - t2))
            confianca = min(1.0, distancia / margem) * fator
            predicoes.append(
                Prediction(label=rotulo, score=float(escore), confidence=float(confianca))
            )
        return predicoes
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_model_calibration.py tests/test_model_core.py -v
```

Esperado: 15 testes PASS (6 da Task 7 continuam verdes).

- [ ] **Step 5: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): calibracao de limiares, confianca e metricas leave-one-out"
```

---

### Task 9: Movimentação de arquivos

**Files:**
- Create: `src/trackclassifier/apply.py`
- Test: `tests/test_apply.py`

**Interfaces:**
- Consumes: nada
- Produces:
  - `FileVanishedError(Exception)`
  - `move_to_folder(src: Path, dest_dir: Path) -> Path` — devolve o caminho final

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_apply.py`:

```python
import hashlib

import pytest

from trackclassifier.apply import FileVanishedError, move_to_folder


def _hash(caminho):
    return hashlib.sha1(caminho.read_bytes()).hexdigest()


def test_move_arquivo_para_a_pasta_destino(tmp_path):
    origem = tmp_path / "in" / "track.mp3"
    origem.parent.mkdir()
    origem.write_bytes(b"conteudo de audio")
    destino_dir = tmp_path / "out"
    destino_dir.mkdir()

    final = move_to_folder(origem, destino_dir)

    assert final == destino_dir / "track.mp3"
    assert final.is_file()
    assert not origem.exists()


def test_conteudo_e_preservado_byte_a_byte(tmp_path):
    origem = tmp_path / "in" / "track.mp3"
    origem.parent.mkdir()
    origem.write_bytes(bytes(range(256)) * 100)
    esperado = _hash(origem)
    destino_dir = tmp_path / "out"
    destino_dir.mkdir()

    final = move_to_folder(origem, destino_dir)

    assert _hash(final) == esperado


def test_colisao_de_nome_gera_sufixo_sem_sobrescrever(tmp_path):
    destino_dir = tmp_path / "out"
    destino_dir.mkdir()
    existente = destino_dir / "track.mp3"
    existente.write_bytes(b"original")

    origem = tmp_path / "in" / "track.mp3"
    origem.parent.mkdir()
    origem.write_bytes(b"novo")

    final = move_to_folder(origem, destino_dir)

    assert final.name == "track (1).mp3"
    assert existente.read_bytes() == b"original"
    assert final.read_bytes() == b"novo"


def test_colisao_repetida_incrementa_o_sufixo(tmp_path):
    destino_dir = tmp_path / "out"
    destino_dir.mkdir()
    (destino_dir / "track.mp3").write_bytes(b"a")
    (destino_dir / "track (1).mp3").write_bytes(b"b")

    origem = tmp_path / "in" / "track.mp3"
    origem.parent.mkdir()
    origem.write_bytes(b"c")

    final = move_to_folder(origem, destino_dir)

    assert final.name == "track (2).mp3"


def test_arquivo_ausente_levanta_erro_especifico(tmp_path):
    destino_dir = tmp_path / "out"
    destino_dir.mkdir()

    with pytest.raises(FileVanishedError):
        move_to_folder(tmp_path / "sumiu.mp3", destino_dir)


def test_cria_pasta_destino_se_necessario(tmp_path):
    origem = tmp_path / "in" / "track.mp3"
    origem.parent.mkdir()
    origem.write_bytes(b"x")
    destino_dir = tmp_path / "out" / "nova"

    final = move_to_folder(origem, destino_dir)

    assert final.is_file()
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_apply.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.apply'`.

- [ ] **Step 3: Implementar `apply.py`**

```python
import shutil
from pathlib import Path


class FileVanishedError(Exception):
    pass


def _destino_livre(dest_dir: Path, nome: str) -> Path:
    candidato = dest_dir / nome
    if not candidato.exists():
        return candidato

    base = Path(nome).stem
    sufixo = Path(nome).suffix
    contador = 1
    while True:
        candidato = dest_dir / f"{base} ({contador}){sufixo}"
        if not candidato.exists():
            return candidato
        contador += 1


def move_to_folder(src: Path, dest_dir: Path) -> Path:
    src = Path(src)
    if not src.is_file():
        raise FileVanishedError(f"Arquivo nao existe mais: {src}")

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    destino = _destino_livre(dest_dir, src.name)
    shutil.move(str(src), str(destino))
    return destino
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_apply.py -v
```

Esperado: 6 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): movimentacao de arquivos preservando bytes e sem sobrescrever"
```

---

### Task 10: Serviço de orquestração

**Files:**
- Create: `src/trackclassifier/service.py`
- Test: `tests/test_service.py`

**Interfaces:**
- Consumes: `Config`, `Label`, `AnalysisCache`, `file_sha1`, `scan_labeled`, `scan_inbox`, `TrackRef`, `HandcraftedExtractor`, `TrackAnalysis`, `TrackTooShortError`, `AudioDecodeError`, `TrackModel`, `NotEnoughClassesError`, `move_to_folder`
- Produces:
  - `QueueItem` (dataclass congelada): `sha1: str`, `filename: str`, `path: Path`, `label: Label`, `score: float`, `confidence: float`, `bpm: float`, `duration_s: float`, `energy_curve: list[float]`, `peak_offset_s: float`
  - `FailedItem` (dataclass congelada): `filename: str`, `reason: str`
  - `TrackService` com:
    - `__init__(self, config: Config, extractor: FeatureExtractor | None = None)`
    - `analyze_all(self) -> None` — analisa rotuladas e inbox, popula cache e `failures`
    - `train(self) -> Metrics` — levanta `NotEnoughClassesError` se faltar classe
    - `queue(self) -> list[QueueItem]` — ordenada por confiança crescente
    - `failures(self) -> list[FailedItem]`
    - `decide(self, sha1: str, label: Label) -> bool` — move e devolve `True` se retreinou
    - `bulk_approve(self, min_confidence: float) -> int` — devolve quantas moveu
    - `path_for(self, sha1: str) -> Path`

**Política de retreino:** um contador interno soma cada decisão; ao atingir `config.retrain_every`, `train()` é chamado e o contador zera. `decide` devolve `True` exatamente nessas ocasiões.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_service.py`:

```python
import numpy as np
import pytest

from trackclassifier.config import Config
from trackclassifier.features import TrackAnalysis
from trackclassifier.labels import Label
from trackclassifier.service import FailedItem, QueueItem, TrackService


class ExtratorFalso:
    """Deriva o vetor do nome do arquivo, para tornar o teste deterministico."""

    name = "falso-v1"

    def __init__(self, falhar_em: set[str] | None = None):
        self.falhar_em = falhar_em or set()

    def extract(self, path):
        if path.name in self.falhar_em:
            raise ValueError(f"falha proposital em {path.name}")
        energia = float(path.stem.split("_")[-1])
        vetor = np.zeros(44, dtype=np.float64)
        vetor[0] = energia
        return TrackAnalysis(
            vector=vetor,
            energy_curve=[energia] * 6,
            peak_offset_s=12.0,
            bpm=128.0,
            duration_s=300.0,
        )


def _config(tmp_path) -> Config:
    pastas = {}
    for chave, rotulo in (("up", Label.UP), ("neutral", Label.NEUTRAL), ("down", Label.DOWN)):
        destino = tmp_path / chave
        destino.mkdir()
        pastas[rotulo] = destino
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    return Config(folders=pastas, inbox=inbox, data_dir=data, retrain_every=2, min_examples=1)


def _povoa(config, n_por_classe=6):
    for rotulo, energia in ((Label.DOWN, 0.0), (Label.NEUTRAL, 0.5), (Label.UP, 1.0)):
        for i in range(n_por_classe):
            valor = energia + i * 0.001
            caminho = config.folders[rotulo] / f"t{i}_{valor:.3f}.mp3"
            caminho.write_bytes(f"{rotulo.value}{i}".encode())


def _servico(config, falhar_em=None) -> TrackService:
    servico = TrackService(config, extractor=ExtratorFalso(falhar_em))
    servico.analyze_all()
    return servico


def test_treina_e_reporta_metricas(tmp_path):
    config = _config(tmp_path)
    _povoa(config)

    metricas = _servico(config).train()

    assert metricas.n_examples == 18
    assert metricas.accuracy > 0.8


def test_fila_traz_apenas_a_inbox_com_predicao(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.98.mp3").write_bytes(b"nova")

    servico = _servico(config)
    servico.train()
    fila = servico.queue()

    assert len(fila) == 1
    item = fila[0]
    assert isinstance(item, QueueItem)
    assert item.filename == "nova_0.98.mp3"
    assert item.label == Label.UP
    assert item.bpm == 128.0
    assert item.energy_curve == [0.98] * 6
    assert item.peak_offset_s == 12.0


def test_fila_ordena_por_confianca_crescente(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    for nome in ("clara_0.99.mp3", "duvidosa_0.34.mp3", "outra_0.02.mp3"):
        (config.inbox / nome).write_bytes(nome.encode())

    servico = _servico(config)
    servico.train()
    confiancas = [item.confidence for item in servico.queue()]

    assert confiancas == sorted(confiancas)


def test_falhas_de_analise_nao_derrubam_a_fila(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "boa_0.9.mp3").write_bytes(b"a")
    (config.inbox / "ruim_0.5.mp3").write_bytes(b"b")

    servico = TrackService(config, extractor=ExtratorFalso(falhar_em={"ruim_0.5.mp3"}))
    servico.analyze_all()
    servico.train()

    assert [item.filename for item in servico.queue()] == ["boa_0.9.mp3"]
    falhas = servico.failures()
    assert len(falhas) == 1
    assert isinstance(falhas[0], FailedItem)
    assert falhas[0].filename == "ruim_0.5.mp3"


def test_decide_move_o_arquivo_para_a_pasta_do_rotulo(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    origem = config.inbox / "nova_0.98.mp3"
    origem.write_bytes(b"nova")

    servico = _servico(config)
    servico.train()
    sha1 = servico.queue()[0].sha1
    servico.decide(sha1, Label.DOWN)

    assert not origem.exists()
    assert (config.folders[Label.DOWN] / "nova_0.98.mp3").is_file()
    assert servico.queue() == []


def test_retreina_ao_atingir_o_limite_de_decisoes(tmp_path):
    config = _config(tmp_path)  # retrain_every = 2
    _povoa(config)
    for nome in ("a_0.9.mp3", "b_0.1.mp3"):
        (config.inbox / nome).write_bytes(nome.encode())

    servico = _servico(config)
    servico.train()
    shas = [item.sha1 for item in servico.queue()]

    assert servico.decide(shas[0], Label.UP) is False
    assert servico.decide(shas[1], Label.DOWN) is True


def test_aprovacao_em_bloco_move_apenas_os_confiantes(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    for nome in ("clara_0.99.mp3", "duvidosa_0.34.mp3"):
        (config.inbox / nome).write_bytes(nome.encode())

    servico = _servico(config)
    servico.train()
    limiar = sorted(item.confidence for item in servico.queue())[-1]

    movidas = servico.bulk_approve(min_confidence=limiar)

    assert movidas == 1
    assert len(servico.queue()) == 1


def test_path_for_devolve_o_caminho_do_arquivo(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.9.mp3").write_bytes(b"nova")

    servico = _servico(config)
    servico.train()
    item = servico.queue()[0]

    assert servico.path_for(item.sha1) == config.inbox / "nova_0.9.mp3"


def test_arquivo_removido_por_fora_some_da_fila(tmp_path):
    config = _config(tmp_path)
    _povoa(config)
    alvo = config.inbox / "nova_0.9.mp3"
    alvo.write_bytes(b"nova")

    servico = _servico(config)
    servico.train()
    sha1 = servico.queue()[0].sha1
    alvo.unlink()

    assert servico.decide(sha1, Label.UP) is False
    assert servico.queue() == []
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_service.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.service'`.

- [ ] **Step 3: Implementar `service.py`**

```python
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .apply import FileVanishedError, move_to_folder
from .cache import AnalysisCache
from .config import Config
from .features import FeatureExtractor, HandcraftedExtractor, TrackAnalysis
from .labels import Label
from .library import TrackRef, scan_inbox, scan_labeled
from .model import Metrics, TrackModel


@dataclass(frozen=True)
class QueueItem:
    sha1: str
    filename: str
    path: Path
    label: Label
    score: float
    confidence: float
    bpm: float
    duration_s: float
    energy_curve: list[float]
    peak_offset_s: float


@dataclass(frozen=True)
class FailedItem:
    filename: str
    reason: str


class TrackService:
    def __init__(self, config: Config, extractor: FeatureExtractor | None = None):
        self.config = config
        self.extractor = extractor or HandcraftedExtractor()
        self.cache = AnalysisCache(config.data_dir / "analyses.parquet")
        self.model_path = config.data_dir / "model.joblib"
        self.model = TrackModel.load(self.model_path) if self.model_path.is_file() else TrackModel()
        self._labeled: list[TrackRef] = []
        self._inbox: list[TrackRef] = []
        self._failures: list[FailedItem] = []
        self._decisions_since_train = 0

    def analyze_all(self) -> None:
        self._failures = []
        self._labeled = self._analyze(scan_labeled(self.config))
        self._inbox = self._analyze(scan_inbox(self.config))
        self.cache.save()

    def _analyze(self, refs: list[TrackRef]) -> list[TrackRef]:
        aceitos: list[TrackRef] = []
        for ref in refs:
            if self.cache.get(ref.sha1) is not None:
                aceitos.append(ref)
                continue
            try:
                analise = self.extractor.extract(ref.path)
            except Exception as erro:
                self._failures.append(FailedItem(filename=ref.path.name, reason=str(erro)))
                continue
            self.cache.put(ref.sha1, ref.path.name, self.extractor.name, analise)
            aceitos.append(ref)
        return aceitos

    def _analysis(self, ref: TrackRef) -> TrackAnalysis:
        analise = self.cache.get(ref.sha1)
        assert analise is not None
        return analise

    def train(self) -> Metrics:
        matriz = np.asarray([self._analysis(ref).vector for ref in self._labeled])
        rotulos = [ref.label for ref in self._labeled if ref.label is not None]
        self.model.fit(matriz, rotulos, min_examples=self.config.min_examples)
        self.model.save(self.model_path)
        self._decisions_since_train = 0
        assert self.model.metrics_ is not None
        return self.model.metrics_

    def failures(self) -> list[FailedItem]:
        return list(self._failures)

    def queue(self) -> list[QueueItem]:
        vivos = [ref for ref in self._inbox if ref.path.is_file()]
        self._inbox = vivos
        if not vivos or not self.model.is_fitted:
            return []

        matriz = np.asarray([self._analysis(ref).vector for ref in vivos])
        predicoes = self.model.predict(matriz)

        itens = []
        for ref, predicao in zip(vivos, predicoes):
            analise = self._analysis(ref)
            itens.append(
                QueueItem(
                    sha1=ref.sha1,
                    filename=ref.path.name,
                    path=ref.path,
                    label=predicao.label,
                    score=predicao.score,
                    confidence=predicao.confidence,
                    bpm=analise.bpm,
                    duration_s=analise.duration_s,
                    energy_curve=analise.energy_curve,
                    peak_offset_s=analise.peak_offset_s,
                )
            )
        return sorted(itens, key=lambda item: item.confidence)

    def path_for(self, sha1: str) -> Path:
        for ref in self._inbox:
            if ref.sha1 == sha1:
                return ref.path
        raise KeyError(f"Track fora da fila: {sha1}")

    def decide(self, sha1: str, label: Label) -> bool:
        ref = next((r for r in self._inbox if r.sha1 == sha1), None)
        if ref is None:
            return False

        self._inbox = [r for r in self._inbox if r.sha1 != sha1]
        try:
            destino = move_to_folder(ref.path, self.config.folders[label])
        except FileVanishedError:
            return False

        self._labeled.append(TrackRef(path=destino, label=label, sha1=ref.sha1))
        self._decisions_since_train += 1
        if self._decisions_since_train >= self.config.retrain_every:
            self.train()
            return True
        return False

    def bulk_approve(self, min_confidence: float) -> int:
        alvos = [item for item in self.queue() if item.confidence >= min_confidence]
        for item in alvos:
            self.decide(item.sha1, item.label)
        return len(alvos)
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_service.py -v
```

Esperado: 9 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): orquestracao de analise, fila, decisao e retreino"
```

---

### Task 11: API HTTP da fila e das decisões

**Files:**
- Create: `src/trackclassifier/web.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `TrackService`, `QueueItem`, `FailedItem` de `service`; `Label` de `labels`
- Produces:
  - `create_app(service: TrackService) -> FastAPI`
  - `GET /api/queue` → `{"items": [...], "low_confidence_mode": bool, "metrics": {...} | null}`
  - `GET /api/failures` → `{"items": [{"filename": str, "reason": str}]}`
  - `POST /api/decide` corpo `{"sha1": str, "label": "+1" | "neutra" | "-1"}` → `{"retrained": bool}`; `404` se o sha1 não estiver na fila
  - `POST /api/bulk-approve` corpo `{"min_confidence": float}` → `{"moved": int}`
  - `GET /` → `index.html` estático

**Nota:** o endpoint de áudio entra na Task 12, no arquivo `streaming.py`, e é montado por `create_app`. Nesta task, `create_app` ainda não o inclui.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_web.py`:

```python
import pytest
from fastapi.testclient import TestClient

from trackclassifier.labels import Label
from trackclassifier.web import create_app
from tests.test_service import ExtratorFalso, _config, _povoa


@pytest.fixture
def cliente(tmp_path):
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    _povoa(config)
    for nome in ("clara_0.99.mp3", "duvidosa_0.34.mp3"):
        (config.inbox / nome).write_bytes(nome.encode())

    servico = TrackService(config, extractor=ExtratorFalso())
    servico.analyze_all()
    servico.train()
    return TestClient(create_app(servico)), servico


def test_fila_retorna_itens_ordenados_por_confianca(cliente):
    client, _ = cliente

    corpo = client.get("/api/queue").json()

    confiancas = [item["confidence"] for item in corpo["items"]]
    assert confiancas == sorted(confiancas)
    assert corpo["low_confidence_mode"] is False
    assert corpo["metrics"]["n_examples"] == 18


def test_item_da_fila_traz_os_campos_da_interface(cliente):
    client, _ = cliente

    item = client.get("/api/queue").json()["items"][0]

    for campo in (
        "sha1", "filename", "label", "score", "confidence",
        "bpm", "duration_s", "energy_curve", "peak_offset_s",
    ):
        assert campo in item
    assert item["label"] in ("+1", "neutra", "-1")


def test_decide_move_o_arquivo_e_tira_da_fila(cliente):
    client, servico = cliente
    sha1 = client.get("/api/queue").json()["items"][0]["sha1"]

    resposta = client.post("/api/decide", json={"sha1": sha1, "label": "-1"})

    assert resposta.status_code == 200
    assert resposta.json() == {"retrained": False}
    restantes = [item["sha1"] for item in client.get("/api/queue").json()["items"]]
    assert sha1 not in restantes
    assert (servico.config.folders[Label.DOWN] / "duvidosa_0.34.mp3").is_file()


def test_decide_com_sha1_desconhecido_retorna_404(cliente):
    client, _ = cliente

    resposta = client.post("/api/decide", json={"sha1": "naoexiste", "label": "+1"})

    assert resposta.status_code == 404


def test_decide_com_rotulo_invalido_retorna_422(cliente):
    client, _ = cliente
    sha1 = client.get("/api/queue").json()["items"][0]["sha1"]

    resposta = client.post("/api/decide", json={"sha1": sha1, "label": "talvez"})

    assert resposta.status_code == 422


def test_aprovacao_em_bloco_reporta_quantidade(cliente):
    client, _ = cliente
    confiancas = [item["confidence"] for item in client.get("/api/queue").json()["items"]]

    resposta = client.post("/api/bulk-approve", json={"min_confidence": max(confiancas)})

    assert resposta.json() == {"moved": 1}


def test_endpoint_de_falhas(tmp_path):
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "ruim_0.5.mp3").write_bytes(b"x")
    servico = TrackService(config, extractor=ExtratorFalso(falhar_em={"ruim_0.5.mp3"}))
    servico.analyze_all()
    servico.train()

    corpo = TestClient(create_app(servico)).get("/api/failures").json()

    assert corpo["items"][0]["filename"] == "ruim_0.5.mp3"
    assert "falha proposital" in corpo["items"][0]["reason"]


def test_raiz_serve_a_pagina(cliente):
    client, _ = cliente

    resposta = client.get("/")

    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
```

- [ ] **Step 2: Criar um `index.html` mínimo para o teste da raiz passar**

`src/trackclassifier/static/index.html` (substituído na Task 13):

```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <title>TrackClassifier</title>
  </head>
  <body>
    <p>Interface na Task 13.</p>
  </body>
</html>
```

- [ ] **Step 3: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_web.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.web'`.

- [ ] **Step 4: Implementar `web.py`**

```python
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .labels import Label
from .service import TrackService

STATIC_DIR = Path(__file__).parent / "static"


class DecideRequest(BaseModel):
    sha1: str
    label: Label


class BulkApproveRequest(BaseModel):
    min_confidence: float


def create_app(service: TrackService) -> FastAPI:
    app = FastAPI(title="TrackClassifier")

    @app.get("/api/queue")
    def fila() -> dict:
        metricas = service.model.metrics_
        return {
            "items": [
                {
                    "sha1": item.sha1,
                    "filename": item.filename,
                    "label": item.label.value,
                    "score": item.score,
                    "confidence": item.confidence,
                    "bpm": item.bpm,
                    "duration_s": item.duration_s,
                    "energy_curve": item.energy_curve,
                    "peak_offset_s": item.peak_offset_s,
                }
                for item in service.queue()
            ],
            "low_confidence_mode": service.model.low_confidence_mode,
            "metrics": None
            if metricas is None
            else {
                "accuracy": metricas.accuracy,
                "ordinal_mae": metricas.ordinal_mae,
                "confusion": metricas.confusion,
                "n_examples": metricas.n_examples,
            },
        }

    @app.get("/api/failures")
    def falhas() -> dict:
        return {
            "items": [
                {"filename": falha.filename, "reason": falha.reason}
                for falha in service.failures()
            ]
        }

    @app.post("/api/decide")
    def decidir(pedido: DecideRequest) -> dict:
        if all(item.sha1 != pedido.sha1 for item in service.queue()):
            raise HTTPException(status_code=404, detail="Track fora da fila")
        return {"retrained": service.decide(pedido.sha1, pedido.label)}

    @app.post("/api/bulk-approve")
    def aprovar_em_bloco(pedido: BulkApproveRequest) -> dict:
        return {"moved": service.bulk_approve(pedido.min_confidence)}

    @app.get("/")
    def raiz() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
```

- [ ] **Step 5: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_web.py -v
```

Esperado: 8 testes PASS.

- [ ] **Step 6: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): API HTTP da fila, decisoes e falhas"
```

---

### Task 12: Streaming de áudio com HTTP range

**Files:**
- Create: `src/trackclassifier/streaming.py`
- Modify: `src/trackclassifier/web.py` (registrar a rota)
- Test: `tests/test_streaming.py`

**Interfaces:**
- Consumes: `needs_transcode` de `audio_io`; `TrackService.path_for` de `service`
- Produces:
  - `ensure_playable(path: Path, cache_dir: Path) -> Path` — devolve o próprio arquivo se o navegador o reproduz, senão transcodifica para MP3 em `cache_dir` e devolve o MP3
  - `range_response(path: Path, range_header: str | None) -> Response` — `200` completo ou `206` parcial com `Content-Range` e `Accept-Ranges`
  - `register_audio_route(app: FastAPI, service: TrackService, cache_dir: Path) -> None` — registra `GET /api/audio/{sha1}`

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_streaming.py`:

```python
import pytest
from fastapi.testclient import TestClient

from trackclassifier.streaming import ensure_playable, range_response
from trackclassifier.web import create_app
from tests.test_service import ExtratorFalso, _config, _povoa


@pytest.fixture
def arquivo(tmp_path):
    caminho = tmp_path / "a.mp3"
    caminho.write_bytes(bytes(range(256)))
    return caminho


def test_resposta_completa_sem_cabecalho_range(arquivo):
    resposta = range_response(arquivo, None)

    assert resposta.status_code == 200
    assert resposta.headers["accept-ranges"] == "bytes"
    assert resposta.body == bytes(range(256))


def test_resposta_parcial_com_cabecalho_range(arquivo):
    resposta = range_response(arquivo, "bytes=10-19")

    assert resposta.status_code == 206
    assert resposta.headers["content-range"] == "bytes 10-19/256"
    assert resposta.headers["content-length"] == "10"
    assert resposta.body == bytes(range(10, 20))


def test_range_aberto_vai_ate_o_fim(arquivo):
    resposta = range_response(arquivo, "bytes=250-")

    assert resposta.status_code == 206
    assert resposta.headers["content-range"] == "bytes 250-255/256"


def test_range_alem_do_tamanho_e_truncado(arquivo):
    resposta = range_response(arquivo, "bytes=200-999")

    assert resposta.status_code == 206
    assert resposta.headers["content-range"] == "bytes 200-255/256"


def test_range_malformado_devolve_arquivo_completo(arquivo):
    resposta = range_response(arquivo, "coisas=abc")

    assert resposta.status_code == 200


def test_formato_nativo_nao_e_transcodificado(arquivo, tmp_path):
    assert ensure_playable(arquivo, tmp_path / "cache") == arquivo


def test_endpoint_de_audio_responde_com_o_conteudo(tmp_path):
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    _povoa(config)
    (config.inbox / "nova_0.9.mp3").write_bytes(b"conteudo de audio falso")
    servico = TrackService(config, extractor=ExtratorFalso())
    servico.analyze_all()
    servico.train()
    client = TestClient(create_app(servico))
    sha1 = client.get("/api/queue").json()["items"][0]["sha1"]

    resposta = client.get(f"/api/audio/{sha1}")

    assert resposta.status_code == 200
    assert resposta.content == b"conteudo de audio falso"


def test_endpoint_de_audio_com_sha1_desconhecido_retorna_404(tmp_path):
    from trackclassifier.service import TrackService

    config = _config(tmp_path)
    _povoa(config)
    servico = TrackService(config, extractor=ExtratorFalso())
    servico.analyze_all()
    servico.train()

    resposta = TestClient(create_app(servico)).get("/api/audio/naoexiste")

    assert resposta.status_code == 404
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_streaming.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.streaming'`.

- [ ] **Step 3: Implementar `streaming.py`**

```python
import mimetypes
import re
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from .audio_io import AudioDecodeError, needs_transcode
from .service import TrackService

_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


def ensure_playable(path: Path, cache_dir: Path) -> Path:
    path = Path(path)
    if not needs_transcode(path):
        return path

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    destino = cache_dir / f"{path.stem}.mp3"
    if destino.is_file():
        return destino

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioDecodeError("ffmpeg nao encontrado no PATH. Instale com: brew install ffmpeg")

    proc = subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-i", str(path), "-b:a", "192k", str(destino)],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise AudioDecodeError(f"Falha ao transcodificar {path.name}")
    return destino


def range_response(path: Path, range_header: str | None) -> Response:
    path = Path(path)
    dados = path.read_bytes()
    tamanho = len(dados)
    tipo = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    correspondencia = _RANGE.match(range_header or "")
    if correspondencia is None:
        return Response(
            content=dados,
            media_type=tipo,
            headers={"accept-ranges": "bytes", "content-length": str(tamanho)},
        )

    inicio_bruto, fim_bruto = correspondencia.groups()
    inicio = int(inicio_bruto) if inicio_bruto else 0
    fim = int(fim_bruto) if fim_bruto else tamanho - 1
    fim = min(fim, tamanho - 1)
    if inicio > fim:
        raise HTTPException(status_code=416, detail="Range invalido")

    trecho = dados[inicio : fim + 1]
    return Response(
        content=trecho,
        status_code=206,
        media_type=tipo,
        headers={
            "accept-ranges": "bytes",
            "content-range": f"bytes {inicio}-{fim}/{tamanho}",
            "content-length": str(len(trecho)),
        },
    )


def register_audio_route(app: FastAPI, service: TrackService, cache_dir: Path) -> None:
    @app.get("/api/audio/{sha1}")
    def audio(sha1: str, request: Request) -> Response:
        try:
            caminho = service.path_for(sha1)
        except KeyError:
            raise HTTPException(status_code=404, detail="Track fora da fila")
        if not caminho.is_file():
            raise HTTPException(status_code=404, detail="Arquivo nao existe mais")
        return range_response(
            ensure_playable(caminho, cache_dir), request.headers.get("range")
        )
```

- [ ] **Step 4: Registrar a rota em `web.py`**

Acrescentar o import no topo:

```python
from .streaming import register_audio_route
```

E, dentro de `create_app`, imediatamente antes do `app.mount("/static", ...)`:

```python
    register_audio_route(app, service, service.config.data_dir / "transcoded")
```

- [ ] **Step 5: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_streaming.py tests/test_web.py -v
```

Esperado: 16 testes PASS.

- [ ] **Step 6: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): streaming de audio com HTTP range e transcodificacao sob demanda"
```

---

### Task 13: Interface de revisão

**Files:**
- Modify: `src/trackclassifier/static/index.html`
- Create: `src/trackclassifier/static/app.js`
- Test: verificação manual (descrita no Step 4)

**Interfaces:**
- Consumes: `GET /api/queue`, `GET /api/failures`, `POST /api/decide`, `POST /api/bulk-approve`, `GET /api/audio/{sha1}`
- Produces: nada consumido por outras tasks

**Nota:** esta task não tem teste automatizado. A lógica testável já está coberta pelas Tasks 11 e 12; o que resta é apresentação, verificada manualmente. Não escrever testes de DOM aqui.

- [ ] **Step 1: Substituir `src/trackclassifier/static/index.html`**

```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>TrackClassifier</title>
    <style>
      :root { color-scheme: dark; }
      body {
        margin: 0; padding: 24px;
        font: 15px/1.5 -apple-system, system-ui, sans-serif;
        background: #14161a; color: #e8eaed;
      }
      h1 { font-size: 20px; margin: 0 0 4px; }
      .resumo { color: #9aa0a6; font-size: 13px; margin-bottom: 20px; }
      .aviso {
        background: #4a3a12; border: 1px solid #7a5f1e; color: #ffd479;
        padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; font-size: 13px;
      }
      .card {
        background: #1e2126; border: 1px solid #2c3036; border-radius: 8px;
        padding: 16px; margin-bottom: 12px;
      }
      .card.ativo { border-color: #5b8def; }
      .cabecalho { display: flex; justify-content: space-between; gap: 16px; align-items: baseline; }
      .nome { font-weight: 600; word-break: break-all; }
      .meta { color: #9aa0a6; font-size: 12px; white-space: nowrap; }
      .sugestao { display: flex; align-items: center; gap: 12px; margin: 12px 0; }
      .rotulo { font-size: 26px; font-weight: 700; min-width: 78px; }
      .rotulo[data-label="+1"] { color: #5ad17f; }
      .rotulo[data-label="neutra"] { color: #d1c25a; }
      .rotulo[data-label="-1"] { color: #d17a5a; }
      .barra { flex: 1; height: 6px; background: #2c3036; border-radius: 3px; overflow: hidden; }
      .barra > div { height: 100%; background: #5b8def; }
      .confianca { color: #9aa0a6; font-size: 12px; min-width: 108px; text-align: right; }
      svg.sparkline { width: 100%; height: 44px; display: block; margin: 10px 0; }
      audio { width: 100%; margin: 8px 0 12px; }
      .acoes { display: flex; gap: 8px; flex-wrap: wrap; }
      button {
        background: #2c3036; color: #e8eaed; border: 1px solid #3a4048;
        border-radius: 6px; padding: 8px 16px; font-size: 14px; cursor: pointer;
      }
      button:hover { background: #363b42; }
      button.primario { background: #2f5fbf; border-color: #3f6fcf; }
      .barra-topo { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
      .falhas { margin-top: 28px; }
      .falhas li { color: #d17a5a; font-size: 13px; }
      .vazio { color: #9aa0a6; padding: 32px 0; }
    </style>
  </head>
  <body>
    <h1>TrackClassifier</h1>
    <p class="resumo" id="resumo">Carregando...</p>
    <div id="aviso"></div>

    <div class="barra-topo">
      <button id="btn-bloco" class="primario">Aprovar todas com confianca alta</button>
      <span class="meta">Atalhos: 1 = -1 &nbsp; 2 = neutra &nbsp; 3 = +1 &nbsp; espaco = tocar</span>
    </div>

    <div id="fila"></div>

    <div class="falhas">
      <h2 style="font-size: 15px">Falharam</h2>
      <ul id="falhas"></ul>
    </div>

    <script src="/static/app.js"></script>
  </body>
</html>
```

- [ ] **Step 2: Criar `src/trackclassifier/static/app.js`**

```javascript
const LIMIAR_BLOCO = 0.75;
let itens = [];
let ativo = 0;

async function json(url, opcoes) {
  const resposta = await fetch(url, opcoes);
  if (!resposta.ok) throw new Error(`${url} respondeu ${resposta.status}`);
  return resposta.json();
}

function sparkline(curva) {
  if (!curva.length) return "";
  const maximo = Math.max(...curva) || 1;
  const pontos = curva
    .map((v, i) => `${(i / Math.max(curva.length - 1, 1)) * 100},${44 - (v / maximo) * 40}`)
    .join(" ");
  return `<svg class="sparkline" viewBox="0 0 100 44" preserveAspectRatio="none">
    <polyline points="${pontos}" fill="none" stroke="#5b8def" stroke-width="1.2"
      vector-effect="non-scaling-stroke" />
  </svg>`;
}

function minutos(segundos) {
  const m = Math.floor(segundos / 60);
  const s = Math.round(segundos % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function cardHtml(item, indice) {
  return `<div class="card ${indice === ativo ? "ativo" : ""}" data-sha1="${item.sha1}">
    <div class="cabecalho">
      <span class="nome">${item.filename}</span>
      <span class="meta">${Math.round(item.bpm)} BPM &middot; ${minutos(item.duration_s)}</span>
    </div>
    <div class="sugestao">
      <span class="rotulo" data-label="${item.label}">${item.label}</span>
      <span class="barra"><div style="width:${(item.confidence * 100).toFixed(0)}%"></div></span>
      <span class="confianca">confianca ${(item.confidence * 100).toFixed(0)}%
        &middot; escore ${item.score.toFixed(2)}</span>
    </div>
    ${sparkline(item.energy_curve)}
    <audio controls preload="none" src="/api/audio/${item.sha1}#t=${Math.floor(item.peak_offset_s)}"></audio>
    <div class="acoes">
      <button data-decidir="+1">+1</button>
      <button data-decidir="neutra">neutra</button>
      <button data-decidir="-1">-1</button>
      <button data-pular="1">pular</button>
    </div>
  </div>`;
}

function render(dados) {
  itens = dados.items;
  ativo = Math.min(ativo, Math.max(itens.length - 1, 0));

  const metricas = dados.metrics;
  document.getElementById("resumo").textContent = metricas
    ? `${itens.length} na fila &middot; modelo com ${metricas.n_examples} exemplos, `
      + `acerto ${(metricas.accuracy * 100).toFixed(0)}%, `
      + `erro ordinal ${metricas.ordinal_mae.toFixed(2)}`
    : `${itens.length} na fila &middot; modelo ainda nao treinado`;

  document.getElementById("aviso").innerHTML = dados.low_confidence_mode
    ? `<div class="aviso">Poucos exemplos rotulados. As confiancas estao reduzidas
       propositalmente ate o dataset crescer.</div>`
    : "";

  document.getElementById("fila").innerHTML = itens.length
    ? itens.map(cardHtml).join("")
    : `<p class="vazio">Nada na fila. Rode <code>dj scan</code> depois de baixar tracks novas.</p>`;
}

async function carregar() {
  render(await json("/api/queue"));
  const falhas = await json("/api/failures");
  document.getElementById("falhas").innerHTML = falhas.items.length
    ? falhas.items.map((f) => `<li>${f.filename} &mdash; ${f.reason}</li>`).join("")
    : `<li class="meta" style="color:#9aa0a6">Nenhuma.</li>`;
}

async function decidir(sha1, label) {
  await json("/api/decide", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ sha1, label }),
  });
  await carregar();
}

document.addEventListener("click", async (evento) => {
  const alvo = evento.target;
  const card = alvo.closest?.(".card");

  if (alvo.dataset?.decidir && card) {
    await decidir(card.dataset.sha1, alvo.dataset.decidir);
  } else if (alvo.dataset?.pular && card) {
    ativo = Math.min(ativo + 1, itens.length - 1);
    render({ items: itens, metrics: null, low_confidence_mode: false });
    await carregar();
  } else if (alvo.id === "btn-bloco") {
    const resultado = await json("/api/bulk-approve", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ min_confidence: LIMIAR_BLOCO }),
    });
    alert(`${resultado.moved} track(s) movida(s).`);
    await carregar();
  }
});

document.addEventListener("keydown", async (evento) => {
  if (!itens.length) return;
  const atalhos = { 1: "-1", 2: "neutra", 3: "+1" };

  if (atalhos[evento.key]) {
    evento.preventDefault();
    await decidir(itens[ativo].sha1, atalhos[evento.key]);
  } else if (evento.code === "Space") {
    evento.preventDefault();
    const player = document.querySelectorAll("audio")[ativo];
    if (player) player.paused ? player.play() : player.pause();
  }
});

carregar();
```

- [ ] **Step 3: Confirmar que os testes existentes continuam passando**

```bash
uv run pytest -v
```

Esperado: toda a suíte PASS. O teste `test_raiz_serve_a_pagina` continua verde com o HTML novo.

- [ ] **Step 4: Verificação manual**

Depois da Task 14, com `config.toml` apontando para pastas reais, rodar `uv run dj review` e conferir na tela:

1. Os cards aparecem ordenados com a menor confiança no topo.
2. A sparkline desenha a curva de energia e o pico coincide com a região que o player abre.
3. Teclas `1`, `2` e `3` movem a track do topo e a fila se atualiza.
4. Barra de espaço toca e pausa.
5. O botão de aprovação em bloco reporta a quantidade movida.

- [ ] **Step 5: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): interface de revisao com sparkline, player e atalhos"
```

---

### Task 14: Interface de linha de comando

**Files:**
- Create: `src/trackclassifier/cli.py`
- Create: `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_config`, `ConfigError` de `config`; `TrackService` de `service`; `create_app` de `web`; `NotEnoughClassesError` de `model`
- Produces:
  - `main(argv: list[str] | None = None) -> int` — código de saída `0` em sucesso, `1` em erro tratado
  - Subcomandos `scan`, `train`, `review`, todos aceitando `--config CAMINHO` (padrão: `config.toml`)

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_cli.py`:

```python
from trackclassifier.cli import main
from tests.test_service import _config, _povoa


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

    assert codigo == 0
    assert "analisadas" in capsys.readouterr().out.lower()


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
```

**Nota:** estes testes usam `HandcraftedExtractor` real, então os arquivos criados por `_povoa` precisam ser áudio de verdade. Ajustar `_povoa` em `tests/test_service.py` não é opção (quebraria a Task 10). Em vez disso, `test_cli.py` monkeypatcha o extrator: acrescentar no topo do arquivo, logo após os imports,

```python
import pytest

from tests.test_service import ExtratorFalso


@pytest.fixture(autouse=True)
def usa_extrator_falso(monkeypatch):
    monkeypatch.setattr("trackclassifier.service.HandcraftedExtractor", ExtratorFalso)
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
uv run pytest tests/test_cli.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.cli'`.

- [ ] **Step 3: Implementar `cli.py`**

```python
import argparse
import sys
from pathlib import Path

import uvicorn

from .config import ConfigError, load_config
from .labels import LABEL_ORDER
from .model import NotEnoughClassesError
from .service import TrackService
from .web import create_app


def _servico(caminho_config: str) -> TrackService:
    config = load_config(Path(caminho_config))
    servico = TrackService(config)
    servico.analyze_all()
    return servico


def _imprime_metricas(metricas) -> None:
    print(f"Exemplos rotulados: {metricas.n_examples}")
    print(f"Acuracia (leave-one-out): {metricas.accuracy * 100:.1f}%")
    print(f"Erro ordinal medio: {metricas.ordinal_mae:.3f}")
    print("Matriz de confusao (linha = real, coluna = previsto):")
    cabecalho = "        " + "".join(f"{rotulo.value:>8}" for rotulo in LABEL_ORDER)
    print(cabecalho)
    for rotulo, linha in zip(LABEL_ORDER, metricas.confusion):
        print(f"{rotulo.value:>8}" + "".join(f"{valor:>8}" for valor in linha))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dj", description="Classificador de tracks por energia")
    parser.add_argument("--config", default="config.toml", help="Caminho do config.toml")
    subcomandos = parser.add_subparsers(dest="comando", required=True)
    for nome, ajuda in (
        ("scan", "Extrai features das tracks ainda nao analisadas"),
        ("train", "Retreina o modelo e imprime as metricas"),
        ("review", "Sobe o servidor web de revisao"),
    ):
        sub = subcomandos.add_parser(nome, help=ajuda)
        sub.add_argument("--config", default="config.toml", help="Caminho do config.toml")
    argumentos = parser.parse_args(argv)

    try:
        servico = _servico(argumentos.config)
    except ConfigError as erro:
        print(f"Erro de configuracao: {erro}", file=sys.stderr)
        return 1

    falhas = servico.failures()
    if falhas:
        print(f"{len(falhas)} arquivo(s) falharam na analise:", file=sys.stderr)
        for falha in falhas:
            print(f"  {falha.filename}: {falha.reason}", file=sys.stderr)

    if argumentos.comando == "scan":
        print(f"{len(servico.cache)} track(s) analisadas no total.")
        return 0

    if argumentos.comando == "train":
        try:
            _imprime_metricas(servico.train())
        except NotEnoughClassesError as erro:
            print(str(erro), file=sys.stderr)
            return 1
        return 0

    try:
        _imprime_metricas(servico.train())
    except NotEnoughClassesError as erro:
        print(str(erro), file=sys.stderr)
        return 1

    print("Revisao em http://127.0.0.1:8000")
    uvicorn.run(create_app(servico), host="127.0.0.1", port=8000, log_level="warning")
    return 0
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

```bash
uv run pytest tests/test_cli.py -v
```

Esperado: 4 testes PASS.

- [ ] **Step 5: Escrever o `README.md`**

`ProjetosPessoais/TrackClassifier/README.md`:

````markdown
# TrackClassifier

Aprende o criterio pessoal de energia de um DJ a partir das pastas ja organizadas
e pre-classifica novos downloads em `+1`, `neutra` e `-1`.

## Pre-requisitos

```bash
brew install ffmpeg
```

## Instalacao

```bash
cd ProjetosPessoais/TrackClassifier
uv sync --extra dev
cp config.example.toml config.toml
```

Editar `config.toml` com os caminhos reais das tres pastas rotuladas e da pasta
de download.

## Uso

```bash
uv run dj scan     # extrai features das tracks novas
uv run dj train    # retreina e imprime as metricas
uv run dj review   # sobe a revisao em http://127.0.0.1:8000
```

Na revisao: `1` marca `-1`, `2` marca `neutra`, `3` marca `+1`, espaco toca e pausa.
Cada decisao move o arquivo para a pasta correspondente, e a cada 10 decisoes o
modelo retreina sozinho.

## Testes

```bash
uv run pytest
```
````

- [ ] **Step 6: Rodar a suíte inteira**

```bash
uv run pytest -v
```

Esperado: todos os testes de todas as tasks PASS.

- [ ] **Step 7: Commit**

```bash
git add ProjetosPessoais/TrackClassifier
git commit -m "feat(trackclassifier): CLI scan/train/review e documentacao de uso"
```

---

## Verificação final

Depois da Task 14, com `config.toml` apontando para as pastas reais:

- [ ] `uv run pytest` — suíte inteira verde
- [ ] `uv run dj scan` — analisa o acervo real sem travar; falhas aparecem listadas, não interrompem
- [ ] `uv run dj train` — imprime acurácia, erro ordinal e matriz de confusão sobre o acervo real
- [ ] `uv run dj review` — a fila carrega, o player toca no pico, os atalhos decidem, os arquivos aparecem nas pastas certas
