# UI desktop fase 2 — tags e capa Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ler titulo, artista, genero e capa embutida de cada track com `mutagen` e exibi-los na aba Revisao e nas colunas da Biblioteca.

**Architecture:** Um cache de apresentacao novo (`presentation.py`), separado do cache de ML, com versao propria — bumpar a versao dele recalcula so apresentacao e nunca dispara re-analise de features. Tags e capa sao lidas durante o scan (custam ~1ms e nao decodificam audio), a capa vai para `covers/<sha1><ext>` em arquivo proprio, e o parquet guarda so texto. A UI consome tudo pelo `viewmodel`, que continua sem importar Qt.

**Tech Stack:** Python 3.11+, `mutagen` (leitura de tags), `pandas`/`pyarrow` (parquet), PySide6-Essentials (widgets, `QPixmap`), pytest.

## Contexto: o que ja existe

Isto e a **fase 2 de 4** da spec `docs/superpowers/specs/2026-08-05-ui-desktop-design.md`. A fase 1 esta entregue e em `main`. O que ja funciona e este plano nao pode quebrar:

- `TrackService` (`service.py`) com `analyze_all(on_progress=..., should_cancel=...) -> bool`, `queue()`, `decide()`, `reclassify()`, `undo_last()`, `failures()`.
- `AnalysisCache` (`cache.py`) — parquet do vetor de ML, chaveado por `(sha1, extractor.name)`. **Este plano nao toca nele.**
- `Sha1Cache` (`library.py`) — sha1 memoizado por `(caminho, mtime, size)`, com `rename(origem, destino)`.
- `ui/viewmodel.py` — dataclasses puras, **nao importa Qt** (ha um teste que falha se importar).
- `ui/worker.py` — uma `QThread` dona do servico.
- `ui/widgets/track_model.py` — `Column(IntEnum)` e `TrackTableModel`.
- `ui/widgets/delegates.py` — `TRACK_ROLE`, `_DelegateComFundo`, `WaveformDelegate`, `ClassificationDelegate`.
- `ui/widgets/waveform_render.py` — `PixmapCache`, LRU generico chaveado por `(sha1, largura, altura)`.
- `ui/tokens.py` — **gerado**, ja contem `SIZE_ART_ROW = 34` e `SIZE_ART_PLAYER = 44`. **Nenhum token novo e necessario nesta fase**, entao `design/build_tokens.py` nao precisa rodar.

## Global Constraints

- **Portugues sem acentos** em tudo que e interno: nomes de variaveis locais, funcoes internas, comentarios, docstrings, mensagens de erro, nomes de teste e texto de UI visivel. `src/` inteiro esta livre de acentos.
- API publica (dataclasses, metodos de classe, campos de parquet, nomes de features) em **ingles**; interior das funcoes em portugues.
- Comentarios explicam **por que**, nao o que — e sao longos quando a decisao nao e obvia (qual excecao, qual race, qual limite).
- ruff: `line-length = 100`, regras `E,F,I,UP,B`. `uv run ruff check .` e gate do CI.
- Commits: conventional commits com escopo (`feat(trackclassifier):`, `fix(ui):`).
- **`ui/viewmodel.py` nao pode importar Qt.** `tests/test_viewmodel.py::test_viewmodel_nao_importa_qt` le o modulo e falha se aparecer `PySide6`.
- **Nenhum hex fora de `design/design-tokens.json`.** Cores vem de `ui/tokens.py`.
- **`ui/tokens.py` e `ui/app.qss` sao gerados** — nunca editar a mao.
- **Nao alterar `FEATURE_NAMES` nem `HandcraftedExtractor.name`.** Qualquer mudanca ali invalida o cache de ML da biblioteca inteira. Esta fase nao tem motivo nenhum para tocar nisso.
- Todo estado em disco fica sob `config.data_dir` (default `.trackclassifier/`, gitignored).
- Escrita de arquivo de estado e **atomica**: grava em `.tmp` no mesmo diretorio e `os.replace`.
- Erros degradam e sao reportados, nunca derrubam o comando.
- Python `>=3.11,<3.14`.

## Fatos verificados sobre o mutagen

Estes foram **testados neste repositorio** antes de escrever o plano. Nao sao suposicoes; confie neles.

1. `mutagen.File(caminho, easy=True)` normaliza `title` / `artist` / `album` / `genre` entre MP3, FLAC, AIFF, OGG, WAV e M4A. O acesso e `objeto.get("title")` e devolve **uma lista** (`["Glue"]`) ou `None`.
2. **`mutagen.File(...)` devolve um objeto FALSY quando o arquivo nao tem tags.** `bool(FLAC_sem_tags)` e `False`. Testar com `if arquivo:` e um bug — descarta silenciosamente todo arquivo sem tag. **Sempre `is None`.**
3. `mutagen.File(...)` devolve `None` de verdade so quando nao reconhece o formato.
4. A capa embutida tem tres formas distintas, e nao ha API unificada:
   - FLAC: atributo `.pictures`, lista de `mutagen.flac.Picture` com `.type`, `.mime`, `.data`.
   - ID3 (MP3, AIFF, WAV): `arquivo.tags.getall("APIC")`, com `.type`, `.mime`, `.data`.
   - MP4/M4A: `arquivo.tags["covr"]`, lista de `MP4Cover` com `.imageformat`.
   - Ogg Vorbis: nao tem nenhum dos tres; a capa vive em `metadata_block_picture` (base64). **Fora do escopo desta fase** — Ogg simplesmente fica sem capa, e isso e aceitavel porque nenhum dos formatos que o usuario usa na pratica (mp3/flac/aiff) depende disso.
   - `type == 3` e COVER_FRONT. Quando ha varias imagens, e essa que interessa.
5. `arquivo.tags` e `None` num arquivo sem tags (WAV, MP3, AIFF recem-criados). `getall` nao existe em `None`.
6. `soundfile` **escreve** MP3, FLAC, AIFF, OGG e WAV. Os testes conseguem gerar fixtures reais para os tres caminhos de capa que importam.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/trackclassifier/presentation.py` | **NOVO.** Leitura de tags e capa (`read_tags`, `extract_cover`) e o cache de apresentacao (`PresentationCache`). Sem Qt, sem librosa. |
| `src/trackclassifier/service.py` | Modificar: passa de apresentacao dentro de `analyze_all`, e `presentation_for(sha1)`. |
| `src/trackclassifier/ui/viewmodel.py` | Modificar: `TrackRow` ganha `title`/`artist`/`genre`/`cover_path` e a propriedade `display_title`. |
| `src/trackclassifier/ui/widgets/track_model.py` | Modificar: colunas `TITULO`/`ARTISTA`/`GENERO` no lugar de `ARQUIVO`. |
| `src/trackclassifier/ui/widgets/delegates.py` | Modificar: `TitleDelegate` novo, pinta miniatura da capa + titulo. |
| `src/trackclassifier/ui/library_tab.py` | Modificar: busca cobre titulo e artista, nao so nome de arquivo. |
| `src/trackclassifier/ui/review_tab.py` | Modificar: cabecalho com capa 44px + titulo · artista · genero. |
| `pyproject.toml` | Modificar: dependencia `mutagen`. |
| `CLAUDE.md` | Modificar: documentar o cache de apresentacao e sua regra de versao. |
| `tests/test_presentation.py` | **NOVO.** Tags, capa nos tres formatos, cache. |

### Decisao de escopo: quais colunas a Biblioteca tem no fim desta fase

A spec lista a tabela alvo como `Onda | Titulo | Artista | Genero | BPM | Key | Classificacao | Duracao`. Duas diferencas em relacao ao que existe hoje, e o tratamento de cada uma:

- **`Arquivo` sai, `Titulo` entra no lugar.** Nada se perde: `display_title` cai para o nome do arquivo quando nao ha tag, entao uma track sem metadado continua identificavel exatamente como hoje.
- **`Confianca` fica, apesar de nao estar na lista da spec.** A spec diz que as fases 2 a 4 sao *aditivas*; remover uma coluna util que ja funciona seria uma regressao que a fase 2 nao foi encarregada de fazer. Quem executar a fase 4 (que traz `Key`) deve levantar essa pergunta ao usuario, nao decidir sozinho.
- **`Key` nao entra** — e fase 4.

## Ordem das tarefas

Tarefas 1 e 2 sao backend puro e testaveis sem Qt. A 3 liga no scan. A 4 e a fronteira. As 5-7 sao UI e dependem da 4.

---

### Task 1: Leitura de tags e capa com mutagen

**Files:**
- Create: `src/trackclassifier/presentation.py`
- Create: `tests/test_presentation.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nada de tarefas anteriores.
- Produces:
  - `TrackTags` — dataclass congelada com `title: str | None`, `artist: str | None`, `album: str | None`, `genre: str | None`
  - `read_tags(path: Path) -> TrackTags`
  - `Cover` — dataclass congelada com `data: bytes` e `suffix: str` (`".jpg"` ou `".png"`)
  - `extract_cover(path: Path) -> Cover | None`

- [ ] **Step 1: Adicionar a dependencia**

```bash
uv add mutagen
```

Confirme que `pyproject.toml` ganhou `"mutagen>=1.47"` (ou versao maior) na lista `dependencies`, e nao em `optional-dependencies`. Ela e obrigatoria: o scan le tags sempre.

- [ ] **Step 2: Escrever os testes de leitura de tags**

Crie `tests/test_presentation.py`:

```python
"""Tags e capa. Fixtures sao arquivos de verdade, gravados na hora.

soundfile escreve MP3, FLAC e AIFF, e o mutagen escreve tags neles -- entao
os tres caminhos distintos de capa embutida (Picture do FLAC, APIC do ID3, e
a ausencia total) sao exercitados contra arquivos reais, nao contra mocks.
"""

import numpy as np
import soundfile as sf

from trackclassifier.presentation import extract_cover, read_tags

JPEG_FALSO = b"\xff\xd8\xff\xe0" + b"conteudo que nao e um jpeg de verdade"
PNG_FALSO = b"\x89PNG\r\n\x1a\n" + b"idem"


def _flac_com_tags(tmp_path, **campos):
    from mutagen.flac import FLAC

    caminho = tmp_path / "t.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    for chave, valor in campos.items():
        arquivo[chave] = [valor]
    arquivo.save()
    return caminho


def _sem_tags(tmp_path, nome="limpo.wav"):
    caminho = tmp_path / nome
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050)
    return caminho


def test_le_os_quatro_campos_de_um_flac(tmp_path):
    caminho = _flac_com_tags(
        tmp_path, title="Glue", artist="Bicep", album="Bicep", genre="Techno"
    )

    tags = read_tags(caminho)

    assert tags.title == "Glue"
    assert tags.artist == "Bicep"
    assert tags.album == "Bicep"
    assert tags.genre == "Techno"


def test_arquivo_sem_tag_nenhuma_devolve_tudo_none(tmp_path):
    # mutagen.File() devolve um objeto FALSY (nao None) para um arquivo sem
    # tags. Uma implementacao que teste `if arquivo:` descarta este caso
    # inteiro em silencio -- e a maioria das tracks de teste cai aqui.
    tags = read_tags(_sem_tags(tmp_path))

    assert tags.title is None
    assert tags.artist is None
    assert tags.album is None
    assert tags.genre is None


def test_tag_parcial_preenche_so_o_que_existe(tmp_path):
    caminho = _flac_com_tags(tmp_path, title="Glue")

    tags = read_tags(caminho)

    assert tags.title == "Glue"
    assert tags.artist is None


def test_arquivo_ilegivel_devolve_tags_vazias_em_vez_de_estourar(tmp_path):
    # Um .mp3 que nao e mp3 nenhum: o scan nao pode morrer por causa disto.
    caminho = tmp_path / "mentira.mp3"
    caminho.write_bytes(b"isto nao e audio")

    tags = read_tags(caminho)

    assert tags.title is None
```

- [ ] **Step 3: Rodar e verificar que falham**

Run: `uv run pytest tests/test_presentation.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'trackclassifier.presentation'`

- [ ] **Step 4: Implementar `read_tags`**

Crie `src/trackclassifier/presentation.py`:

```python
"""Dados de apresentacao: tags e capa embutida.

Vive separado de cache.py de proposito. O cache de ML invalida tudo quando
`extractor.name` muda; se titulo e capa morassem la, acrescentar um campo de
apresentacao dispararia re-analise de features da biblioteca inteira (HPSS do
librosa sobre centenas de arquivos). Aqui a versao e propria e barata: bumpar
PRESENTATION_VERSION recalcula so o que este modulo produz.

Nada aqui importa Qt nem librosa.
"""

from dataclasses import dataclass
from pathlib import Path

import mutagen

#: Formato jpeg/png -> sufixo de arquivo. Serve so para nomear o arquivo da
#: capa com a extensao honesta; o Qt identifica a imagem pelo conteudo.
_SUFIXO_POR_MIME = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
}

#: type == 3 e COVER_FRONT no padrao ID3/FLAC. Um arquivo pode trazer contra
#: capa, foto do artista e encarte; e a frontal que interessa.
_COVER_FRONT = 3


@dataclass(frozen=True)
class TrackTags:
    title: str | None
    artist: str | None
    album: str | None
    genre: str | None


VAZIO = TrackTags(title=None, artist=None, album=None, genre=None)


def _primeiro(valor) -> str | None:
    """As tags do mutagen sao listas mesmo quando ha um valor so."""
    if not valor:
        return None
    texto = str(valor[0]).strip()
    return texto or None


def read_tags(path: Path) -> TrackTags:
    """Le titulo/artista/album/genero. Nunca levanta.

    Custa ~1ms e nao decodifica audio -- le so o cabecalho de metadados.
    """
    try:
        arquivo = mutagen.File(Path(path), easy=True)
    except Exception:
        # Arquivo truncado, permissao, formato mentindo na extensao. Uma
        # track sem tag legivel continua perfeitamente classificavel; derrubar
        # o scan por causa de metadado seria trocar o essencial pelo cosmetico.
        return VAZIO

    # `arquivo is None` e "formato nao reconhecido". NAO troque por `if not
    # arquivo`: um FLAC sem tags e um objeto valido e FALSY ao mesmo tempo, e
    # a versao com truthiness descarta todo arquivo sem metadado.
    if arquivo is None:
        return VAZIO

    return TrackTags(
        title=_primeiro(arquivo.get("title")),
        artist=_primeiro(arquivo.get("artist")),
        album=_primeiro(arquivo.get("album")),
        genre=_primeiro(arquivo.get("genre")),
    )
```

- [ ] **Step 5: Rodar os testes de tags**

Run: `uv run pytest tests/test_presentation.py -v`
Expected: PASS nos quatro.

- [ ] **Step 6: Escrever os testes de capa**

Acrescente a `tests/test_presentation.py`:

```python
def test_extrai_capa_frontal_de_um_flac(tmp_path):
    from mutagen.flac import FLAC, Picture

    caminho = _flac_com_tags(tmp_path, title="Glue")
    arquivo = FLAC(caminho)
    imagem = Picture()
    imagem.type = 3  # COVER_FRONT
    imagem.mime = "image/jpeg"
    imagem.data = JPEG_FALSO
    arquivo.add_picture(imagem)
    arquivo.save()

    capa = extract_cover(caminho)

    assert capa is not None
    assert capa.data == JPEG_FALSO
    assert capa.suffix == ".jpg"


def test_extrai_capa_de_id3_apic_num_mp3(tmp_path):
    from mutagen.id3 import APIC, ID3

    caminho = tmp_path / "t.mp3"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="MP3")
    tags = ID3()
    tags.add(APIC(encoding=3, mime="image/png", type=3, desc="", data=PNG_FALSO))
    tags.save(caminho)

    capa = extract_cover(caminho)

    assert capa is not None
    assert capa.data == PNG_FALSO
    assert capa.suffix == ".png"


def test_prefere_a_frontal_quando_ha_varias_imagens(tmp_path):
    from mutagen.flac import FLAC, Picture

    caminho = _flac_com_tags(tmp_path, title="Glue")
    arquivo = FLAC(caminho)
    for tipo, dados in ((4, b"contracapa"), (3, JPEG_FALSO), (8, b"artista")):
        imagem = Picture()
        imagem.type = tipo
        imagem.mime = "image/jpeg"
        imagem.data = dados
        arquivo.add_picture(imagem)
    arquivo.save()

    capa = extract_cover(caminho)

    assert capa is not None
    assert capa.data == JPEG_FALSO


def test_usa_a_primeira_imagem_quando_nenhuma_e_marcada_como_frontal(tmp_path):
    from mutagen.flac import FLAC, Picture

    caminho = _flac_com_tags(tmp_path, title="Glue")
    arquivo = FLAC(caminho)
    imagem = Picture()
    imagem.type = 0  # "other" -- muitos rippers nao marcam o tipo direito
    imagem.mime = "image/jpeg"
    imagem.data = JPEG_FALSO
    arquivo.add_picture(imagem)
    arquivo.save()

    capa = extract_cover(caminho)

    assert capa is not None
    assert capa.data == JPEG_FALSO


def test_arquivo_sem_capa_devolve_none(tmp_path):
    assert extract_cover(_sem_tags(tmp_path)) is None


def test_capa_de_mime_desconhecido_e_ignorada(tmp_path):
    # Guardar um .bmp ou um mime inventado como se fosse jpg poluiria
    # covers/ com arquivo que o QPixmap nao abre.
    from mutagen.flac import FLAC, Picture

    caminho = _flac_com_tags(tmp_path, title="Glue")
    arquivo = FLAC(caminho)
    imagem = Picture()
    imagem.type = 3
    imagem.mime = "image/bmp"
    imagem.data = b"bmp"
    arquivo.add_picture(imagem)
    arquivo.save()

    assert extract_cover(caminho) is None


def test_capa_de_arquivo_ilegivel_devolve_none(tmp_path):
    caminho = tmp_path / "mentira.flac"
    caminho.write_bytes(b"isto nao e audio")

    assert extract_cover(caminho) is None
```

- [ ] **Step 7: Rodar e verificar que falham**

Run: `uv run pytest tests/test_presentation.py -v -k capa or frontal or imagem`
Expected: FAIL com `ImportError: cannot import name 'extract_cover'`

- [ ] **Step 8: Implementar `extract_cover`**

Acrescente a `src/trackclassifier/presentation.py`:

```python
@dataclass(frozen=True)
class Cover:
    data: bytes
    #: ".jpg" ou ".png". So para nomear o arquivo de forma honesta.
    suffix: str


def _melhor(imagens: list) -> object | None:
    """Escolhe a capa frontal; cai para a primeira se nenhuma se declara.

    Muito ripper nao preenche o campo type, entao exigir type == 3 deixaria
    sem capa uma parte grande do acervo real.
    """
    if not imagens:
        return None
    for imagem in imagens:
        if int(getattr(imagem, "type", 0)) == _COVER_FRONT:
            return imagem
    return imagens[0]


def _imagens_embutidas(arquivo) -> list:
    """Junta as tres formas incompativeis de capa embutida numa lista so.

    Nao ha API unificada no mutagen: FLAC expoe .pictures, ID3 (mp3/aiff/wav)
    expoe tags.getall("APIC"), e MP4 guarda em tags["covr"]. Ogg Vorbis usa
    metadata_block_picture em base64 e fica de fora desta fase.
    """
    imagens = list(getattr(arquivo, "pictures", []) or [])
    if imagens:
        return imagens

    tags = getattr(arquivo, "tags", None)
    if tags is None:
        # Arquivo sem bloco de tags nenhum. Nao e erro -- e o caso comum de
        # um wav recem-exportado.
        return []

    if hasattr(tags, "getall"):
        return list(tags.getall("APIC"))

    capas = tags.get("covr") if hasattr(tags, "get") else None
    return list(capas or [])


def _mime_de(imagem) -> str | None:
    """Devolve o mime, normalizando o formato numerico do MP4."""
    mime = getattr(imagem, "mime", None)
    if mime is not None:
        return str(mime).lower()

    # MP4Cover nao tem mime: tem imageformat, um enum onde 13 = JPEG e
    # 14 = PNG (constantes MP4Cover.FORMAT_JPEG / FORMAT_PNG).
    formato = getattr(imagem, "imageformat", None)
    if formato == 13:
        return "image/jpeg"
    if formato == 14:
        return "image/png"
    return None


def extract_cover(path: Path) -> Cover | None:
    """Devolve a capa embutida, ou None. Nunca levanta."""
    try:
        arquivo = mutagen.File(Path(path))
    except Exception:
        return None
    if arquivo is None:
        return None

    imagem = _melhor(_imagens_embutidas(arquivo))
    if imagem is None:
        return None

    sufixo = _SUFIXO_POR_MIME.get(_mime_de(imagem) or "")
    dados = bytes(getattr(imagem, "data", b"") or b"")
    if sufixo is None or not dados:
        # Mime que o QPixmap pode nao abrir, ou imagem vazia: melhor nao ter
        # capa do que ter um arquivo quebrado em covers/.
        return None

    return Cover(data=dados, suffix=sufixo)
```

- [ ] **Step 9: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS. Nenhum teste da fase 1 pode quebrar — nada foi modificado fora do modulo novo.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml uv.lock src/trackclassifier/presentation.py tests/test_presentation.py
git commit -m "feat(trackclassifier): leitura de tags e capa embutida com mutagen"
```

---

### Task 2: Cache de apresentacao em parquet

**Files:**
- Modify: `src/trackclassifier/presentation.py`
- Modify: `tests/test_presentation.py`

**Interfaces:**
- Consumes: `TrackTags`, `Cover`, `read_tags`, `extract_cover` da Task 1.
- Produces:
  - `PRESENTATION_VERSION: int` (valor `1`)
  - `PresentationRecord` — dataclass congelada: `sha1: str`, `title: str | None`, `artist: str | None`, `album: str | None`, `genre: str | None`, `cover_suffix: str | None`
  - `PresentationCache(path: Path, covers_dir: Path)` com:
    - `get(sha1: str) -> PresentationRecord | None`
    - `put(sha1: str, tags: TrackTags, cover: Cover | None) -> None`
    - `cover_path(sha1: str) -> Path | None`
    - `save() -> None`
    - `__len__() -> int`

- [ ] **Step 1: Escrever os testes do cache**

Acrescente a `tests/test_presentation.py`:

```python
def _cache(tmp_path):
    from trackclassifier.presentation import PresentationCache

    return PresentationCache(tmp_path / "presentation.parquet", tmp_path / "covers")


def test_cache_guarda_e_devolve_as_tags(tmp_path):
    from trackclassifier.presentation import TrackTags

    cache = _cache(tmp_path)
    cache.put(
        "abc123",
        TrackTags(title="Glue", artist="Bicep", album="Bicep", genre="Techno"),
        None,
    )

    registro = cache.get("abc123")
    assert registro is not None
    assert registro.title == "Glue"
    assert registro.artist == "Bicep"
    assert registro.genre == "Techno"
    assert registro.cover_suffix is None


def test_cache_sha1_desconhecida_devolve_none(tmp_path):
    assert _cache(tmp_path).get("nunca-visto") is None


def test_cache_grava_a_capa_em_arquivo_proprio(tmp_path):
    from trackclassifier.presentation import Cover, TrackTags

    cache = _cache(tmp_path)
    cache.put("abc123", TrackTags(None, None, None, None), Cover(JPEG_FALSO, ".jpg"))

    caminho = cache.cover_path("abc123")
    assert caminho is not None
    assert caminho.name == "abc123.jpg"
    assert caminho.read_bytes() == JPEG_FALSO


def test_cover_path_e_none_quando_nao_ha_capa(tmp_path):
    from trackclassifier.presentation import TrackTags

    cache = _cache(tmp_path)
    cache.put("abc123", TrackTags(None, None, None, None), None)

    assert cache.cover_path("abc123") is None


def test_cover_path_e_none_quando_o_arquivo_sumiu_do_disco(tmp_path):
    # O registro diz que ha capa, mas alguem limpou covers/ por fora. Devolver
    # um caminho inexistente faria o QPixmap silenciosamente virar um pixmap
    # nulo, e a linha ficaria sem placeholder.
    from trackclassifier.presentation import Cover, TrackTags

    cache = _cache(tmp_path)
    cache.put("abc123", TrackTags(None, None, None, None), Cover(JPEG_FALSO, ".jpg"))
    cache.cover_path("abc123").unlink()

    assert cache.cover_path("abc123") is None


def test_cache_persiste_entre_instancias(tmp_path):
    from trackclassifier.presentation import PresentationCache, TrackTags

    caminho = tmp_path / "presentation.parquet"
    covers = tmp_path / "covers"

    primeiro = PresentationCache(caminho, covers)
    primeiro.put("abc123", TrackTags("Glue", "Bicep", None, None), None)
    primeiro.save()

    segundo = PresentationCache(caminho, covers)
    registro = segundo.get("abc123")
    assert registro is not None
    assert registro.title == "Glue"
    assert registro.artist == "Bicep"


def test_cache_sobrevive_a_parquet_corrompido(tmp_path):
    from trackclassifier.presentation import PresentationCache

    caminho = tmp_path / "presentation.parquet"
    caminho.write_bytes(b"isto nao e um parquet")

    cache = PresentationCache(caminho, tmp_path / "covers")

    assert len(cache) == 0


def test_bump_de_versao_invalida_os_registros_antigos(tmp_path):
    # E o ponto inteiro deste cache existir separado do de ML: recalcular
    # apresentacao nao pode custar re-analise de features.
    from trackclassifier import presentation
    from trackclassifier.presentation import PresentationCache, TrackTags

    caminho = tmp_path / "presentation.parquet"
    covers = tmp_path / "covers"

    primeiro = PresentationCache(caminho, covers)
    primeiro.put("abc123", TrackTags("Glue", None, None, None), None)
    primeiro.save()

    original = presentation.PRESENTATION_VERSION
    presentation.PRESENTATION_VERSION = original + 1
    try:
        segundo = PresentationCache(caminho, covers)
        assert segundo.get("abc123") is None
    finally:
        presentation.PRESENTATION_VERSION = original


def test_save_e_atomico_e_nao_deixa_tmp_para_tras(tmp_path):
    from trackclassifier.presentation import TrackTags

    cache = _cache(tmp_path)
    cache.put("abc123", TrackTags("Glue", None, None, None), None)
    cache.save()

    assert (tmp_path / "presentation.parquet").is_file()
    assert not list(tmp_path.glob("*.tmp"))
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_presentation.py -v -k cache or cover_path or versao or atomico`
Expected: FAIL com `ImportError: cannot import name 'PresentationCache'`

- [ ] **Step 3: Implementar `PresentationCache`**

Acrescente a `src/trackclassifier/presentation.py`. O bloco de imports do topo do arquivo passa a ser exatamente este (ruff `I` reclama de qualquer outra ordem):

```python
import os
from dataclasses import dataclass
from pathlib import Path

import mutagen
import pandas as pd
```

E o corpo:

```python
#: Bumpe quando o CONTEUDO produzido por este modulo mudar (campo novo, regra
#: de extracao diferente). Recalcula so apresentacao -- ~1ms por track, sem
#: decodificar audio -- e nunca toca no cache de ML.
PRESENTATION_VERSION = 1

_COLUNAS = ["sha1", "title", "artist", "album", "genre", "cover_suffix", "version"]


@dataclass(frozen=True)
class PresentationRecord:
    sha1: str
    title: str | None
    artist: str | None
    album: str | None
    genre: str | None
    cover_suffix: str | None


def _ou_none(valor) -> str | None:
    """Parquet devolve NaN para celula vazia; a dataclass quer None."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor)
    return texto or None


class PresentationCache:
    """Tags por sha1 em parquet; capa em arquivo proprio por track.

    A capa fica fora do parquet de proposito: um acervo de centenas de tracks
    com capa embutida viraria um blob de centenas de MB que o pandas leria
    inteiro para a memoria no boot da janela, para exibir as ~20 linhas
    visiveis. Em arquivo, o Qt carrega sob demanda.
    """

    def __init__(self, path: Path, covers_dir: Path):
        self.path = Path(path)
        self.covers_dir = Path(covers_dir)
        self._linhas: dict[str, dict] = {}

        if not self.path.is_file():
            return
        try:
            frame = pd.read_parquet(self.path)
        except Exception:
            # Mesma contencao de cache.py: parquet truncado por interrupcao ou
            # schema de uma versao anterior vira cache vazio. Aqui o custo de
            # errar e ainda menor -- reler tags e ~1ms por track.
            return
        for registro in frame.to_dict(orient="records"):
            if int(registro.get("version", -1)) != PRESENTATION_VERSION:
                continue
            self._linhas[str(registro["sha1"])] = registro

    def __len__(self) -> int:
        return len(self._linhas)

    def get(self, sha1: str) -> PresentationRecord | None:
        registro = self._linhas.get(sha1)
        if registro is None:
            return None
        return PresentationRecord(
            sha1=sha1,
            title=_ou_none(registro.get("title")),
            artist=_ou_none(registro.get("artist")),
            album=_ou_none(registro.get("album")),
            genre=_ou_none(registro.get("genre")),
            cover_suffix=_ou_none(registro.get("cover_suffix")),
        )

    def put(self, sha1: str, tags: TrackTags, cover: Cover | None) -> None:
        sufixo = None
        if cover is not None:
            self.covers_dir.mkdir(parents=True, exist_ok=True)
            destino = self.covers_dir / f"{sha1}{cover.suffix}"
            # Escrita atomica pelo mesmo motivo do parquet: a janela le estes
            # arquivos a qualquer momento, e um jpeg pela metade vira pixmap
            # nulo sem erro nenhum.
            tmp = destino.with_suffix(destino.suffix + ".tmp")
            tmp.write_bytes(cover.data)
            os.replace(tmp, destino)
            sufixo = cover.suffix

        self._linhas[sha1] = {
            "sha1": sha1,
            "title": tags.title,
            "artist": tags.artist,
            "album": tags.album,
            "genre": tags.genre,
            "cover_suffix": sufixo,
            "version": PRESENTATION_VERSION,
        }

    def cover_path(self, sha1: str) -> Path | None:
        registro = self._linhas.get(sha1)
        if registro is None:
            return None
        sufixo = _ou_none(registro.get("cover_suffix"))
        if sufixo is None:
            return None
        caminho = self.covers_dir / f"{sha1}{sufixo}"
        # Confere existencia: covers/ pode ter sido limpo por fora, e devolver
        # um caminho morto faria o QPixmap virar nulo em silencio, sem cair no
        # placeholder.
        return caminho if caminho.is_file() else None

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        frame = pd.DataFrame(list(self._linhas.values()), columns=_COLUNAS)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        frame.to_parquet(tmp, index=False)
        os.replace(tmp, self.path)
```

- [ ] **Step 4: Rodar os testes do cache**

Run: `uv run pytest tests/test_presentation.py -v`
Expected: PASS em todos.

- [ ] **Step 5: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/trackclassifier/presentation.py tests/test_presentation.py
git commit -m "feat(trackclassifier): cache de apresentacao com versao propria"
```

---

### Task 3: Passada de apresentacao dentro do scan

**Files:**
- Modify: `src/trackclassifier/service.py`
- Modify: `tests/test_service.py`

**Interfaces:**
- Consumes: `PresentationCache`, `PresentationRecord`, `read_tags`, `extract_cover`, `PRESENTATION_VERSION` da Task 2.
- Produces:
  - `TrackService.presentation: PresentationCache` (atributo publico)
  - `TrackService.presentation_for(sha1: str) -> PresentationRecord | None`
  - `TrackService.cover_path_for(sha1: str) -> Path | None`

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_service.py`:

```python
def test_scan_preenche_tags_de_quem_ainda_nao_tem(tmp_path):
    from mutagen.flac import FLAC

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.5.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Glue"]
    arquivo["artist"] = ["Bicep"]
    arquivo.save()

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()

    sha1 = servico._inbox[0].sha1
    registro = servico.presentation_for(sha1)
    assert registro is not None
    assert registro.title == "Glue"
    assert registro.artist == "Bicep"


def test_track_sem_tag_fica_com_registro_vazio_e_nao_e_relida(tmp_path):
    # Gravar um registro vazio e o que impede reler as tags do arquivo a cada
    # scan de uma biblioteca inteira sem metadado.
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()

    sha1 = servico._labeled[0].sha1
    registro = servico.presentation_for(sha1)
    assert registro is not None
    assert registro.title is None

    leituras = {"n": 0}
    import trackclassifier.service as modulo

    original = modulo.read_tags

    def _espiao(caminho):
        leituras["n"] += 1
        return original(caminho)

    modulo.read_tags = _espiao
    try:
        servico.analyze_all()
    finally:
        modulo.read_tags = original

    assert leituras["n"] == 0


def test_falha_ao_ler_tag_nao_entra_em_failures(tmp_path):
    # A track continua classificavel sem metadado; poluir a aba Modelo com
    # "erro" por causa de capa faltando esconderia as falhas que importam.
    config = _config(tmp_path)
    _povoa(config, n_por_classe=1)

    import trackclassifier.service as modulo

    original = modulo.read_tags

    def _explode(caminho):
        raise OSError("disco resolveu sumir")

    modulo.read_tags = _explode
    try:
        servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
        servico.analyze_all()
    finally:
        modulo.read_tags = original

    assert servico.failures() == []


def test_cancelar_o_scan_interrompe_tambem_a_passada_de_apresentacao(tmp_path):
    config = _config(tmp_path)
    _povoa(config)

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    # Cache de ML ja quente: o unico trabalho restante e a apresentacao.
    servico.analyze_all()
    servico.presentation._linhas.clear()

    lidas = []
    import trackclassifier.service as modulo

    original = modulo.read_tags

    def _conta(caminho):
        lidas.append(caminho)
        return original(caminho)

    modulo.read_tags = _conta
    try:
        cancelado = servico.analyze_all(should_cancel=lambda: len(lidas) >= 2)
    finally:
        modulo.read_tags = original

    assert cancelado is True
    assert len(lidas) == 2


def test_cover_path_for_devolve_o_arquivo_da_capa(tmp_path):
    from mutagen.flac import FLAC, Picture

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.5.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    imagem = Picture()
    imagem.type = 3
    imagem.mime = "image/jpeg"
    imagem.data = b"\xff\xd8\xff\xe0capa"
    arquivo.add_picture(imagem)
    arquivo.save()

    servico = TrackService(config, extractor=ExtratorFalso(), max_workers=1)
    servico.analyze_all()

    sha1 = servico._inbox[0].sha1
    capa = servico.cover_path_for(sha1)
    assert capa is not None
    assert capa.read_bytes() == b"\xff\xd8\xff\xe0capa"
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_service.py -v -k presentation or tags or cover or apresentacao`
Expected: FAIL com `AttributeError: 'TrackService' object has no attribute 'presentation_for'`

- [ ] **Step 3: Importar no `service.py`**

Em `src/trackclassifier/service.py`, junto dos imports existentes:

```python
from .presentation import (
    PresentationCache,
    PresentationRecord,
    extract_cover,
    read_tags,
)
```

> Importe os nomes direto (`read_tags`, nao `presentation.read_tags`). Os testes
> acima trocam `modulo.read_tags` no namespace de `service`, que so funciona com
> o import direto — e e a mesma forma que `tests/test_library.py` ja usa para
> espionar `file_sha1`.

- [ ] **Step 4: Instanciar o cache no `__init__`**

Em `TrackService.__init__`, logo depois da linha que cria `self.sha1_cache`:

```python
        self.presentation = PresentationCache(
            config.data_dir / "presentation.parquet",
            config.data_dir / "covers",
        )
```

- [ ] **Step 5: Chamar a passada dentro de `analyze_all`**

Substitua o corpo de `analyze_all` a partir da linha `aceitos, cancelado = self._analyze(...)`:

```python
        aceitos, cancelado = self._analyze(candidatos, on_progress, should_cancel)
        self._labeled = [ref for ref in aceitos if ref.label is not None]
        self._inbox = [ref for ref in aceitos if ref.label is None]
        self.cache.save()

        if not cancelado:
            cancelado = self._preenche_apresentacao(aceitos, should_cancel)
        self.presentation.save()
        return cancelado
```

- [ ] **Step 6: Implementar `_preenche_apresentacao` e os dois acessores**

Acrescente a `TrackService`, logo depois de `_analyze`:

```python
    def _preenche_apresentacao(
        self, refs: list[TrackRef], should_cancel: CancelCheck | None = None
    ) -> bool:
        """Le tags e capa de quem ainda nao tem registro na versao atual.

        Roda depois da extracao, e sobre TODAS as refs aceitas -- nao so as
        que foram extraidas agora. Os dois caches sao independentes: uma track
        com features em cache pode nao ter apresentacao nenhuma (biblioteca
        analisada antes desta fase existir, ou PRESENTATION_VERSION bumpada).

        Nao emite progresso: ler tags e ~1ms e nao decodifica audio, entao uma
        barra so piscaria. E nao alimenta failures(): uma track sem metadado
        legivel continua classificavel, e poluir a aba Modelo com isso
        esconderia as falhas de analise, que sao as que importam.
        """
        cancelou = should_cancel if should_cancel is not None else (lambda: False)

        for ref in refs:
            if cancelou():
                return True
            if self.presentation.get(ref.sha1) is not None:
                continue
            try:
                tags = read_tags(ref.path)
                capa = extract_cover(ref.path)
            except Exception:
                # read_tags/extract_cover ja contem tudo o que sabem conter;
                # chegar aqui e algo fora deles (o proprio open falhando por
                # permissao, arquivo removido no meio do scan). Grava vazio
                # em vez de deixar a track sem registro: sem isto, ela seria
                # retentada a cada scan, para sempre.
                tags, capa = VAZIO, None
            self.presentation.put(ref.sha1, tags, capa)

        return False

    def presentation_for(self, sha1: str) -> PresentationRecord | None:
        return self.presentation.get(sha1)

    def cover_path_for(self, sha1: str) -> Path | None:
        return self.presentation.cover_path(sha1)
```

Acrescente `VAZIO` ao import de `presentation` feito no Step 3:

```python
from .presentation import (
    VAZIO,
    PresentationCache,
    PresentationRecord,
    extract_cover,
    read_tags,
)
```

- [ ] **Step 7: Rodar os testes**

Run: `uv run pytest tests/test_service.py -v`
Expected: PASS. Os testes de cancelamento da fase 1 tambem precisam continuar passando — `_preenche_apresentacao` so roda quando `_analyze` **nao** cancelou.

- [ ] **Step 8: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/trackclassifier/service.py tests/test_service.py
git commit -m "feat(trackclassifier): le tags e capa durante o scan"
```

---

### Task 4: `TrackRow` ganha os campos de apresentacao

**Files:**
- Modify: `src/trackclassifier/ui/viewmodel.py`
- Modify: `tests/test_viewmodel.py`

**Interfaces:**
- Consumes: `TrackService.presentation_for(sha1)` e `cover_path_for(sha1)` da Task 3.
- Produces: `TrackRow` com quatro campos novos e uma propriedade:
  - `title: str | None`, `artist: str | None`, `genre: str | None`, `cover_path: str | None`
  - `display_title: str` (propriedade; `title` ou, na falta, `filename`)

> **Atencao:** `TrackRow` e construida em dois lugares de `viewmodel.py` —
> `_row_da_fila` (fila de revisao) e `library_state` (biblioteca). Os dois
> precisam dos campos novos, senao a construcao levanta `TypeError`.

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_viewmodel.py`:

```python
def test_track_row_traz_as_tags_do_servico(tmp_path):
    from mutagen.flac import FLAC

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "r9_0.9.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Glue"]
    arquivo["artist"] = ["Bicep"]
    arquivo["genre"] = ["Techno"]
    arquivo.save()

    servico = _servico(config)

    linha = next(
        linha for linha in viewmodel.library_state(servico).rows if linha.filename.endswith(".flac")
    )
    assert linha.title == "Glue"
    assert linha.artist == "Bicep"
    assert linha.genre == "Techno"


def test_display_title_cai_para_o_nome_do_arquivo_sem_tag(tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    linha = viewmodel.library_state(servico).rows[0]

    assert linha.title is None
    assert linha.display_title == linha.filename


def test_display_title_usa_a_tag_quando_existe(tmp_path):
    from trackclassifier.ui.viewmodel import TrackRow

    linha = TrackRow(
        sha1="abc",
        filename="01 - faixa.flac",
        label=None,
        predicted=None,
        score=None,
        confidence=None,
        bpm=128.0,
        duration_s=300.0,
        energy_curve=(),
        peak_offset_s=0.0,
        path_hint="/tmp/01 - faixa.flac",
        title="Glue",
        artist="Bicep",
        genre="Techno",
        cover_path=None,
    )

    assert linha.display_title == "Glue"


def test_row_da_fila_tambem_traz_as_tags(tmp_path):
    from mutagen.flac import FLAC

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.7.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Opal"]
    arquivo.save()

    servico = _servico(config)
    servico.train()

    estado = viewmodel.review_state(servico)
    assert estado.current is not None
    assert estado.current.title == "Opal"
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_viewmodel.py -v -k tags or display_title`
Expected: FAIL com `TypeError: TrackRow.__init__() got an unexpected keyword argument 'title'`

- [ ] **Step 3: Acrescentar os campos a `TrackRow`**

Em `src/trackclassifier/ui/viewmodel.py`, acrescente ao final da dataclass `TrackRow`, depois de `path_hint`:

```python
    # Tags lidas por presentation.py. Todas opcionais: um acervo de promos e
    # rips costuma vir sem metadado nenhum, e isso nao e um estado de erro.
    title: str | None = None
    artist: str | None = None
    genre: str | None = None
    #: Caminho de covers/<sha1><ext>, ja verificado como existente por
    #: PresentationCache.cover_path. String pelo mesmo motivo de path_hint:
    #: este modulo e a fronteira de dados puros, e Path carrega comportamento
    #: de mais. Quem consome converte.
    cover_path: str | None = None

    @property
    def display_title(self) -> str:
        """O que a tela mostra como titulo.

        Sem tag, o nome do arquivo e a unica identificacao que o usuario tem
        -- e e o que a coluna Arquivo mostrava antes desta fase, entao nada
        se perde ao troca-la por Titulo.
        """
        return self.title or self.filename
```

> Os quatro campos tem default `None` de proposito: e o que permite construir
> uma `TrackRow` em teste sem repetir os campos de apresentacao, e o que evita
> quebrar qualquer construcao existente que este plano nao tenha previsto.

- [ ] **Step 4: Preencher em `_row_da_fila`**

Substitua a funcao `_row_da_fila` por:

```python
def _row_da_fila(item, service: TrackService) -> TrackRow:
    registro = service.presentation_for(item.sha1)
    capa = service.cover_path_for(item.sha1)
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
        path_hint=str(item.path),
        title=registro.title if registro is not None else None,
        artist=registro.artist if registro is not None else None,
        genre=registro.genre if registro is not None else None,
        cover_path=str(capa) if capa is not None else None,
    )
```

E atualize as duas chamadas em `review_state` para passar o servico:

```python
    return ReviewState(
        current=_row_da_fila(fila[0], service),
        upcoming=tuple(_row_da_fila(item, service) for item in fila[1 : 1 + PROXIMAS]),
        low_confidence=service.model.low_confidence_mode,
        remaining=len(fila),
    )
```

- [ ] **Step 5: Preencher em `library_state`**

Dentro do laco de `library_state`, antes de montar a `TrackRow`:

```python
    for ref in service._labeled:
        analise = service._analysis(ref)
        registro = service.presentation_for(ref.sha1)
        capa = service.cover_path_for(ref.sha1)
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
                path_hint=str(ref.path),
                title=registro.title if registro is not None else None,
                artist=registro.artist if registro is not None else None,
                genre=registro.genre if registro is not None else None,
                cover_path=str(capa) if capa is not None else None,
            )
        )
```

- [ ] **Step 6: Rodar os testes**

Run: `uv run pytest tests/test_viewmodel.py -v`
Expected: PASS, inclusive `test_viewmodel_nao_importa_qt` — nada aqui importa Qt.

- [ ] **Step 7: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/trackclassifier/ui/viewmodel.py tests/test_viewmodel.py
git commit -m "feat(ui): TrackRow carrega titulo, artista, genero e capa"
```

---

### Task 5: Colunas Titulo, Artista e Genero na Biblioteca

**Files:**
- Modify: `src/trackclassifier/ui/widgets/track_model.py`
- Modify: `src/trackclassifier/ui/library_tab.py`
- Modify: `tests/test_window.py`
- Modify: `tests/test_delegates.py`

**Interfaces:**
- Consumes: `TrackRow.title` / `.artist` / `.genre` / `.display_title` da Task 4.
- Produces: `Column` com os membros `WAVEFORM=0`, `TITULO=1`, `ARTISTA=2`, `GENERO=3`, `BPM=4`, `CLASSIFICACAO=5`, `CONFIANCA=6`, `DURACAO=7`.

> **Atencao:** `Column.ARQUIVO` deixa de existir. `library_tab._monta_tabela`
> referencia `Column.ARQUIVO` em tres lugares (resize mode, largura, indicador
> de ordenacao) e todos viram `Column.TITULO`.

- [ ] **Step 1: Atualizar o teste de cabecalhos**

Em `tests/test_window.py`, no teste `test_table_model_expoe_as_colunas_da_fase_1`, troque o nome e a lista esperada:

```python
def test_table_model_expoe_as_colunas_da_fase_2(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)

    modelo = TrackTableModel(list(library_state(servico).rows))

    assert modelo.rowCount() == 9
    assert modelo.columnCount() == len(Column)
    cabecalhos = [
        modelo.headerData(coluna, Qt.Orientation.Horizontal) for coluna in Column
    ]
    assert cabecalhos == [
        "Onda",
        "Titulo",
        "Artista",
        "Genero",
        "BPM",
        "Classificacao",
        "Confianca",
        "Duracao",
    ]
```

- [ ] **Step 2: Escrever os testes de conteudo e ordenacao**

Acrescente a `tests/test_window.py`:

```python
def test_coluna_titulo_mostra_a_tag_e_cai_para_o_nome_do_arquivo(qapp, tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.labels import Label

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "r9_0.9.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Glue"]
    arquivo.save()

    servico = _servico(config)
    modelo = TrackTableModel(list(library_state(servico).rows))

    titulos = [
        modelo.data(modelo.index(i, Column.TITULO)) for i in range(modelo.rowCount())
    ]
    assert "Glue" in titulos
    # As nove sem tag continuam identificaveis pelo nome do arquivo.
    assert "r0_0.1.wav" in titulos


def test_coluna_sem_tag_mostra_travessao_em_vez_de_vazio(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    modelo = TrackTableModel(list(library_state(servico).rows))

    assert modelo.data(modelo.index(0, Column.ARTISTA)) == "—"
    assert modelo.data(modelo.index(0, Column.GENERO)) == "—"


def test_ordena_por_artista_com_os_sem_tag_no_fim(qapp, tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.labels import Label

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "r9_0.9.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["artist"] = ["Bicep"]
    arquivo.save()

    servico = _servico(config)
    modelo = TrackTableModel(list(library_state(servico).rows))
    modelo.sort(Column.ARTISTA, Qt.SortOrder.AscendingOrder)

    artistas = [modelo.row_at(i).artist for i in range(modelo.rowCount())]
    assert artistas[0] == "Bicep"
    assert artistas[-1] is None
```

- [ ] **Step 3: Rodar e verificar que falham**

Run: `uv run pytest tests/test_window.py -v -k coluna or fase_2 or artista`
Expected: FAIL com `AttributeError: TITULO` (o membro ainda nao existe no enum).

- [ ] **Step 4: Reescrever o enum e os mapas**

Em `src/trackclassifier/ui/widgets/track_model.py`, substitua a classe `Column` e os dois dicionarios:

```python
class Column(IntEnum):
    WAVEFORM = 0
    TITULO = 1
    ARTISTA = 2
    GENERO = 3
    BPM = 4
    CLASSIFICACAO = 5
    CONFIANCA = 6
    DURACAO = 7

    @property
    def header(self) -> str:
        return _HEADERS[self]

    @property
    def width(self) -> int:
        return _WIDTHS[self]


_HEADERS: dict[Column, str] = {
    Column.WAVEFORM: "Onda",
    Column.TITULO: "Titulo",
    Column.ARTISTA: "Artista",
    Column.GENERO: "Genero",
    Column.BPM: "BPM",
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
    Column.CLASSIFICACAO: 110,
    Column.CONFIANCA: 90,
    Column.DURACAO: 70,
}

#: Mostrado onde nao ha dado. Mesmo travessao que BPM e confianca ja usam --
#: celula vazia parece bug de render, travessao parece ausencia.
SEM_DADO = "—"
```

- [ ] **Step 5: Atualizar `data()`**

No metodo `data`, substitua o bloco de `DisplayRole`:

```python
        if coluna is Column.TITULO:
            return linha.display_title
        if coluna is Column.ARTISTA:
            return linha.artist or SEM_DADO
        if coluna is Column.GENERO:
            return linha.genre or SEM_DADO
        if coluna is Column.BPM:
            return f"{linha.bpm:.0f}" if linha.bpm else SEM_DADO
        if coluna is Column.CONFIANCA:
            return SEM_DADO if linha.confidence is None else f"{linha.confidence:.2f}"
        if coluna is Column.DURACAO:
            return format_duration(linha.duration_s)
        # Onda e classificacao sao pintadas pelos delegates.
        return None
```

E no bloco de `TextAlignmentRole`, a lista de colunas a direita nao muda
(`BPM`, `CONFIANCA`, `DURACAO`); as tres novas caem no `_LEFT` do final.

- [ ] **Step 6: Atualizar `_sort_key`**

Substitua a funcao inteira:

```python
def _sort_key(column: Column):
    """Chave de ordenacao por coluna. None sempre vai para o fim.

    A tupla `(e_none, valor)` e o que empurra os ausentes para o fim em ordem
    crescente: False < True. Numa biblioteca de promos, ordenar por artista
    com metade sem tag e o caso comum, nao a excecao.
    """
    if column is Column.TITULO:
        # display_title nunca e None -- cai para o nome do arquivo.
        return lambda linha: linha.display_title.lower()
    if column is Column.ARTISTA:
        return lambda linha: (linha.artist is None, (linha.artist or "").lower())
    if column is Column.GENERO:
        return lambda linha: (linha.genre is None, (linha.genre or "").lower())
    if column is Column.BPM:
        return lambda linha: (linha.bpm is None, linha.bpm or 0.0)
    if column is Column.CONFIANCA:
        return lambda linha: (linha.confidence is None, linha.confidence or 0.0)
    if column is Column.DURACAO:
        return lambda linha: linha.duration_s
    if column is Column.CLASSIFICACAO:
        rotulo = lambda linha: linha.label or linha.predicted  # noqa: E731
        return lambda linha: (rotulo(linha) is None, rotulo(linha) or "")
    return lambda linha: linha.display_title.lower()
```

- [ ] **Step 7: Trocar `Column.ARQUIVO` por `Column.TITULO` em `library_tab.py`**

Em `_monta_tabela`, tres ocorrencias:

```python
        cabecalho.setSectionResizeMode(Column.TITULO, QHeaderView.ResizeMode.Stretch)
        for coluna in Column:
            if coluna is not Column.TITULO:
                tabela.setColumnWidth(coluna, coluna.width)
```

e

```python
        cabecalho.setSortIndicator(Column.TITULO, Qt.SortOrder.AscendingOrder)
```

- [ ] **Step 8: Corrigir o teste de ordenacao em `tests/test_delegates.py`**

`test_ordenacao_da_tabela_sobrevive_ao_filtro` ordena por `Column.BPM` — o
membro continua existindo, entao o teste passa sem mudanca. Rode para
confirmar:

Run: `uv run pytest tests/test_delegates.py -v`
Expected: PASS.

- [ ] **Step 9: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add src/trackclassifier/ui/widgets/track_model.py src/trackclassifier/ui/library_tab.py tests/
git commit -m "feat(ui): colunas Titulo, Artista e Genero na Biblioteca"
```

---

### Task 6: Busca por titulo e artista, e miniatura da capa

**Files:**
- Modify: `src/trackclassifier/ui/library_tab.py`
- Modify: `src/trackclassifier/ui/widgets/delegates.py`
- Modify: `tests/test_delegates.py`

**Interfaces:**
- Consumes: `Column.TITULO` da Task 5; `TrackRow.cover_path` / `.display_title` da Task 4; `PixmapCache` e `_DelegateComFundo` (ja existem).
- Produces: `TitleDelegate(QStyledItemDelegate)` em `delegates.py`, com `clear_cache()`.

- [ ] **Step 1: Escrever o teste da busca**

Acrescente a `tests/test_delegates.py`:

```python
def test_busca_encontra_por_titulo_e_por_artista(qapp, tmp_path):
    from mutagen.flac import FLAC

    from trackclassifier.labels import Label
    from trackclassifier.ui.library_tab import LibraryTab

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "r9_0.9.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Glue"]
    arquivo["artist"] = ["Bicep"]
    arquivo.save()

    servico = _servico(config)
    aba = LibraryTab()
    aba.set_state(library_state(servico))

    aba._busca.setText("glue")
    assert aba._model.rowCount() == 1

    aba._busca.setText("bicep")
    assert aba._model.rowCount() == 1

    # O nome do arquivo continua valendo: e a unica pista de uma track sem tag.
    # "r0_0.1" e nao "r0_": `_servico` grava r0_0.1 / r0_0.5 / r0_0.9, entao o
    # prefixo curto casaria tres linhas e o assert nao provaria nada.
    aba._busca.setText("r0_0.1")
    assert aba._model.rowCount() == 1
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `uv run pytest tests/test_delegates.py -v -k busca`
Expected: FAIL — `aba._busca.setText("glue")` filtra tudo, porque a busca so
olha `filename`, e o arquivo se chama `r9_0.9.flac`.

- [ ] **Step 3: Ampliar o filtro**

Em `src/trackclassifier/ui/library_tab.py`, substitua o corpo do laco de
`_reaplica_filtros`:

A funcao inteira, ja com o bloco de reordenacao que a fase 1 acrescentou — nao
apague essas quatro linhas finais, elas sao o que impede a tabela de embaralhar
a cada tecla digitada na busca:

```python
    def _reaplica_filtros(self) -> None:
        termo = self._busca.text().strip().lower()
        rotulo = self._filtro.currentText()
        linhas = [
            linha
            for linha in self._todas
            if (rotulo == "Todos" or linha.label == rotulo)
            and (not termo or _casa(linha, termo))
        ]
        self._model.set_rows(linhas)

        # set_rows reseta o modelo, e o QTableView nao reordena sozinho depois
        # de um reset -- mesmo com setSortingEnabled(True), que so liga o
        # cabecalho ao model.sort() quando o INDICADOR muda. Sem isto o
        # indicador continua apontando para a coluna escolhida enquanto as
        # linhas voltam para a ordem de insercao: o usuario ordena por BPM,
        # digita uma letra na busca e a tabela embaralha sem aviso.
        cabecalho = self._table.horizontalHeader()
        self._model.sort(cabecalho.sortIndicatorSection(), cabecalho.sortIndicatorOrder())
```

E acrescente, no nivel de modulo:

```python
def _casa(linha, termo: str) -> bool:
    """Busca em titulo, artista e nome de arquivo.

    O nome do arquivo continua no conjunto mesmo agora que ha tags: numa
    biblioteca de promos, boa parte das tracks nao tem metadado nenhum, e
    tirar o nome do arquivo deixaria justamente essas impossiveis de achar.
    """
    campos = (linha.title, linha.artist, linha.filename)
    return any(campo and termo in campo.lower() for campo in campos)
```

- [ ] **Step 4: Rodar o teste da busca**

Run: `uv run pytest tests/test_delegates.py -v -k busca`
Expected: PASS.

- [ ] **Step 5: Escrever os testes do delegate de titulo**

Acrescente a `tests/test_delegates.py`:

```python
def test_delegate_de_titulo_pinta_o_fundo_de_selecao(qapp, tmp_path):
    from trackclassifier.ui.widgets.delegates import TitleDelegate

    modelo = _modelo(tmp_path)
    index = modelo.index(0, Column.TITULO)
    delegate = TitleDelegate()

    assert _pinta(delegate, index, False) != _pinta(delegate, index, True)


def test_delegate_de_titulo_desenha_algo_mesmo_sem_capa(qapp, tmp_path):
    # Sem capa a linha ganha um placeholder, nao um buraco: uma coluna que
    # oscila entre ter e nao ter miniatura desalinha o texto de linha para
    # linha.
    from PySide6.QtGui import QColor, QImage

    from trackclassifier.ui.widgets.delegates import TitleDelegate

    modelo = _modelo(tmp_path)
    assert modelo.row_at(0).cover_path is None

    index = modelo.index(0, Column.TITULO)
    pintada = _pinta(TitleDelegate(), index, False)

    vazia = QImage(LARGURA, ALTURA, QImage.Format.Format_ARGB32)
    vazia.fill(QColor("#000000"))
    assert pintada != vazia


def _modelo_com_capa(tmp_path):
    """Modelo cuja PRIMEIRA linha tem capa de verdade em disco.

    O `_modelo` comum produz linhas todas sem capa, e um teste de cache sobre
    elas passaria sem provar nada: `_miniatura` sai antes de tocar no disco
    quando `cover_path` e None, entao o contador ficaria em zero dos dois
    lados da comparacao.
    """
    from mutagen.flac import FLAC, Picture

    from trackclassifier.labels import Label

    config = _config(tmp_path)
    caminho = config.folders[Label.UP] / "aaa_0.9.flac"  # "aaa" para ordenar primeiro
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Com capa"]
    imagem = Picture()
    imagem.type = 3
    imagem.mime = "image/jpeg"
    # Um jpeg minimo de verdade: o QPixmap precisa conseguir decodificar,
    # senao _miniatura cai no placeholder e o cache nunca e alimentado.
    imagem.data = _jpeg_minimo()
    arquivo.add_picture(imagem)
    arquivo.save()

    servico = _servico(config)
    linhas = sorted(library_state(servico).rows, key=lambda linha: linha.filename)
    assert linhas[0].cover_path is not None, "fixture nao produziu capa"
    return TrackTableModel(linhas)


def _jpeg_minimo() -> bytes:
    """Gera um JPEG 1x1 valido usando o proprio Qt, sem dependencia nova."""
    from PySide6.QtCore import QBuffer, QByteArray

    imagem = QImage(1, 1, QImage.Format.Format_RGB32)
    imagem.fill(QColor("#4CC2E0"))
    buffer_bytes = QByteArray()
    buffer = QBuffer(buffer_bytes)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    imagem.save(buffer, "JPG")
    buffer.close()
    return bytes(buffer_bytes)


def test_cache_de_capa_evita_reler_o_disco_a_cada_paint(qapp, tmp_path):
    # Rolar a tabela chama paint() dezenas de vezes por segundo. Sem cache,
    # cada uma abriria o jpeg de novo.
    from trackclassifier.ui.widgets.delegates import TitleDelegate

    modelo = _modelo_com_capa(tmp_path)
    index = modelo.index(0, Column.TITULO)
    delegate = TitleDelegate()

    _pinta(delegate, index, False)
    assert delegate._leituras == 1, "a primeira pintura tem que ler o disco"

    _pinta(delegate, index, False)
    _pinta(delegate, index, False)

    assert delegate._leituras == 1


def test_delegate_de_titulo_desenha_a_capa_quando_ela_existe(qapp, tmp_path):
    # Prova que o ramo da miniatura e distinto do ramo do placeholder.
    from trackclassifier.ui.widgets.delegates import TitleDelegate

    com_capa = _modelo_com_capa(tmp_path)
    # Diretorio proprio: _config cria as pastas de rotulo dentro do caminho que
    # recebe (e com mkdir() sem parents=True, entao ele precisa ja existir).
    outro = tmp_path / "outro"
    outro.mkdir()
    sem_capa = _modelo(outro)

    pintada_com = _pinta(TitleDelegate(), com_capa.index(0, Column.TITULO), False)
    pintada_sem = _pinta(TitleDelegate(), sem_capa.index(0, Column.TITULO), False)

    assert pintada_com != pintada_sem
```

- [ ] **Step 6: Rodar e verificar que falham**

Run: `uv run pytest tests/test_delegates.py -v -k titulo or capa`
Expected: FAIL com `ImportError: cannot import name 'TitleDelegate'`

- [ ] **Step 7: Implementar `TitleDelegate`**

Em `src/trackclassifier/ui/widgets/delegates.py`, acrescente ao import de
tokens `SIZE_ART_ROW` e `COLOR_SURFACE_3`:

```python
from ..tokens import COLOR_SURFACE_3, SIZE_ART_ROW, SIZE_WAVE_BAR, classification_colors
```

E a classe, depois de `WaveformDelegate`:

```python
class TitleDelegate(_DelegateComFundo):
    """Miniatura da capa a esquerda, titulo a direita.

    O pixmap e cacheado por (sha1, largura, altura) no mesmo LRU do render da
    onda: paint() roda dezenas de vezes por segundo durante o scroll, e abrir
    o jpeg do disco em cada chamada transforma a rolagem em I/O.

    Sem capa, desenha um retangulo em surface-3 no lugar. Um placeholder de
    largura fixa e o que mantem o texto alinhado entre linhas com e sem capa
    -- deixar o buraco faria o titulo dancar durante o scroll.
    """

    def __init__(self, parent: QWidget | None = None, margin: int = 6) -> None:
        super().__init__(parent)
        self._cache = PixmapCache(capacity=256)
        self._margin = margin
        #: Contador de leituras de disco. Existe para o teste provar que o
        #: cache esta sendo usado; nada na UI depende dele.
        self._leituras = 0

    def _miniatura(self, linha: TrackRow, lado: int) -> QPixmap | None:
        if linha.cover_path is None:
            return None

        chave = (linha.sha1, lado, lado)
        pixmap = self._cache.get(chave)
        if pixmap is not None:
            return pixmap

        self._leituras += 1
        origem = QPixmap(linha.cover_path)
        if origem.isNull():
            # Arquivo corrompido ou formato que o Qt nao abre. Cai no
            # placeholder em vez de deixar a celula sem nada.
            return None

        pixmap = origem.scaled(
            lado,
            lado,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._cache.put(chave, pixmap)
        return pixmap

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        self._pinta_fundo(painter, option, index)

        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None:
            return

        rect = option.rect.adjusted(self._margin, 0, -self._margin, 0)
        lado = min(SIZE_ART_ROW, max(0, rect.height() - self._margin))
        if lado <= 0:
            return

        arte = QRect(rect.left(), rect.top() + (rect.height() - lado) // 2, lado, lado)
        miniatura = self._miniatura(linha, lado)

        painter.save()
        if miniatura is not None:
            painter.drawPixmap(arte, miniatura)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLOR_SURFACE_3))
            painter.drawRoundedRect(arte, 3.0, 3.0)

        texto = QRect(
            arte.right() + self._margin,
            rect.top(),
            max(0, rect.right() - arte.right() - self._margin),
            rect.height(),
        )
        painter.setPen(option.palette.text().color())
        painter.drawText(
            texto,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(option.font).elidedText(
                linha.display_title, Qt.TextElideMode.ElideRight, texto.width()
            ),
        )
        painter.restore()

    def clear_cache(self) -> None:
        self._cache.clear()
```

Acrescente `QPixmap` ao import de `PySide6.QtGui`:

```python
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPixmap
```

- [ ] **Step 8: Ligar o delegate na tabela**

Em `src/trackclassifier/ui/library_tab.py`, em `_monta_tabela`, junto dos
outros delegates:

```python
        self._title_delegate = TitleDelegate(tabela)
        tabela.setItemDelegateForColumn(Column.TITULO, self._title_delegate)
```

E no import:

```python
from .widgets.delegates import ClassificationDelegate, TitleDelegate, WaveformDelegate
```

- [ ] **Step 9: Rodar os testes**

Run: `uv run pytest tests/test_delegates.py -v`
Expected: PASS.

- [ ] **Step 10: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add src/trackclassifier/ui/library_tab.py src/trackclassifier/ui/widgets/delegates.py tests/test_delegates.py
git commit -m "feat(ui): busca por tag e miniatura da capa na Biblioteca"
```

---

### Task 7: Cabecalho da Revisao com capa, titulo, artista e genero

**Files:**
- Modify: `src/trackclassifier/ui/review_tab.py`
- Modify: `tests/test_window.py`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `TrackRow.title` / `.artist` / `.genre` / `.cover_path` / `.display_title` da Task 4.
- Produces: nada consumido por outra tarefa. Esta e a ultima.

- [ ] **Step 1: Escrever os testes**

Acrescente a `tests/test_window.py`:

```python
def test_revisao_mostra_titulo_artista_e_genero(qapp, tmp_path):
    from mutagen.flac import FLAC

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.7.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["title"] = ["Glue"]
    arquivo["artist"] = ["Bicep"]
    arquivo["genre"] = ["Techno"]
    arquivo.save()

    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    assert aba._titulo.text() == "Glue"
    assert "Bicep" in aba._subtitulo.text()
    assert "Techno" in aba._subtitulo.text()


def test_revisao_sem_tag_usa_o_nome_do_arquivo_e_esconde_o_subtitulo(qapp, tmp_path):
    config = _config(tmp_path)
    sf.write(config.inbox / "nova_0.7.wav", np.zeros(100), 22050)

    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    assert aba._titulo.text() == "nova_0.7.wav"
    # Sem artista nem genero, uma linha vazia so consome espaco vertical.
    assert aba._subtitulo.text() == ""


def test_revisao_mostra_so_o_artista_quando_nao_ha_genero(qapp, tmp_path):
    from mutagen.flac import FLAC

    config = _config(tmp_path)
    caminho = config.inbox / "nova_0.7.flac"
    sf.write(caminho, np.zeros(22050, dtype="float32"), 22050, format="FLAC")
    arquivo = FLAC(caminho)
    arquivo["artist"] = ["Bicep"]
    arquivo.save()

    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    # Sem separador solto: " · " sobrando parece dado faltando por bug.
    assert aba._subtitulo.text() == "Bicep"


def test_revisao_limpa_o_cabecalho_na_fila_vazia(qapp, tmp_path):
    config = _config(tmp_path)
    servico = _servico(config)
    servico.train()

    aba = ReviewTab(SimulatedPlayer())
    aba.set_state(review_state(servico))

    assert aba._subtitulo.text() == ""
    assert aba._capa.pixmap().isNull()
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `uv run pytest tests/test_window.py -v -k revisao`
Expected: FAIL com `AttributeError: 'ReviewTab' object has no attribute '_subtitulo'`

- [ ] **Step 3: Criar os widgets do cabecalho**

Em `src/trackclassifier/ui/review_tab.py`, no `__init__`, logo depois de
`self._titulo`:

```python
        self._subtitulo = QLabel("")
        self._subtitulo.setObjectName("SectionLabel")

        self._capa = QLabel()
        self._capa.setFixedSize(SIZE_ART_PLAYER, SIZE_ART_PLAYER)
        self._capa.setScaledContents(True)
```

E acrescente ao import de tokens:

```python
from .tokens import SIZE_ART_PLAYER
```

- [ ] **Step 4: Montar o cabecalho no layout**

Substitua o bloco que monta `topo`:

```python
        # Capa a esquerda, titulo e subtitulo empilhados, numeros a direita.
        textos = QVBoxLayout()
        textos.setSpacing(SPACE_1)
        textos.addWidget(self._titulo)
        textos.addWidget(self._subtitulo)

        topo = QHBoxLayout()
        topo.addWidget(self._capa)
        topo.addLayout(textos, 1)
        topo.addWidget(self._numeros)
```

E acrescente `SPACE_1` ao import de tokens:

```python
from .tokens import SIZE_ART_PLAYER, SPACE_1
```

- [ ] **Step 5: Preencher no `_atualiza_exibicao`**

No ramo de fila vazia (`if atual is None:`), acrescente antes do `return`:

```python
            self._subtitulo.setText("")
            self._capa.clear()
```

E no ramo com track, junto de `self._titulo.setText(...)`, substituindo a
linha existente:

```python
        self._titulo.setText(atual.display_title)
        # Junta so o que existe: com um dos dois ausente, um " · " solto no
        # meio parece dado faltando por bug em vez de tag ausente.
        self._subtitulo.setText(
            " · ".join(parte for parte in (atual.artist, atual.genre) if parte)
        )
        self._mostra_capa(atual)
```

- [ ] **Step 6: Implementar `_mostra_capa`**

Acrescente a `ReviewTab`, depois de `_atualiza_exibicao`:

```python
    def _mostra_capa(self, linha: TrackRow) -> None:
        """Carrega a capa do disco, uma vez por track.

        Sem cache proprio: aqui e uma imagem so, recarregada apenas quando a
        track muda -- diferente da tabela, que pinta dezenas por segundo
        durante o scroll e por isso precisa do PixmapCache.
        """
        if linha.cover_path is None:
            self._capa.clear()
            return

        pixmap = QPixmap(linha.cover_path)
        if pixmap.isNull():
            # Arquivo corrompido ou formato que o Qt nao abre.
            self._capa.clear()
            return
        self._capa.setPixmap(pixmap)
```

E acrescente o import:

```python
from PySide6.QtGui import QPixmap
```

- [ ] **Step 7: Rodar os testes**

Run: `uv run pytest tests/test_window.py -v -k revisao`
Expected: PASS.

- [ ] **Step 8: Rodar a suite inteira**

Run: `uv run ruff check . && uv run pytest`
Expected: PASS.

- [ ] **Step 9: Documentar em `CLAUDE.md`**

Na secao **Estado em disco**, depois do paragrafo do `sha1.json`, acrescente:

```markdown
`presentation.parquet` e `covers/<sha1>.<ext>` sao o cache de **apresentacao**
(`presentation.py`): titulo, artista, album, genero e capa embutida, lidos com
`mutagen` durante o scan. Ele existe separado do cache de ML por um motivo so:
o de ML invalida tudo quando `extractor.name` muda, entao acrescentar um campo
de apresentacao la dispararia re-analise de features da biblioteca inteira.
Aqui a versao e propria — **bumpe `PRESENTATION_VERSION` quando mudar o que
este modulo produz**, e o custo e ~1ms por track, sem decodificar audio. A capa
fica em arquivo por track, nao em coluna de parquet, para o pandas nao carregar
centenas de MB de blob no boot da janela.

Armadilha do `mutagen`: `mutagen.File(...)` devolve um objeto **falsy** para um
arquivo sem tags, e `None` so quando nao reconhece o formato. Teste sempre com
`is None` — `if arquivo:` descarta em silencio toda track sem metadado.
```

- [ ] **Step 10: Commit**

```bash
git add src/trackclassifier/ui/review_tab.py tests/test_window.py CLAUDE.md
git commit -m "feat(ui): cabecalho da Revisao com capa, titulo, artista e genero"
```

---

## Verificacao final da fase

Depois da Task 7, antes de fechar a branch:

- [ ] `uv run ruff check .` — sem achado.
- [ ] `uv run pytest` — tudo verde.
- [ ] `uv run dj scan` numa pasta real com mp3/flac tagueados: confirmar que `presentation.parquet` e `covers/` aparecem em `.trackclassifier/`.
- [ ] `uv run dj review`: a Biblioteca mostra Titulo/Artista/Genero com miniatura, a busca acha por artista, e a Revisao mostra capa e subtitulo.
- [ ] Rodar `dj scan` duas vezes seguidas e confirmar que a segunda nao rele tags (o cache de apresentacao esta sendo consultado).

## Fora do escopo desta fase

Registrado para nao virar decisao silenciosa de quem implementa:

- **Key / Camelot / `KeyChip`** — fase 4. A coluna `Key` da spec nao entra agora.
- **Buckets RGB da waveform** — fase 3.
- **Capa de Ogg Vorbis** (`metadata_block_picture` em base64) — nenhum dos formatos que o usuario usa na pratica depende disso.
- **Escrever tags** — este projeto so le. Nada aqui modifica o arquivo do usuario.
- **Buscar capa na internet** quando nao ha embutida.
- **Coluna `Confianca`** continua na tabela, apesar de nao estar na lista da spec. Ver "Decisao de escopo" acima; quem fizer a fase 4 deve levantar isso com o usuario.
