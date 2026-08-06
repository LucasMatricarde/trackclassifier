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
