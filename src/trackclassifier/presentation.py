"""Dados de apresentacao: tags e capa embutida.

Vive separado de cache.py de proposito. O cache de ML invalida tudo quando
`extractor.name` muda; se titulo e capa morassem la, acrescentar um campo de
apresentacao dispararia re-analise de features da biblioteca inteira (HPSS do
librosa sobre centenas de arquivos). Aqui a versao e propria e barata: bumpar
PRESENTATION_VERSION recalcula so o que este modulo produz.

Nada aqui importa Qt nem librosa.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import mutagen
import numpy as np
import pandas as pd

from .keys import Key, parse_key

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

#: Campos de key em vorbis comment (FLAC/OGG), na ordem de preferencia.
#: initialkey e o que Rekordbox e Mixed In Key escrevem; `key` aparece em
#: exportacoes mais antigas e em quem catalogou a mao.
_CAMPOS_VORBIS_KEY = ("initialkey", "key")

#: Atom freeform do MP4/M4A. O prefixo "----" e a convencao do container
#: para chave custom com namespace.
_ATOM_MP4_KEY = "----:com.apple.iTunes:initialkey"


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
    bruto = getattr(imagem, "data", None)
    if bruto is None and isinstance(imagem, bytes):
        # MP4Cover (mutagen) e subclasse de bytes -- o proprio objeto JA E a
        # imagem, diferente de Picture (FLAC) e APIC (ID3) que tem atributo
        # .data. Sem este fallback, a capa de todo .m4a some em silencio.
        bruto = imagem
    dados = bytes(bruto or b"")
    if sufixo is None or not dados:
        # Mime que o QPixmap pode nao abrir, ou imagem vazia: melhor nao ter
        # capa do que ter um arquivo quebrado em covers/.
        return None

    return Cover(data=dados, suffix=sufixo)


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
            for registro in frame.to_dict(orient="records"):
                if int(registro.get("version", -1)) != PRESENTATION_VERSION:
                    continue
                self._linhas[str(registro["sha1"])] = registro
        except Exception:
            # Mesma contencao de cache.py: parquet truncado por interrupcao,
            # schema de uma versao anterior, ou uma coluna `version` que nao
            # e numerica (int() levanta ValueError) vira cache vazio. Aqui o
            # custo de errar e ainda menor -- reler tags e ~1ms por track.
            self._linhas = {}
            return

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
