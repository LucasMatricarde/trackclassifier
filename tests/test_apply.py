import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor

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


def test_colisao_concorrente_no_mesmo_processo_nao_perde_nem_sobrescreve(tmp_path):
    """Simula requisicoes concorrentes (ex.: /api/decide duplo-clicado, ou
    /api/decide correndo junto de /api/bulk-approve) que resolvem para o
    mesmo nome de destino ao mesmo tempo, em threads do mesmo processo --
    o cenario real do servico web, cujas rotas sincronas o Starlette
    executa num thread pool. Se a reserva do nome de destino nao for
    atomica, duas threads podem concordar no mesmo nome livre e uma
    sobrescreve silenciosamente a outra via shutil.move/os.rename.
    """
    destino_dir = tmp_path / "out"
    destino_dir.mkdir()

    n = 8
    origens = []
    conteudos_esperados = {}
    for i in range(n):
        origem = tmp_path / f"in{i}" / "track.mp3"
        origem.parent.mkdir()
        conteudo = bytes([i]) * 1000
        origem.write_bytes(conteudo)
        origens.append(origem)
        conteudos_esperados[i] = conteudo

    barreira = threading.Barrier(n)

    def mover(origem):
        barreira.wait()
        return move_to_folder(origem, destino_dir)

    with ThreadPoolExecutor(max_workers=n) as pool:
        finais = list(pool.map(mover, origens))

    # nenhuma chamada perdeu nem duplicou o slot de destino
    assert len(finais) == n
    assert len(set(finais)) == n

    nomes = {f.name for f in finais}
    nomes_esperados = {"track.mp3"} | {f"track ({i}).mp3" for i in range(1, n)}
    assert nomes == nomes_esperados

    # nenhum arquivo foi silenciosamente sobrescrito ou perdido no disco
    arquivos_no_destino = list(destino_dir.iterdir())
    assert len(arquivos_no_destino) == n

    conteudos_no_destino = {f.read_bytes() for f in finais}
    assert conteudos_no_destino == set(conteudos_esperados.values())
