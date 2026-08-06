# UI desktop fase 4 — Key e Camelot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ler a tonalidade das tags durante o scan, guardar em forma canonica, e exibi-la como `KeyChip` colorido na Revisao e como coluna ordenavel na Biblioteca, com alternador entre notacao Camelot e classica.

**Architecture:** Um modulo puro `keys.py` (sem Qt, sem librosa) guarda a tonalidade como `pitch_class` + `mode` e formata so na hora de exibir. A leitura vem das tags, no mesmo passe de apresentacao que ja le titulo/artista/capa — ~1ms por track, sem decodificar audio. A cor do chip vem da roda de Camelot, via um helper novo gerado por `build_tokens.py`.

**Tech Stack:** Python 3.11+, `mutagen` (leitura de tags), `pandas`/`pyarrow` (parquet), PySide6-Essentials, pytest.

## Contexto: o que ja existe

Isto e a **fase 4 de 4** da spec `docs/superpowers/specs/2026-08-05-ui-desktop-design.md` — a ultima. As fases 1, 2 e 3 estao entregues e em `main`. O que ja funciona e este plano nao pode quebrar:

- `TrackService` (`service.py`) com `analyze_all(on_progress=..., should_cancel=...) -> bool`, `_preenche_apresentacao(refs, should_cancel)`, `presentation_for(sha1)`, `cover_path_for(sha1)`, `peaks_for(sha1)`, `ensure_peaks(sha1, path)`.
- `presentation.py` — `TrackTags`, `Cover`, `read_tags`, `extract_cover`, `VAZIO`, `PRESENTATION_VERSION = 1`, `PresentationRecord`, `PresentationCache`, `PeaksStore`. **Sem Qt, sem librosa.**
- `peaks.py` — `compute_bands`, computo preguicoso dos buckets RGB.
- `ui/viewmodel.py` — dataclasses puras, **nao importa Qt** (teste gramatical).
- `ui/widgets/track_model.py` — `Column(IntEnum)` com `WAVEFORM=0, TITULO=1, ARTISTA=2, GENERO=3, BPM=4, CLASSIFICACAO=5, CONFIANCA=6, DURACAO=7`, `_HEADERS`, `_WIDTHS`, `SEM_DADO = "—"`, `_sort_key`.
- `ui/widgets/delegates.py` — `TRACK_ROLE`, `_DelegateComFundo`, `WaveformDelegate`, `TitleDelegate`, `ClassificationDelegate`.
- `ui/tokens.py` — **gerado**, ja contem `COLOR_CAMELOT_1` ate `COLOR_CAMELOT_12` e o helper `classification_colors(label)`.
- `design/build_tokens.py` — gera `ui/tokens.py` e `ui/app.qss`; ja emite `classification_colors` (ver `build_py`, o bloco `lines += [...]` no fim).

## Global Constraints

- **Portugues sem acentos** em tudo interno: variaveis locais, funcoes internas, comentarios, docstrings, mensagens de erro, nomes de teste e texto de UI visivel. API publica (dataclasses, campos de parquet, nomes de classe) em **ingles**.
- Comentarios explicam **por que**, nao o que — longos quando a decisao nao e obvia.
- ruff: `line-length = 100`, regras `E,F,I,UP,B`. `uv run ruff check .` e gate do CI.
- Commits: conventional commits com escopo (`feat(trackclassifier):`, `feat(ui):`).
- **`ui/viewmodel.py` nao pode importar Qt.** `tests/test_viewmodel.py::test_viewmodel_nao_importa_qt` le o modulo e falha se aparecer `PySide6`. Importar `keys.py` la e permitido — `keys.py` e dominio puro.
- **Nenhum hex fora de `design/design-tokens.json`.** `tests/test_tokens.py::test_nenhum_hex_fora_do_json` varre `ui/` e falha se achar um literal de cor fora de `tokens.py`/`app.qss`.
- **`ui/tokens.py` e `ui/app.qss` sao GERADOS.** Nunca editar a mao — editar `design/build_tokens.py` (ou o JSON) e rodar `uv run python design/build_tokens.py`. `tests/test_tokens.py::test_arquivos_gerados_estao_em_dia_com_o_json` roda o gerador e falha se o resultado divergir do que esta commitado.
- **Nao alterar `FEATURE_NAMES` nem `HandcraftedExtractor.name`.** Qualquer mudanca ali invalida o cache de ML da biblioteca inteira.
- Escrita de estado em disco e **atomica**: `.tmp` no mesmo diretorio + `os.replace`.
- Erros degradam e sao reportados, nunca derrubam o comando.
- Python `>=3.11,<3.14`.

## Fatos verificados sobre key em tags

Estes foram **testados neste repositorio** antes de escrever o plano. Nao sao suposicoes.

1. Uma unica chamada `mutagen.File(caminho)` cobre os quatro formatos, mas o acesso e **diferente em cada familia** — nao ha API unificada, exatamente como aconteceu com a capa na fase 2:

   | Formato | `type(mutagen.File(p))` | Onde a key vive | Como ler |
   |---|---|---|---|
   | FLAC, OGG | `FLAC`, `OggVorbis` | vorbis comment | `tags.get("initialkey")` ou `tags.get("key")` -> lista de `str` |
   | MP3, AIFF, WAV | `MP3`, `AIFF`, `WAVE` | frame ID3 `TKEY` | `tags.getall("TKEY")` -> lista de `TKEY`, texto em `.text[0]` |
   | M4A | `MP4` | atom freeform | `tags.get("----:com.apple.iTunes:initialkey")` -> lista de `MP4FreeForm` |

2. **`MP4FreeForm` e subclasse de `bytes`** — igual ao `MP4Cover` que causou o achado Important da fase 2. Precisa de `.decode("utf-8")`, nao de um atributo `.text`/`.data`. Este e o mesmo tipo de armadilha, no mesmo lugar do codigo: nao repita o erro.

3. `mutagen.File(..., easy=True)` **nao** expoe `TKEY` em MP3 (`easy.keys()` devolve `None` para um mp3 so com TKEY). Em FLAC ele expoe `key`/`initialkey` porque vorbis comments passam direto. Ou seja: **a leitura de key nao pode usar o caminho `easy`** que `read_tags` usa — precisa do objeto cru.

4. `mutagen.File(...)` devolve um objeto **falsy** (nao `None`) para arquivo sem tags. `is None` significa "formato nao reconhecido". Isto ja esta documentado em `CLAUDE.md` desde a fase 2 — vale aqui tambem.

5. `soundfile` escreve FLAC, MP3, AIFF e WAV; `.m4a` precisa de `ffmpeg` (disponivel no PATH, e o CI ja instala). Para gravar ID3 em AIFF nos testes, use `mutagen.aiff.AIFF` + `add_tags()` — chamar `ID3().save(caminho_aiff)` direto **corrompe o arquivo** (o mutagen passa a ler como MP3 e levanta `HeaderNotFoundError`).

## Decisao de escopo: a key vem da tag, nao de analise de audio

A spec previa detectar a key por audio (chroma CQT + correlacao Krumhansl-Schmuckler, ~1-2s por track, no mesmo caminho preguicoso dos buckets). **Esta fase nao faz isso** — le so a tag. As razoes, registradas para quem for reabrir:

- Rekordbox e Mixed In Key ja gravam a key na tag na maioria dos acervos de DJ reais. Ler custa ~1ms e o valor vem de uma ferramenta especializada.
- KS sobre chroma acerta ~60-70% em musica eletronica. Exibir uma key errada com a mesma confianca visual de uma certa e pior, para quem mixa harmonicamente, do que exibir travessao.
- Sem analise nova, esta fase nao precisa de nenhuma infra preguicosa: a key entra no passe de apresentacao que ja existe.

Se a deteccao por audio entrar depois, o desenho aqui ja acomoda: `Key` e canonica, `PresentationRecord.key` e a fonte unica, e bastaria um caminho preguicoso preenchendo o mesmo campo para quem nao tem tag.

## Decisao de escopo: `compatible_keys` nao e portado

O `keys.py` do ref2 traz `compatible_keys(key)` (vizinhos +/-1 na roda de Camelot e o relativo maior/menor). A spec lista **"Destaque de keys compatíveis"** explicitamente em **Escopo cortado** ("e feature de montar set, nao de classificar energia"). A funcao nao entra — YAGNI, e portar codigo morto convida alguem a liga-lo sem passar pela decisao.

`ALL_KEYS` **e** portado: serve ao teste que percorre as 24 tonalidades, que a propria spec pede na tabela de testes.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/trackclassifier/keys.py` | **NOVO.** Dominio puro: `Mode`, `KeyNotation`, `Key`, `parse_key`, `format_key`, `ALL_KEYS`. Sem Qt, sem librosa, sem mutagen. |
| `src/trackclassifier/presentation.py` | Modificar: `read_key`, key em `PresentationRecord`/`PresentationCache`, `PRESENTATION_VERSION` para 2. |
| `src/trackclassifier/service.py` | Modificar: `_preenche_apresentacao` le a key junto com tags e capa. |
| `src/trackclassifier/ui/viewmodel.py` | Modificar: `TrackRow.key: Key \| None`. |
| `design/build_tokens.py` | Modificar: emitir o helper `camelot_color(number)`. |
| `src/trackclassifier/ui/tokens.py` | **GERADO** — sai do gerador acima, nunca editado a mao. |
| `src/trackclassifier/ui/widgets/key_chip.py` | **NOVO.** `KeyChip`, o widget do chip colorido pela roda de Camelot. |
| `src/trackclassifier/ui/widgets/delegates.py` | Modificar: `KeyDelegate`, pinta o chip na coluna da tabela. |
| `src/trackclassifier/ui/widgets/track_model.py` | Modificar: coluna `KEY`, ordenacao pelo numero de Camelot, notacao corrente. |
| `src/trackclassifier/ui/library_tab.py` | Modificar: alternador de notacao, coluna nova, repasse da notacao. |
| `src/trackclassifier/ui/review_tab.py` | Modificar: `KeyChip` no cabecalho. |
| `src/trackclassifier/ui/window.py` | Modificar: notacao e preferencia global, relaiada as duas abas. |
| `CLAUDE.md` | Modificar: documentar a forma canonica e a armadilha do `MP4FreeForm`. |
| `tests/test_keys.py` | **NOVO.** As 24 tonalidades, parse de lixo de tag, round-trip. |

---

### Task 1: Modulo `keys.py` (dominio puro)

**Files:**
- Create: `src/trackclassifier/keys.py`
- Create: `tests/test_keys.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `Mode(Enum)` — `MAJOR = "B"`, `MINOR = "A"`
  - `KeyNotation(Enum)` — `CAMELOT = "camelot"`, `CLASSIC = "classic"`
  - `Key` — dataclass congelada com `pitch_class: int` (0-11) e `mode: Mode`; propriedades `camelot -> str`, `classic -> str`, `camelot_number -> int`; metodo `format(notation: KeyNotation) -> str`
  - `parse_key(text: str) -> Key | None`
  - `format_key(key: Key | None, notation: KeyNotation) -> str`
  - `ALL_KEYS: tuple[Key, ...]` — as 24

- [ ] **Step 1: Escrever os testes**

Crie `tests/test_keys.py`:

```python
"""Conversao entre notacao Camelot e classica. Funcoes puras, sem Qt."""

import pytest

from trackclassifier.keys import (
    ALL_KEYS,
    Key,
    KeyNotation,
    Mode,
    format_key,
    parse_key,
)


def test_existem_exatamente_24_tonalidades():
    assert len(ALL_KEYS) == 24
    assert len(set(ALL_KEYS)) == 24


def test_toda_tonalidade_faz_round_trip_nas_duas_notacoes():
    # E o contrato que sustenta guardar a forma canonica em vez da string:
    # se o round-trip quebrasse, trocar de notacao perderia dado.
    for chave in ALL_KEYS:
        assert parse_key(chave.camelot) == chave
        assert parse_key(chave.classic) == chave


def test_camelot_de_referencia():
    # 8A = Am e o exemplo canonico da roda de Camelot; 8B = C e o relativo.
    assert Key(9, Mode.MINOR).camelot == "8A"
    assert Key(9, Mode.MINOR).classic == "Am"
    assert Key(0, Mode.MAJOR).camelot == "8B"
    assert Key(0, Mode.MAJOR).classic == "C"


def test_camelot_number_fica_entre_1_e_12():
    for chave in ALL_KEYS:
        assert 1 <= chave.camelot_number <= 12


def test_pitch_class_fora_da_faixa_levanta():
    with pytest.raises(ValueError):
        Key(12, Mode.MINOR)
    with pytest.raises(ValueError):
        Key(-1, Mode.MAJOR)


def test_format_respeita_a_notacao():
    chave = Key(9, Mode.MINOR)
    assert chave.format(KeyNotation.CAMELOT) == "8A"
    assert chave.format(KeyNotation.CLASSIC) == "Am"


def test_parse_aceita_enarmonicos_que_aparecem_em_tag_id3():
    # Tags de ID3 nao seguem padrao nenhum: o mesmo tom aparece como C#m ou
    # Dbm dependendo da ferramenta que gravou.
    assert parse_key("C#m") == parse_key("Dbm")
    assert parse_key("G#") == parse_key("Ab")


def test_parse_tolera_espaco_e_caixa():
    assert parse_key("  8a  ") == Key(9, Mode.MINOR)
    assert parse_key("AM") == parse_key("Am")


def test_parse_de_lixo_devolve_none():
    # A tag pode conter qualquer coisa; quem chama decide o que fazer.
    for lixo in ("", "   ", "banana", "13A", "0A", "8C", "H", "999"):
        assert parse_key(lixo) is None, lixo


def test_format_key_de_none_mostra_travessao():
    assert format_key(None, KeyNotation.CAMELOT) == "—"
    assert format_key(Key(9, Mode.MINOR), KeyNotation.CAMELOT) == "8A"
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_keys.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.keys'`

- [ ] **Step 3: Implementar `keys.py`**

Crie `src/trackclassifier/keys.py`. E um porte do prototipo de referencia, **sem** o `compatible_keys` (ver "Decisao de escopo" acima):

```python
"""Conversao entre notacao Camelot e classica.

Funcoes puras, sem dependencia de Qt nem de mutagen. A key e guardada em
forma canonica (pitch class + modo) e formatada so na hora de exibir --
gravar a string "8A" no parquet inviabilizaria trocar de notacao depois, que
e exatamente o alternador que esta fase entrega.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final


class Mode(Enum):
    """Modo da tonalidade. Camelot usa A para menor e B para maior."""

    MAJOR = "B"
    MINOR = "A"


class KeyNotation(Enum):
    """Como a key e exibida. Preferencia global, alternavel na Biblioteca."""

    CAMELOT = "camelot"
    CLASSIC = "classic"


#: pitch class: 0 = C, 1 = C#/Db, ... 11 = B
_CAMELOT_PARA_PITCH: Final[dict[tuple[int, Mode], int]] = {
    (1, Mode.MINOR): 8,   (1, Mode.MAJOR): 11,
    (2, Mode.MINOR): 3,   (2, Mode.MAJOR): 6,
    (3, Mode.MINOR): 10,  (3, Mode.MAJOR): 1,
    (4, Mode.MINOR): 5,   (4, Mode.MAJOR): 8,
    (5, Mode.MINOR): 0,   (5, Mode.MAJOR): 3,
    (6, Mode.MINOR): 7,   (6, Mode.MAJOR): 10,
    (7, Mode.MINOR): 2,   (7, Mode.MAJOR): 5,
    (8, Mode.MINOR): 9,   (8, Mode.MAJOR): 0,
    (9, Mode.MINOR): 4,   (9, Mode.MAJOR): 7,
    (10, Mode.MINOR): 11, (10, Mode.MAJOR): 2,
    (11, Mode.MINOR): 6,  (11, Mode.MAJOR): 9,
    (12, Mode.MINOR): 1,  (12, Mode.MAJOR): 4,
}

_PITCH_PARA_CAMELOT: Final[dict[tuple[int, Mode], int]] = {
    (pitch, modo): numero for (numero, modo), pitch in _CAMELOT_PARA_PITCH.items()
}

#: Grafia usada por Rekordbox/Mixed In Key: bemois no menor, exceto F#m.
_NOMES_MENOR: Final[tuple[str, ...]] = (
    "Cm", "Dbm", "Dm", "Ebm", "Em", "Fm",
    "F#m", "Gm", "Abm", "Am", "Bbm", "Bm",
)
_NOMES_MAIOR: Final[tuple[str, ...]] = (
    "C", "Db", "D", "Eb", "E", "F",
    "F#", "G", "Ab", "A", "Bb", "B",
)

#: Enarmonicos aceitos na leitura de tag: ID3 nao segue padrao nenhum, e o
#: mesmo tom aparece como C#m ou Dbm conforme a ferramenta que gravou.
_ALIASES: Final[dict[str, str]] = {
    "c#m": "Dbm", "d#m": "Ebm", "gbm": "F#m", "g#m": "Abm", "a#m": "Bbm",
    "c#": "Db", "d#": "Eb", "gb": "F#", "g#": "Ab", "a#": "Bb",
}

SEM_KEY: Final[str] = "—"


@dataclass(frozen=True, slots=True)
class Key:
    """Tonalidade canonica. `pitch_class` 0-11 com 0 = C."""

    pitch_class: int
    mode: Mode

    def __post_init__(self) -> None:
        if not 0 <= self.pitch_class <= 11:
            raise ValueError(f"pitch_class fora de 0-11: {self.pitch_class}")

    @property
    def camelot(self) -> str:
        """Ex.: '8A'."""
        return f"{_PITCH_PARA_CAMELOT[(self.pitch_class, self.mode)]}{self.mode.value}"

    @property
    def classic(self) -> str:
        """Ex.: 'Am'."""
        tabela = _NOMES_MENOR if self.mode is Mode.MINOR else _NOMES_MAIOR
        return tabela[self.pitch_class]

    @property
    def camelot_number(self) -> int:
        """1-12. E o que define a cor do chip na roda de Camelot."""
        return _PITCH_PARA_CAMELOT[(self.pitch_class, self.mode)]

    def format(self, notation: KeyNotation) -> str:
        return self.camelot if notation is KeyNotation.CAMELOT else self.classic


def parse_key(text: str) -> Key | None:
    """Le '8A', 'Am', 'C#m' ou 'F'. Devolve None se nao reconhecer.

    Best-effort de proposito: a tag pode conter qualquer coisa (inclusive
    texto livre de quem catalogou a mao), e quem chama decide o que fazer
    com None -- aqui, mostrar travessao.
    """
    bruto = text.strip()
    if not bruto:
        return None

    # Camelot: numero seguido de A ou B.
    if len(bruto) >= 2 and bruto[:-1].isdigit() and bruto[-1].upper() in ("A", "B"):
        numero = int(bruto[:-1])
        modo = Mode.MINOR if bruto[-1].upper() == "A" else Mode.MAJOR
        pitch = _CAMELOT_PARA_PITCH.get((numero, modo))
        return Key(pitch, modo) if pitch is not None else None

    # Classica, com enarmonicos tolerados.
    nome = _ALIASES.get(bruto.lower(), bruto)
    normalizado = nome[0].upper() + nome[1:].replace("M", "m")
    if normalizado in _NOMES_MENOR:
        return Key(_NOMES_MENOR.index(normalizado), Mode.MINOR)
    if normalizado in _NOMES_MAIOR:
        return Key(_NOMES_MAIOR.index(normalizado), Mode.MAJOR)
    return None


def format_key(key: Key | None, notation: KeyNotation) -> str:
    """Formata para exibicao. Track sem key mostra travessao."""
    return key.format(notation) if key is not None else SEM_KEY


ALL_KEYS: Final[tuple[Key, ...]] = tuple(
    Key(pitch, modo)
    for (pitch, modo) in sorted(
        _PITCH_PARA_CAMELOT, key=lambda k: (_PITCH_PARA_CAMELOT[k], k[1].value)
    )
)
```

> O guard `len(bruto) >= 2` no ramo Camelot e deliberado: sem ele, a string
> `"A"` sozinha entraria no ramo (porque `""[:-1].isdigit()` e `False`, mas
> `"A"[:-1]` e `""` e `"".isdigit()` tambem e `False` — o ramo nao dispara,
> mas a intencao fica ilegivel). Com o guard, o leitor ve a regra: precisa de
> pelo menos um digito **e** a letra.

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_keys.py -v`
Expected: PASS nos 10.

- [ ] **Step 5: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS. Nada fora do modulo novo foi tocado.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/keys.py tests/test_keys.py
git commit -m "feat(trackclassifier): modulo de conversao Camelot/classica"
```

---

### Task 2: Leitura da key das tags

**Files:**
- Modify: `src/trackclassifier/presentation.py`
- Modify: `tests/test_presentation.py`

**Interfaces:**
- Consumes: `Key`, `parse_key` da Task 1.
- Produces: `read_key(path: Path) -> Key | None`

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_presentation.py`. Reuse os helpers `_flac_com_tags` e `_sem_tags` que ja existem no arquivo (confira os nomes antes; se divergirem, adapte):

```python
def test_le_key_de_vorbis_comment_num_flac(tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.keys import Key, Mode
    from trackclassifier.presentation import read_key

    caminho = _flac_com_tags(tmp_path, title="Glue")
    arquivo = FLAC(caminho)
    arquivo["initialkey"] = ["8A"]
    arquivo.save()

    assert read_key(caminho) == Key(9, Mode.MINOR)


def test_le_key_do_campo_key_quando_nao_ha_initialkey(tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.keys import Key, Mode
    from trackclassifier.presentation import read_key

    caminho = _flac_com_tags(tmp_path, title="Glue")
    arquivo = FLAC(caminho)
    arquivo["key"] = ["Am"]
    arquivo.save()

    assert read_key(caminho) == Key(9, Mode.MINOR)


def test_le_key_de_tkey_num_mp3(tmp_path):
    # easy=True NAO expoe TKEY em mp3 -- por isso read_key usa o objeto cru.
    import numpy as np
    import soundfile as sf
    from mutagen.id3 import TKEY
    from mutagen.mp3 import MP3

    from trackclassifier.keys import Key, Mode
    from trackclassifier.presentation import read_key

    caminho = tmp_path / "t.mp3"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="MP3")
    arquivo = MP3(caminho)
    if arquivo.tags is None:
        arquivo.add_tags()
    arquivo.tags.add(TKEY(encoding=3, text="5A"))
    arquivo.save()

    assert read_key(caminho) == Key(0, Mode.MINOR)


def test_le_key_de_atom_freeform_num_m4a(tmp_path):
    # MP4FreeForm e subclasse de bytes, igual ao MP4Cover da fase 2: sem
    # decode, a key some em silencio.
    import subprocess

    import numpy as np
    import soundfile as sf
    from mutagen.mp4 import MP4

    from trackclassifier.keys import Key, Mode
    from trackclassifier.presentation import read_key

    wav = tmp_path / "fonte.wav"
    sf.write(wav, np.zeros(22050, dtype="float32"), 22050)
    caminho = tmp_path / "t.m4a"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav), "-c:a", "aac", str(caminho)],
        check=True,
        capture_output=True,
    )
    arquivo = MP4(caminho)
    arquivo["----:com.apple.iTunes:initialkey"] = [b"8A"]
    arquivo.save()

    assert read_key(caminho) == Key(9, Mode.MINOR)


def test_le_key_de_id3_num_aiff(tmp_path):
    # AIFF carrega ID3 num chunk proprio: precisa do wrapper mutagen.aiff.AIFF.
    # ID3().save(caminho_aiff) direto CORROMPE o arquivo.
    import numpy as np
    import soundfile as sf
    from mutagen.aiff import AIFF
    from mutagen.id3 import TKEY

    from trackclassifier.keys import Key, Mode
    from trackclassifier.presentation import read_key

    caminho = tmp_path / "t.aiff"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="AIFF")
    arquivo = AIFF(caminho)
    if arquivo.tags is None:
        arquivo.add_tags()
    arquivo.tags.add(TKEY(encoding=3, text="Am"))
    arquivo.save()

    assert read_key(caminho) == Key(9, Mode.MINOR)


def test_arquivo_sem_key_devolve_none(tmp_path):
    from trackclassifier.presentation import read_key

    assert read_key(_sem_tags(tmp_path)) is None


def test_key_ilegivel_na_tag_devolve_none(tmp_path):
    # Alguem catalogou a mao e escreveu texto livre no campo.
    from mutagen.flac import FLAC

    from trackclassifier.presentation import read_key

    caminho = _flac_com_tags(tmp_path, title="Glue")
    arquivo = FLAC(caminho)
    arquivo["initialkey"] = ["sei la, algo em menor"]
    arquivo.save()

    assert read_key(caminho) is None


def test_key_de_arquivo_ilegivel_devolve_none(tmp_path):
    from trackclassifier.presentation import read_key

    caminho = tmp_path / "mentira.flac"
    caminho.write_bytes(b"isto nao e audio")

    assert read_key(caminho) is None
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_presentation.py -v -k key`
Expected: FAIL com `ImportError: cannot import name 'read_key'`

- [ ] **Step 3: Implementar `read_key`**

Em `src/trackclassifier/presentation.py`, acrescente ao import do topo:

```python
from .keys import Key, parse_key
```

E as constantes, junto das que ja existem (`_SUFIXO_POR_MIME`, `_COVER_FRONT`):

```python
#: Campos de key em vorbis comment (FLAC/OGG), na ordem de preferencia.
#: initialkey e o que Rekordbox e Mixed In Key escrevem; `key` aparece em
#: exportacoes mais antigas e em quem catalogou a mao.
_CAMPOS_VORBIS_KEY = ("initialkey", "key")

#: Atom freeform do MP4/M4A. O prefixo "----" e a convencao do container
#: para chave custom com namespace.
_ATOM_MP4_KEY = "----:com.apple.iTunes:initialkey"
```

E a funcao, apos `extract_cover`:

```python
def _texto_de_key(arquivo) -> str | None:
    """Extrai o texto cru da key. Tres familias, tres acessos diferentes.

    Nao ha API unificada no mutagen -- mesmo problema de _imagens_embutidas.
    E o caminho `easy` nao serve aqui: ele nao expoe TKEY em mp3, so os
    vorbis comments do FLAC.
    """
    tags = getattr(arquivo, "tags", None)
    if tags is None:
        # Arquivo sem bloco de tags nenhum. Caso comum de wav recem-exportado.
        return None

    if hasattr(tags, "getall"):
        # ID3 (mp3, aiff, wav): TKEY guarda o texto numa lista em .text.
        for frame in tags.getall("TKEY"):
            texto = _primeiro(getattr(frame, "text", None))
            if texto is not None:
                return texto
        return None

    if not hasattr(tags, "get"):
        return None

    for campo in _CAMPOS_VORBIS_KEY:
        texto = _primeiro(tags.get(campo))
        if texto is not None:
            return texto

    # MP4/M4A: MP4FreeForm e subclasse de BYTES -- o proprio objeto e o
    # conteudo, sem atributo .text nem .data. Mesma armadilha do MP4Cover na
    # extracao de capa; tratar como str aqui devolveria "b'8A'".
    bruto = tags.get(_ATOM_MP4_KEY)
    if bruto:
        primeiro = bruto[0]
        if isinstance(primeiro, bytes):
            return primeiro.decode("utf-8", errors="replace").strip() or None
        texto = str(primeiro).strip()
        return texto or None

    return None


def read_key(path: Path) -> Key | None:
    """Le a tonalidade da tag. Nunca levanta.

    Custa ~1ms e nao decodifica audio. Devolve None quando nao ha tag, quando
    o formato nao e reconhecido, ou quando o texto da tag nao e uma key
    valida -- a tag e texto livre e frequentemente tem lixo.
    """
    try:
        arquivo = mutagen.File(Path(path))
    except Exception:
        return None
    # `is None` e "formato nao reconhecido". NAO troque por `if not arquivo`:
    # um arquivo sem tags e um objeto valido e FALSY ao mesmo tempo.
    if arquivo is None:
        return None

    texto = _texto_de_key(arquivo)
    return parse_key(texto) if texto is not None else None
```

- [ ] **Step 4: Rodar os testes**

Run: `uv run pytest tests/test_presentation.py -v`
Expected: PASS em todos, inclusive os 8 novos.

- [ ] **Step 5: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/presentation.py tests/test_presentation.py
git commit -m "feat(trackclassifier): le a tonalidade das tags nos quatro formatos"
```

---

### Task 3: Key no cache de apresentacao e no scan

**Files:**
- Modify: `src/trackclassifier/presentation.py`
- Modify: `src/trackclassifier/service.py`
- Modify: `tests/test_presentation.py`
- Modify: `tests/test_service.py`

**Interfaces:**
- Consumes: `read_key` da Task 2; `Key`, `Mode` da Task 1.
- Produces:
  - `PRESENTATION_VERSION = 2`
  - `PresentationRecord.key: Key | None`
  - `PresentationCache.put(sha1, tags, cover, key)` — assinatura com o quarto parametro
  - `TrackService.key_for(sha1: str) -> Key | None`

> **Atencao:** `PRESENTATION_VERSION` sobe de 1 para 2 porque o schema do
> parquet ganha duas colunas. Isso invalida os registros antigos, e o passe
> de apresentacao os reconstroi no proximo scan — ~1ms por track, sem
> decodificar audio. E exatamente o cenario para o qual a versao propria
> existe: **o cache de ML nao e tocado**.

- [ ] **Step 1: Escrever os testes do cache**

Acrescente a `tests/test_presentation.py`:

```python
def test_cache_guarda_e_devolve_a_key(tmp_path):
    from trackclassifier.keys import Key, Mode
    from trackclassifier.presentation import TrackTags

    cache = _cache(tmp_path)
    cache.put("abc123", TrackTags(None, None, None, None), None, Key(9, Mode.MINOR))

    registro = cache.get("abc123")
    assert registro is not None
    assert registro.key == Key(9, Mode.MINOR)


def test_cache_sem_key_devolve_none(tmp_path):
    from trackclassifier.presentation import TrackTags

    cache = _cache(tmp_path)
    cache.put("abc123", TrackTags(None, None, None, None), None, None)

    registro = cache.get("abc123")
    assert registro is not None
    assert registro.key is None


def test_key_sobrevive_ao_round_trip_do_parquet(tmp_path):
    # A forma canonica (pitch + modo) tem que voltar identica: e o que
    # permite trocar de notacao sem reler as tags.
    from trackclassifier.keys import ALL_KEYS
    from trackclassifier.presentation import PresentationCache, TrackTags

    caminho = tmp_path / "presentation.parquet"
    covers = tmp_path / "covers"

    primeiro = PresentationCache(caminho, covers)
    for i, chave in enumerate(ALL_KEYS):
        primeiro.put(f"sha{i}", TrackTags(None, None, None, None), None, chave)
    primeiro.save()

    segundo = PresentationCache(caminho, covers)
    for i, chave in enumerate(ALL_KEYS):
        registro = segundo.get(f"sha{i}")
        assert registro is not None
        assert registro.key == chave, f"{chave.camelot} nao sobreviveu"


def test_key_invalida_no_parquet_vira_none_em_vez_de_estourar(tmp_path):
    # Um pitch_class fora de 0-11 gravado por uma versao futura/quebrada nao
    # pode derrubar o boot da janela: Key() levanta ValueError no construtor.
    import pandas as pd

    from trackclassifier.presentation import PRESENTATION_VERSION, PresentationCache

    caminho = tmp_path / "presentation.parquet"
    pd.DataFrame(
        [
            {
                "sha1": "abc123",
                "title": None,
                "artist": None,
                "album": None,
                "genre": None,
                "cover_suffix": None,
                "key_pc": 99,
                "key_mode": "A",
                "version": PRESENTATION_VERSION,
            }
        ]
    ).to_parquet(caminho, index=False)

    registro = PresentationCache(caminho, tmp_path / "covers").get("abc123")
    assert registro is not None
    assert registro.key is None
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_presentation.py -v -k key`
Expected: FAIL — `put()` ainda aceita 3 argumentos, `PresentationRecord` nao tem `key`.

- [ ] **Step 3: Atualizar o cache**

Em `src/trackclassifier/presentation.py`:

Suba a versao e as colunas:

```python
#: Bumpe quando o CONTEUDO produzido por este modulo mudar (campo novo, regra
#: de extracao diferente). Recalcula so apresentacao -- ~1ms por track, sem
#: decodificar audio -- e nunca toca no cache de ML.
#:
#: 2: key_pc/key_mode acrescentados (fase 4).
PRESENTATION_VERSION = 2

_COLUNAS = [
    "sha1",
    "title",
    "artist",
    "album",
    "genre",
    "cover_suffix",
    "key_pc",
    "key_mode",
    "version",
]
```

Acrescente o campo a `PresentationRecord`:

```python
@dataclass(frozen=True)
class PresentationRecord:
    sha1: str
    title: str | None
    artist: str | None
    album: str | None
    genre: str | None
    cover_suffix: str | None
    key: Key | None = None
```

Acrescente o helper de reconstrucao, junto de `_ou_none`:

```python
def _key_de(registro: dict) -> Key | None:
    """Reconstroi a Key das duas colunas do parquet.

    Guarda-se pitch_class + modo, nunca a string formatada: gravar "8A"
    inviabilizaria o alternador de notacao, que so pode existir porque a
    forma canonica sobrevive ao round-trip.
    """
    pitch = registro.get("key_pc")
    modo = _ou_none(registro.get("key_mode"))
    if pitch is None or modo is None or (isinstance(pitch, float) and pd.isna(pitch)):
        return None
    try:
        return Key(int(pitch), Mode(modo))
    except (ValueError, TypeError):
        # pitch fora de 0-11 ou modo desconhecido: parquet de uma versao
        # futura, ou escrito por outra ferramenta. Cair para None e melhor
        # do que derrubar o boot da janela.
        return None
```

E acrescente `Mode` ao import de `keys`:

```python
from .keys import Key, Mode, parse_key
```

Em `get()`, passe a key adiante:

```python
        return PresentationRecord(
            sha1=sha1,
            title=_ou_none(registro.get("title")),
            artist=_ou_none(registro.get("artist")),
            album=_ou_none(registro.get("album")),
            genre=_ou_none(registro.get("genre")),
            cover_suffix=_ou_none(registro.get("cover_suffix")),
            key=_key_de(registro),
        )
```

E em `put()`, o quarto parametro e as duas colunas novas:

```python
    def put(
        self,
        sha1: str,
        tags: TrackTags,
        cover: Cover | None,
        key: Key | None = None,
    ) -> None:
```

com o dict final virando:

```python
        self._linhas[sha1] = {
            "sha1": sha1,
            "title": tags.title,
            "artist": tags.artist,
            "album": tags.album,
            "genre": tags.genre,
            "cover_suffix": sufixo,
            "key_pc": key.pitch_class if key is not None else None,
            "key_mode": key.mode.value if key is not None else None,
            "version": PRESENTATION_VERSION,
        }
```

> `key` tem default `None` para nao quebrar nenhuma chamada existente de
> `put()` que este plano nao tenha previsto. O passe de apresentacao (Step 5)
> sempre passa o valor de verdade.

- [ ] **Step 4: Escrever o teste de servico**

Acrescente a `tests/test_service.py`:

```python
def test_scan_le_a_key_da_tag(tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.keys import Key, Mode

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.5.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["initialkey"] = ["8A"]
    arquivo.save()

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()

    sha1 = servico._inbox[0].sha1
    assert servico.key_for(sha1) == Key(9, Mode.MINOR)


def test_track_sem_key_na_tag_fica_com_key_none(tmp_path):
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()

    assert servico.key_for(servico._labeled[0].sha1) is None


def test_falha_ao_ler_key_nao_entra_em_failures(tmp_path):
    # Mesma regra de tags e capa: metadado ausente nao e falha de analise.
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)

    import trackclassifier.service as modulo

    original = modulo.read_key

    def _explode(caminho):
        raise OSError("disco resolveu sumir")

    modulo.read_key = _explode
    try:
        servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
        servico.analyze_all()
    finally:
        modulo.read_key = original

    assert servico.failures() == []
```

- [ ] **Step 5: Ligar no servico**

Em `src/trackclassifier/service.py`, acrescente `read_key` ao import de `presentation` (import direto, como os outros — os testes fazem monkey-patch de `trackclassifier.service.read_key`):

```python
from .presentation import (
    VAZIO,
    PresentationCache,
    PresentationRecord,
    extract_cover,
    read_key,
    read_tags,
)
```

E acrescente `Key` ao import de `keys`:

```python
from .keys import Key
```

Dentro de `_preenche_apresentacao`, no bloco `try`, leia a key junto e passe adiante:

```python
            try:
                tags = read_tags(ref.path)
                capa = extract_cover(ref.path)
                chave = read_key(ref.path)
            except Exception:
                # read_tags/extract_cover/read_key ja contem tudo o que sabem
                # conter; chegar aqui e algo fora deles (o proprio open
                # falhando por permissao, arquivo removido no meio do scan).
                # Grava vazio em vez de deixar a track sem registro: sem isto,
                # ela seria retentada a cada scan, para sempre.
                tags, capa, chave = VAZIO, None, None
            self.presentation.put(ref.sha1, tags, capa, chave)
```

E o acessor, junto de `presentation_for`/`cover_path_for`:

```python
    def key_for(self, sha1: str) -> Key | None:
        registro = self.presentation.get(sha1)
        return registro.key if registro is not None else None
```

- [ ] **Step 6: Rodar os testes**

Run: `uv run pytest tests/test_presentation.py tests/test_service.py -v`
Expected: PASS. Os testes de cancelamento e de apresentacao das fases 2 e 3 continuam passando.

- [ ] **Step 7: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/trackclassifier/presentation.py src/trackclassifier/service.py tests/
git commit -m "feat(trackclassifier): guarda a key canonica no cache de apresentacao"
```

---

### Task 4: `TrackRow.key`

**Files:**
- Modify: `src/trackclassifier/ui/viewmodel.py`
- Modify: `tests/test_viewmodel.py`

**Interfaces:**
- Consumes: `TrackService.key_for(sha1)` da Task 3; `Key` da Task 1.
- Produces: `TrackRow.key: Key | None`

> **Atencao:** `TrackRow` e construida em **dois** lugares de `viewmodel.py` —
> `_row_da_fila(item, service)` e dentro do laco de `library_state(service)`.
> Os dois precisam preencher o campo. E `viewmodel.py` continua proibido de
> importar Qt; `keys.py` e dominio puro, entao importa-lo la e permitido.

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_viewmodel.py`:

```python
def test_track_row_traz_a_key_do_servico(tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.keys import Key, Mode

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "r9_0.9.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["initialkey"] = ["8A"]
    arquivo.save()

    servico = _servico(config)

    linha = next(
        linha
        for linha in viewmodel.library_state(servico).rows
        if linha.filename.endswith(".flac")
    )
    assert linha.key == Key(9, Mode.MINOR)


def test_track_row_sem_key_fica_none(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    assert viewmodel.library_state(servico).rows[0].key is None


def test_row_da_fila_tambem_traz_a_key(tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.keys import Key, Mode

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.7.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["initialkey"] = ["5A"]
    arquivo.save()

    servico = _servico(config)
    servico.train()

    estado = viewmodel.review_state(servico)
    assert estado.current is not None
    assert estado.current.key == Key(0, Mode.MINOR)
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_viewmodel.py -v -k key`
Expected: FAIL com `AttributeError: 'TrackRow' object has no attribute 'key'`

- [ ] **Step 3: Acrescentar o campo**

Em `src/trackclassifier/ui/viewmodel.py`, o import (dominio puro, nao viola a regra de Qt):

```python
from ..keys import Key
```

E o campo ao final da dataclass `TrackRow`:

```python
    #: Tonalidade canonica lida da tag. None quando a track nao tem key na
    #: tag -- a maioria de um acervo de promos. Guardada como Key (pitch +
    #: modo), nunca como string formatada: e o que permite o alternador de
    #: notacao Camelot/classica trocar a exibicao sem reler nada.
    key: Key | None = None
```

- [ ] **Step 4: Preencher nos dois construtores**

Em `_row_da_fila`, acrescente ao `TrackRow(...)`:

```python
        key=service.key_for(item.sha1),
```

E dentro do laco de `library_state`, ao `TrackRow(...)`:

```python
                key=service.key_for(ref.sha1),
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
git commit -m "feat(ui): TrackRow carrega a tonalidade"
```

---

### Task 5: `camelot_color` no gerador de tokens e o `KeyChip`

**Files:**
- Modify: `design/build_tokens.py`
- Modify: `src/trackclassifier/ui/tokens.py` (**GERADO** — sai do comando, nao editado a mao)
- Create: `src/trackclassifier/ui/widgets/key_chip.py`
- Create: `tests/test_key_chip.py`

**Interfaces:**
- Consumes: `Key`, `KeyNotation`, `format_key` da Task 1.
- Produces:
  - `tokens.camelot_color(number: int) -> str`
  - `KeyChip(QWidget)` com `set_key(key: Key | None)` e `set_notation(notation: KeyNotation)`

> **Atencao:** `ui/tokens.py` NAO pode ser editado a mao. O teste
> `tests/test_tokens.py::test_arquivos_gerados_estao_em_dia_com_o_json` roda
> `design/build_tokens.py` e compara com o que esta commitado — editar o
> gerado sem passar pelo gerador quebra o teste.

- [ ] **Step 1: Escrever o teste do helper de cor**

Acrescente a `tests/test_tokens.py`:

```python
def test_camelot_color_cobre_as_doze_posicoes_da_roda():
    from trackclassifier.ui.tokens import camelot_color

    cores = {camelot_color(n) for n in range(1, 13)}
    # Doze cores distintas: a roda de Camelot perde a utilidade se duas
    # posicoes vizinhas ficarem indistinguiveis.
    assert len(cores) == 12
    assert all(cor.startswith("#") for cor in cores)


def test_camelot_color_fora_da_roda_levanta():
    from trackclassifier.ui.tokens import camelot_color

    import pytest

    for invalido in (0, 13, -1):
        with pytest.raises(KeyError):
            camelot_color(invalido)
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `uv run pytest tests/test_tokens.py -v -k camelot`
Expected: FAIL com `ImportError: cannot import name 'camelot_color'`

- [ ] **Step 3: Emitir o helper no gerador**

Em `design/build_tokens.py`, dentro de `build_py`, ha um bloco `lines += [...]` no fim que ja emite `classification_colors`. Ele termina assim, hoje:

```python
    lines += [
        "",
        "",
        "def classification_colors(label: str) -> tuple[str, str]:",
        '    """Devolve (bg, text) do chip para \'animada\' | \'neutro\' | \'lento\'."""',
        "    table = {",
        '        "animada": (COLOR_CLASSIFICATION_ANIMADA_BG, COLOR_CLASSIFICATION_ANIMADA_TEXT),',
        '        "neutro": (COLOR_CLASSIFICATION_NEUTRO_BG, COLOR_CLASSIFICATION_NEUTRO_TEXT),',
        '        "lento": (COLOR_CLASSIFICATION_LENTO_BG, COLOR_CLASSIFICATION_LENTO_TEXT),',
        "    }",
        "    return table[label.lower()]",
        "",
    ]
```

Substitua esse bloco inteiro (do `lines += [` ate o `]` que o fecha) por este,
que preserva `classification_colors` palavra por palavra e acrescenta
`camelot_color` logo depois:

```python
    lines += [
        "",
        "",
        "def classification_colors(label: str) -> tuple[str, str]:",
        '    """Devolve (bg, text) do chip para \'animada\' | \'neutro\' | \'lento\'."""',
        "    table = {",
        '        "animada": (COLOR_CLASSIFICATION_ANIMADA_BG, COLOR_CLASSIFICATION_ANIMADA_TEXT),',
        '        "neutro": (COLOR_CLASSIFICATION_NEUTRO_BG, COLOR_CLASSIFICATION_NEUTRO_TEXT),',
        '        "lento": (COLOR_CLASSIFICATION_LENTO_BG, COLOR_CLASSIFICATION_LENTO_TEXT),',
        "    }",
        "    return table[label.lower()]",
        "",
        "",
        "def camelot_color(number: int) -> str:",
        '    """Cor da posicao 1-12 na roda de Camelot. Levanta fora da faixa."""',
        "    return {",
    ] + [
        f"        {n}: COLOR_CAMELOT_{n}," for n in range(1, 13)
    ] + [
        "    }[number]",
        "",
    ]
```

> A concatenacao `[...] + [...] + [...]` e proposital: a list comprehension
> do meio gera as 12 linhas `1: COLOR_CAMELOT_1,` ate `12: COLOR_CAMELOT_12,`
> sem repetir cada uma a mao. Cole o bloco inteiro exatamente como esta acima
> — nao tente fazer um diff parcial em cima do bloco antigo, o risco de
> fechar colchete no lugar errado e real. Rode o gerador e leia o
> `tokens.py` resultante antes de commitar.

- [ ] **Step 4: Regerar os tokens**

Run: `uv run python design/build_tokens.py`

Depois **leia** `src/trackclassifier/ui/tokens.py` e confirme que a funcao
nova esta bem formada e que `classification_colors` continua intacta.

- [ ] **Step 5: Rodar o teste do helper**

Run: `uv run pytest tests/test_tokens.py -v`
Expected: PASS, inclusive `test_arquivos_gerados_estao_em_dia_com_o_json`.

- [ ] **Step 6: Escrever os testes do `KeyChip`**

Crie `tests/test_key_chip.py`:

```python
"""O chip de tonalidade. Roda com QT_QPA_PLATFORM=offscreen (conftest)."""

from trackclassifier.keys import Key, KeyNotation, Mode
from trackclassifier.ui.widgets.key_chip import KeyChip


def test_chip_mostra_camelot_por_padrao(qapp):
    chip = KeyChip()
    chip.set_key(Key(9, Mode.MINOR))

    assert chip.text() == "8A"


def test_chip_troca_para_notacao_classica(qapp):
    chip = KeyChip()
    chip.set_key(Key(9, Mode.MINOR))
    chip.set_notation(KeyNotation.CLASSIC)

    assert chip.text() == "Am"


def test_chip_sem_key_mostra_travessao(qapp):
    chip = KeyChip()
    chip.set_key(None)

    assert chip.text() == "—"


def test_trocar_notacao_sem_key_nao_quebra(qapp):
    chip = KeyChip()
    chip.set_notation(KeyNotation.CLASSIC)

    assert chip.text() == "—"


def test_chip_pinta_cores_diferentes_para_posicoes_diferentes_da_roda(qapp):
    # A cor E a informacao: duas keys distantes na roda nao podem sair iguais.
    oito_a = KeyChip()
    oito_a.set_key(Key(9, Mode.MINOR))  # 8A
    dois_a = KeyChip()
    dois_a.set_key(Key(3, Mode.MINOR))  # 2A

    assert oito_a.grab().toImage() != dois_a.grab().toImage()
```

- [ ] **Step 7: Rodar e verificar que falham**

Run: `uv run pytest tests/test_key_chip.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.ui.widgets.key_chip'`

- [ ] **Step 8: Implementar o `KeyChip`**

Crie `src/trackclassifier/ui/widgets/key_chip.py`:

```python
"""Chip da tonalidade, colorido pela roda de Camelot.

A cor nao e decoracao: a posicao na roda e o que diz se duas tracks mixam
bem, entao keys vizinhas tem cores vizinhas e o olho encontra o par antes de
ler o texto.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from ...keys import Key, KeyNotation, format_key
from ..tokens import COLOR_TEXT_INVERSE, RADIUS_SM, SPACE_2, camelot_color


class KeyChip(QLabel):
    """Rotulo com fundo colorido. QLabel e nao QWidget pintado a mao porque
    o texto e o unico conteudo -- QSS resolve o resto."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key: Key | None = None
        self._notation = KeyNotation.CAMELOT
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._repinta()

    def set_key(self, key: Key | None) -> None:
        self._key = key
        self._repinta()

    def set_notation(self, notation: KeyNotation) -> None:
        self._notation = notation
        self._repinta()

    def _repinta(self) -> None:
        self.setText(format_key(self._key, self._notation))
        if self._key is None:
            # Sem key, sem cor: um chip colorido vazio sugeriria que a track
            # tem tonalidade e o app so nao soube formatar.
            self.setStyleSheet("")
            return
        fundo = camelot_color(self._key.camelot_number)
        self.setStyleSheet(
            f"background: {fundo}; color: {COLOR_TEXT_INVERSE}; "
            f"border-radius: {RADIUS_SM}px; padding: 0px {SPACE_2}px;"
        )
```

> O `setStyleSheet` com f-string monta cores vindas de `tokens.py` — nenhum
> hex literal aparece neste arquivo, entao
> `tests/test_tokens.py::test_nenhum_hex_fora_do_json` continua passando.
> Confirme rodando esse teste especificamente.

- [ ] **Step 9: Rodar os testes**

Run: `uv run pytest tests/test_key_chip.py tests/test_tokens.py -v`
Expected: PASS em todos.

- [ ] **Step 10: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add design/build_tokens.py src/trackclassifier/ui/tokens.py \
        src/trackclassifier/ui/widgets/key_chip.py tests/test_key_chip.py tests/test_tokens.py
git commit -m "feat(ui): KeyChip colorido pela roda de Camelot"
```

---

### Task 6: Coluna Key na Biblioteca

**Files:**
- Modify: `src/trackclassifier/ui/widgets/track_model.py`
- Modify: `src/trackclassifier/ui/widgets/delegates.py`
- Modify: `src/trackclassifier/ui/library_tab.py`
- Modify: `tests/test_window.py`
- Modify: `tests/test_delegates.py`

**Interfaces:**
- Consumes: `TrackRow.key` da Task 4; `camelot_color` e `KeyChip` da Task 5.
- Produces:
  - `Column` com `KEY = 5` e os seguintes deslocados: `CLASSIFICACAO = 6`, `CONFIANCA = 7`, `DURACAO = 8`
  - `TrackTableModel.set_notation(notation: KeyNotation)`
  - `KeyDelegate(_DelegateComFundo)`

> **Atencao:** inserir `KEY` no meio do enum desloca os ordinais de tres
> colunas. `library_tab._monta_tabela` percorre `Column` e referencia
> `Column.TITULO`; o teste de cabecalhos em `tests/test_window.py` afirma a
> lista completa. Confira todas as referencias a `Column` depois da mudanca:
> `grep -rn "Column\." src/ tests/`.

- [ ] **Step 1: Atualizar o teste de cabecalhos**

Em `tests/test_window.py`, o teste `test_table_model_expoe_as_colunas_da_fase_2` afirma a lista de cabecalhos (o nome ficou da fase 2, quando a tabela ganhou Titulo/Artista/Genero — a fase 3, que so mexeu na Onda, nao o renomeou). Renomeie para `test_table_model_expoe_as_colunas_da_fase_4` e atualize:

```python
    assert cabecalhos == [
        "Onda",
        "Titulo",
        "Artista",
        "Genero",
        "BPM",
        "Key",
        "Classificacao",
        "Confianca",
        "Duracao",
    ]
```

- [ ] **Step 2: Escrever os testes de conteudo e ordenacao**

Acrescente a `tests/test_window.py`:

```python
def test_coluna_key_ordena_pela_roda_de_camelot_nao_pelo_alfabeto(qapp, tmp_path):
    # 10A vem depois de 2A na roda; alfabeticamente viria antes. Ordenar pela
    # string quebraria a leitura harmonica, que e o proposito da coluna.
    from dataclasses import replace

    from trackclassifier.keys import Key, Mode

    config = _config(tmp_path)
    servico = _servico(config)
    linhas = list(library_state(servico).rows)

    linhas[0] = replace(linhas[0], key=Key(11, Mode.MINOR))  # 10A
    linhas[1] = replace(linhas[1], key=Key(3, Mode.MINOR))   # 2A
    linhas[2] = replace(linhas[2], key=None)

    modelo = TrackTableModel(linhas)
    modelo.sort(Column.KEY, Qt.SortOrder.AscendingOrder)

    numeros = [
        modelo.row_at(i).key.camelot_number if modelo.row_at(i).key else None
        for i in range(modelo.rowCount())
    ]
    assert numeros[0] == 2
    assert numeros[1] == 10
    assert numeros[-1] is None  # sem key sempre no fim


def test_modelo_formata_a_key_na_notacao_corrente(qapp, tmp_path):
    from dataclasses import replace

    from trackclassifier.keys import Key, KeyNotation, Mode

    config = _config(tmp_path)
    servico = _servico(config)
    linhas = list(library_state(servico).rows)
    linhas[0] = replace(linhas[0], key=Key(9, Mode.MINOR))

    modelo = TrackTableModel(linhas)

    assert modelo.data(modelo.index(0, Column.KEY)) == "8A"
    modelo.set_notation(KeyNotation.CLASSIC)
    assert modelo.data(modelo.index(0, Column.KEY)) == "Am"


def test_coluna_key_sem_key_mostra_travessao(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    modelo = TrackTableModel(list(library_state(servico).rows))

    assert modelo.data(modelo.index(0, Column.KEY)) == "—"
```

- [ ] **Step 3: Rodar e verificar que falham**

Run: `uv run pytest tests/test_window.py -v -k key or fase_4`
Expected: FAIL com `AttributeError: KEY`

- [ ] **Step 4: Atualizar o enum e os mapas**

Em `src/trackclassifier/ui/widgets/track_model.py`:

```python
class Column(IntEnum):
    WAVEFORM = 0
    TITULO = 1
    ARTISTA = 2
    GENERO = 3
    BPM = 4
    KEY = 5
    CLASSIFICACAO = 6
    CONFIANCA = 7
    DURACAO = 8
```

```python
_HEADERS: dict[Column, str] = {
    Column.WAVEFORM: "Onda",
    Column.TITULO: "Titulo",
    Column.ARTISTA: "Artista",
    Column.GENERO: "Genero",
    Column.BPM: "BPM",
    Column.KEY: "Key",
    Column.CLASSIFICACAO: "Classificacao",
    Column.CONFIANCA: "Confianca",
    Column.DURACAO: "Duracao",
}

_WIDTHS: dict[Column, int] = {
    Column.WAVEFORM: 150,
    Column.TITULO: 280,
    Column.ARTISTA: 180,
    Column.GENERO: 120,
    Column.BPM: 60,
    Column.KEY: 70,
    Column.CLASSIFICACAO: 110,
    Column.CONFIANCA: 90,
    Column.DURACAO: 70,
}
```

- [ ] **Step 5: Guardar a notacao no modelo**

Ainda em `track_model.py`, acrescente o import:

```python
from ...keys import KeyNotation, format_key
```

No `__init__` de `TrackTableModel`, apos `self._rows`:

```python
        #: Notacao corrente da coluna Key. O modelo formata; a Key guardada
        #: em TrackRow continua canonica, entao trocar de notacao e so
        #: repintar -- nada e relido nem reconvertido.
        self._notation = KeyNotation.CAMELOT
```

E o metodo, junto de `set_rows`:

```python
    def set_notation(self, notation: KeyNotation) -> None:
        if notation is self._notation:
            return
        self._notation = notation
        # A coluna inteira muda de texto sem que nenhuma linha mude de dado:
        # dataChanged so na coluna Key evita o reset de modelo, que perderia
        # a selecao (o mesmo problema que a fase 3 corrigiu no computo de
        # peaks).
        if self._rows:
            self.dataChanged.emit(
                self.index(0, Column.KEY),
                self.index(len(self._rows) - 1, Column.KEY),
                [Qt.ItemDataRole.DisplayRole],
            )
```

- [ ] **Step 6: Formatar e ordenar**

Em `data()`, no bloco de `DisplayRole`, acrescente antes do `return None` final:

```python
        if coluna is Column.KEY:
            return format_key(linha.key, self._notation)
```

E no `TextAlignmentRole`, acrescente `Column.KEY` ao grupo centralizado (junto de `Column.CLASSIFICACAO`), porque o chip e centrado na celula:

```python
            if coluna in (Column.CLASSIFICACAO, Column.KEY):
                return _CENTER
```

Em `_sort_key`, acrescente o ramo:

```python
    if column is Column.KEY:
        # Pela POSICAO NA RODA, nao pela string: "10A" < "2A" no alfabeto, o
        # que embaralharia justamente a leitura harmonica que a coluna serve.
        return lambda linha: (
            linha.key is None,
            linha.key.camelot_number if linha.key else 0,
            linha.key.mode.value if linha.key else "",
        )
```

- [ ] **Step 7: Escrever o teste do delegate**

Acrescente a `tests/test_delegates.py`:

```python
def test_delegate_de_key_pinta_o_fundo_de_selecao(qapp, tmp_path):
    from trackclassifier.ui.widgets.delegates import KeyDelegate

    modelo = _modelo(tmp_path)
    index = modelo.index(0, Column.KEY)
    delegate = KeyDelegate()

    assert _pinta(delegate, index, False) != _pinta(delegate, index, True)


def test_delegate_de_key_pinta_chips_diferentes_para_keys_diferentes(qapp, tmp_path):
    from dataclasses import replace

    from trackclassifier.keys import Key, Mode
    from trackclassifier.ui.widgets.delegates import KeyDelegate

    modelo = _modelo(tmp_path)
    linha = modelo.row_at(0)

    modelo.set_rows([replace(linha, key=Key(9, Mode.MINOR))])
    oito_a = _pinta(KeyDelegate(), modelo.index(0, Column.KEY), False)

    modelo.set_rows([replace(linha, key=Key(3, Mode.MINOR))])
    dois_a = _pinta(KeyDelegate(), modelo.index(0, Column.KEY), False)

    assert oito_a != dois_a


def test_delegate_de_key_sem_key_nao_quebra(qapp, tmp_path):
    from trackclassifier.ui.widgets.delegates import KeyDelegate

    modelo = _modelo(tmp_path)
    assert modelo.row_at(0).key is None

    imagem = _pinta(KeyDelegate(), modelo.index(0, Column.KEY), False)

    assert not imagem.isNull()
```

- [ ] **Step 8: Implementar o `KeyDelegate`**

Em `src/trackclassifier/ui/widgets/delegates.py`, acrescente `camelot_color` ao import de tokens e `Qt` ja esta importado. Acrescente a classe, apos `ClassificationDelegate`:

```python
class KeyDelegate(_DelegateComFundo):
    """Chip da tonalidade, colorido pela posicao na roda de Camelot.

    O texto vem do DisplayRole (o modelo ja formatou na notacao corrente);
    aqui so se desenha o fundo colorido. Sem key, nao ha chip -- o travessao
    do DisplayRole e desenhado como texto simples, porque um chip cinza
    sugeriria que a track tem tonalidade e o app so nao soube formatar.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius = 4.0
        self._padding_h = 6
        self._padding_v = 3

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        self._pinta_fundo(painter, option, index)

        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None:
            return

        texto = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if not texto:
            return

        metricas = QFontMetrics(option.font)
        largura = metricas.horizontalAdvance(texto) + self._padding_h * 2
        altura = metricas.height() + self._padding_v * 2
        chip = QRect(0, 0, largura, altura)
        chip.moveCenter(option.rect.center())

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if linha.key is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(camelot_color(linha.key.camelot_number)))
            painter.drawRoundedRect(chip, self._radius, self._radius)
            painter.setPen(QColor(COLOR_TEXT_INVERSE))
        else:
            painter.setPen(option.palette.text().color())
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, texto)
        painter.restore()
```

E o import de tokens no topo do arquivo vira:

```python
from ..tokens import (
    COLOR_SURFACE_3,
    COLOR_TEXT_INVERSE,
    SIZE_ART_ROW,
    SIZE_WAVE_BAR,
    camelot_color,
    classification_colors,
)
```

- [ ] **Step 9: Ligar o delegate e corrigir as referencias de coluna**

Em `src/trackclassifier/ui/library_tab.py`, no import:

```python
from .widgets.delegates import (
    ClassificationDelegate,
    KeyDelegate,
    TitleDelegate,
    WaveformDelegate,
)
```

E em `_monta_tabela`, junto dos outros delegates:

```python
        tabela.setItemDelegateForColumn(Column.KEY, KeyDelegate(tabela))
```

Rode `grep -rn "Column\." src/ tests/` e confirme que nenhuma referencia
assume os ordinais antigos.

- [ ] **Step 10: Rodar os testes**

Run: `uv run pytest tests/test_window.py tests/test_delegates.py -v`
Expected: PASS.

- [ ] **Step 11: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 12: Commit**

```bash
git add src/trackclassifier/ui/widgets/track_model.py \
        src/trackclassifier/ui/widgets/delegates.py \
        src/trackclassifier/ui/library_tab.py tests/
git commit -m "feat(ui): coluna Key ordenada pela roda de Camelot"
```

---

### Task 7: Alternador de notacao e `KeyChip` na Revisao

**Files:**
- Modify: `src/trackclassifier/ui/library_tab.py`
- Modify: `src/trackclassifier/ui/review_tab.py`
- Modify: `src/trackclassifier/ui/window.py`
- Modify: `tests/test_window.py`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `KeyChip` da Task 5; `TrackTableModel.set_notation` da Task 6; `KeyNotation` da Task 1.
- Produces:
  - `LibraryTab.notation_changed = Signal(object)` — emite o `KeyNotation` escolhido
  - `ReviewTab.set_notation(notation: KeyNotation)`

> **Decisao registrada:** a notacao e preferencia de sessao, nao persistida.
> Persistir exigiria plumbing de `config.toml` que a spec nao pede, e a spec
> lista "alternador de notacao" sem mencionar persistencia. Reabrir a janela
> volta para Camelot. Registrado em "Fora do escopo" no fim deste plano.

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_window.py`:

```python
def test_alternador_de_notacao_muda_biblioteca_e_revisao_juntas(qapp, tmp_path):
    # A notacao e preferencia global: ver "8A" na tabela e "Am" no cabecalho
    # ao mesmo tempo seria dois modelos mentais para o mesmo dado.
    from dataclasses import replace

    from mutagen.flac import FLAC

    from trackclassifier.keys import Key, Mode
    from trackclassifier.labels import Label

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "r9_0.9.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["initialkey"] = ["8A"]
    arquivo.save()

    sf.write(config.inbox / "nova_0.7.flac", np.zeros(22050, dtype="float32"), 22050,
             format="FLAC")
    entrada = FLAC(config.inbox / "nova_0.7.flac")
    entrada["initialkey"] = ["8A"]
    entrada.save()

    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )

        modelo = janela.library_tab._model
        indice_flac = next(
            i for i in range(modelo.rowCount())
            if modelo.row_at(i).filename.endswith(".flac")
        )
        assert modelo.data(modelo.index(indice_flac, Column.KEY)) == "8A"
        assert janela.review_tab._key_chip.text() == "8A"

        janela.library_tab._notacao.setCurrentText("Classica")

        assert modelo.data(modelo.index(indice_flac, Column.KEY)) == "Am"
        assert janela.review_tab._key_chip.text() == "Am"
    finally:
        janela.close()


def test_revisao_sem_key_mostra_travessao_no_chip(qapp, tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)
    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    assert aba._key_chip.text() == "—"


def test_trocar_notacao_nao_perde_a_selecao_da_biblioteca(qapp, tmp_path):
    # set_notation usa dataChanged, nao reset de modelo: e a mesma licao do
    # computo de peaks na fase 3.
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    janela = MainWindow(servico)
    try:
        _mostra_e_ativa(janela)
        janela.apply_states(
            review_state(servico), library_state(servico), model_state(servico)
        )
        janela.tabs.setCurrentWidget(janela.library_tab)

        tabela = janela.library_tab._table
        tabela.setCurrentIndex(tabela.model().index(2, 0))
        assert tabela.currentIndex().row() == 2

        janela.library_tab._notacao.setCurrentText("Classica")

        assert tabela.currentIndex().row() == 2
    finally:
        janela.close()
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_window.py -v -k notacao or chip`
Expected: FAIL com `AttributeError: 'LibraryTab' object has no attribute '_notacao'`

- [ ] **Step 3: Alternador na Biblioteca**

Em `src/trackclassifier/ui/library_tab.py`, o import:

```python
from ..keys import KeyNotation
```

O sinal, junto dos existentes:

```python
    #: KeyNotation escolhido. object porque Signal nao aceita Enum arbitrario
    #: como tipo declarado.
    notation_changed = Signal(object)
```

No `__init__`, apos o `self._filtro`:

```python
        self._notacao = QComboBox()
        self._notacao.addItems([_CAMELOT, _CLASSICA])
        self._notacao.currentTextChanged.connect(self._muda_notacao)
```

E na barra, apos `barra.addWidget(self._filtro)`:

```python
        barra.addWidget(self._notacao)
```

O handler, junto de `decide_selecionada`:

```python
    def _muda_notacao(self, texto: str) -> None:
        notacao = KeyNotation.CLASSIC if texto == _CLASSICA else KeyNotation.CAMELOT
        self._model.set_notation(notacao)
        self.notation_changed.emit(notacao)
```

E as constantes, no nivel de modulo:

```python
#: Texto do alternador. Nao vem de KeyNotation.value porque aquilo e chave
#: interna ("camelot"/"classic"), nao rotulo de tela.
_CAMELOT = "Camelot"
_CLASSICA = "Classica"
```

- [ ] **Step 4: `KeyChip` no cabecalho da Revisao**

Em `src/trackclassifier/ui/review_tab.py`, os imports:

```python
from ..keys import KeyNotation
from .widgets.key_chip import KeyChip
```

No `__init__`, apos `self._capa`:

```python
        self._key_chip = KeyChip()
```

No layout `topo`, entre os textos e os numeros:

```python
        topo = QHBoxLayout()
        topo.addWidget(self._capa)
        topo.addLayout(textos, 1)
        topo.addWidget(self._key_chip)
        topo.addWidget(self._numeros)
```

Em `_atualiza_exibicao`, no ramo de fila vazia, antes do `return`:

```python
            self._key_chip.set_key(None)
```

E no ramo com track, junto de `self._mostra_capa(atual)`:

```python
        self._key_chip.set_key(atual.key)
```

E o metodo publico, junto de `recebe_peaks`:

```python
    def set_notation(self, notation: KeyNotation) -> None:
        """Recebe a preferencia global vinda do alternador da Biblioteca."""
        self._key_chip.set_notation(notation)
```

- [ ] **Step 5: Ligar na janela**

Em `src/trackclassifier/ui/window.py`, em `_conecta`, junto das outras ligacoes de aba:

```python
        self.library_tab.notation_changed.connect(self.review_tab.set_notation)
```

- [ ] **Step 6: Rodar os testes**

Run: `uv run pytest tests/test_window.py -v`
Expected: PASS.

- [ ] **Step 7: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 8: Documentar em `CLAUDE.md`**

Na secao **Estado em disco**, apos o paragrafo de `presentation.parquet`, acrescente:

```markdown
A tonalidade e guardada em forma **canonica** (`key_pc` 0-11 mais `key_mode`
"A"/"B"), nunca como a string formatada. Gravar `"8A"` inviabilizaria o
alternador Camelot/classica, que so funciona porque `keys.Key` sobrevive ao
round-trip do parquet e e formatada na hora de exibir. `keys.py` e dominio
puro -- sem Qt, sem mutagen, sem librosa -- e por isso `ui/viewmodel.py` pode
importa-lo sem violar a fronteira de tela.

A key vem **da tag**, lida no mesmo passe de apresentacao das outras (~1ms,
sem decodificar audio). Nao ha deteccao por audio: Rekordbox e Mixed In Key
ja gravam a key na maioria dos acervos reais, e uma estimativa propria por
chroma acerta ~60-70% em musica eletronica -- key errada exibida com a mesma
confianca de uma certa e pior que travessao para quem mixa harmonicamente.

Armadilha do `mutagen`, segunda parte: a key mora em tres lugares
incompativeis -- vorbis comment (`initialkey`/`key`) no FLAC/OGG, frame
`TKEY` no ID3 (mp3/aiff/wav), e o atom `----:com.apple.iTunes:initialkey` no
MP4. E `MP4FreeForm` e **subclasse de bytes**, igual ao `MP4Cover`: precisa
de `.decode()`, nao de `.text`. O caminho `easy=True` nao serve aqui -- ele
nao expoe `TKEY` em mp3.
```

- [ ] **Step 9: Commit**

```bash
git add src/trackclassifier/ui/library_tab.py src/trackclassifier/ui/review_tab.py \
        src/trackclassifier/ui/window.py tests/test_window.py CLAUDE.md
git commit -m "feat(ui): alternador de notacao e KeyChip na Revisao"
```

---

## Verificacao final da fase

Depois da Task 7, antes de fechar a branch:

- [ ] `uv run ruff check .` — sem achado.
- [ ] `uv run pytest` — tudo verde.
- [ ] `uv run python design/build_tokens.py` seguido de `git diff --exit-code` — os gerados ja estao em dia.
- [ ] `uv run dj scan` numa pasta real com tracks tagueadas pelo Rekordbox/MIK: confirmar que `presentation.parquet` ganhou `key_pc`/`key_mode` preenchidos.
- [ ] `uv run dj review`: a Biblioteca mostra a coluna Key com chips coloridos, ordenar por Key segue a roda (2A antes de 10A), o alternador troca as duas abas de uma vez, e a Revisao mostra o chip no cabecalho.
- [ ] Selecionar uma linha na Biblioteca, trocar a notacao, e confirmar que a selecao **nao** se perde.

## Fora do escopo desta fase

Registrado para nao virar decisao silenciosa de quem implementa:

- **Deteccao de key por audio** (chroma CQT + Krumhansl-Schmuckler) — ver "Decisao de escopo" no topo. O desenho acomoda se entrar depois.
- **`compatible_keys` / destaque de keys compativeis** — a spec ja lista em Escopo cortado ("feature de montar set, nao de classificar energia"). A funcao nem e portada.
- **Persistir a notacao entre execucoes** — preferencia de sessao; reabrir volta para Camelot.
- **Escrever key de volta na tag** — este projeto so le. Nada aqui modifica o arquivo do usuario.
- **Coluna `Confianca`** continua na tabela, apesar de nao estar na lista de colunas da spec. Foi decisao registrada na fase 2 (as fases sao aditivas; remover seria regressao nao pedida). Esta e a ultima fase, entao a pergunta agora e do usuario: vale abrir separado se ele quiser a tabela exatamente como a spec desenhou.
