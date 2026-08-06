"""Tags e capa. Fixtures sao arquivos de verdade, gravados na hora.

soundfile escreve MP3, FLAC e AIFF, e o mutagen escreve tags neles -- entao
os tres caminhos distintos de capa embutida (Picture do FLAC, APIC do ID3, e
a ausencia total) sao exercitados contra arquivos reais, nao contra mocks.
"""

import subprocess

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


def _m4a_com_capa(tmp_path):
    """Gera um .m4a real via ffmpeg (soundfile nao escreve esse formato) e
    grava tags + capa com mutagen -- MP4Cover e o unico dos tres tipos de
    capa embutida que e subclasse de bytes em vez de ter atributo .data."""
    from mutagen.mp4 import MP4, MP4Cover

    wav = tmp_path / "fonte.wav"
    sf.write(wav, np.zeros(22050, dtype="float32"), 22050)
    caminho = tmp_path / "t.m4a"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav), "-c:a", "aac", str(caminho)],
        check=True,
        capture_output=True,
    )

    arquivo = MP4(caminho)
    arquivo["\xa9nam"] = ["Glue"]
    arquivo["covr"] = [MP4Cover(JPEG_FALSO, imageformat=MP4Cover.FORMAT_JPEG)]
    arquivo.save()
    return caminho


def test_extrai_capa_de_mp4cover_num_m4a(tmp_path):
    # MP4Cover e subclasse de bytes -- o proprio objeto JA E a imagem,
    # diferente de Picture (FLAC) e APIC (ID3) que tem atributo .data. Sem
    # tratar esse caso, extract_cover devolve None para todo .m4a com capa.
    caminho = _m4a_com_capa(tmp_path)

    capa = extract_cover(caminho)

    assert capa is not None
    assert capa.data == JPEG_FALSO
    assert capa.suffix == ".jpg"


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


def test_cache_sobrevive_a_coluna_version_nao_numerica(tmp_path):
    # Um parquet valido, mas com schema estranho (version como string nao
    # numerica) tem que virar cache vazio, igual a um parquet corrompido --
    # nao pode propagar ValueError e derrubar TrackService.__init__.
    import pandas as pd

    from trackclassifier.presentation import PresentationCache

    caminho = tmp_path / "presentation.parquet"
    frame = pd.DataFrame(
        [{"sha1": "abc123", "title": "Glue", "artist": None, "album": None,
          "genre": None, "cover_suffix": None, "version": "abc"}]
    )
    frame.to_parquet(caminho, index=False)

    cache = PresentationCache(caminho, tmp_path / "covers")

    assert len(cache) == 0


def test_save_e_atomico_e_nao_deixa_tmp_para_tras(tmp_path):
    from trackclassifier.presentation import TrackTags

    cache = _cache(tmp_path)
    cache.put("abc123", TrackTags("Glue", None, None, None), None)
    cache.save()

    assert (tmp_path / "presentation.parquet").is_file()
    assert not list(tmp_path.glob("*.tmp"))


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
