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
