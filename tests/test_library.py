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


def _config_pastas_aninhadas(tmp_path) -> Config:
    """Layout real de usuario: as pastas rotuladas ficam DENTRO da inbox."""
    raiz = tmp_path / "Tracks"
    raiz.mkdir()
    pastas = {}
    for chave, rotulo in (
        ("up", Label.UP),
        ("neutral", Label.NEUTRAL),
        ("down", Label.DOWN),
    ):
        destino = raiz / chave
        destino.mkdir()
        pastas[rotulo] = destino
    data = tmp_path / "data"
    data.mkdir()
    return Config(folders=pastas, inbox=raiz, data_dir=data, retrain_every=10, min_examples=15)


def test_inbox_ignora_arquivos_que_ja_estao_em_pasta_rotulada(tmp_path):
    config = _config_pastas_aninhadas(tmp_path)
    _cria(config.folders[Label.UP] / "ja_classificada.mp3", b"1")
    _cria(config.inbox / "nova.mp3", b"2")

    refs = scan_inbox(config)

    assert [ref.path.name for ref in refs] == ["nova.mp3"]


def test_scan_labeled_nao_e_afetado_por_pastas_aninhadas(tmp_path):
    config = _config_pastas_aninhadas(tmp_path)
    _cria(config.folders[Label.UP] / "a.mp3", b"1")
    _cria(config.inbox / "solta.mp3", b"2")

    refs = scan_labeled(config)

    assert [ref.path.name for ref in refs] == ["a.mp3"]


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


def test_sha1_cache_poda_entrada_de_arquivo_que_sumiu_ao_salvar(tmp_path):
    # Toda decisao move o arquivo pra outra pasta -- a chave (o caminho
    # antigo) fica orfa no cache pra sempre se ninguem podar. save() deve
    # descartar entradas cujo arquivo nao existe mais antes de escrever.
    from trackclassifier import library

    arquivo = tmp_path / "t.wav"
    arquivo.write_bytes(b"vai sumir")
    caminho = tmp_path / "sha1.json"

    cache = library.Sha1Cache(caminho)
    cache.get(arquivo)
    arquivo.unlink()
    cache.save()

    recarregado = library.Sha1Cache(caminho)
    assert len(recarregado) == 0
