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
