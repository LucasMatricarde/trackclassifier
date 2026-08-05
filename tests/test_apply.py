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
