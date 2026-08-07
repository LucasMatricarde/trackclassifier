"""Contagem de arquivos para o chip da aba Configuracao. Sem Qt."""

from trackclassifier.ui.counts import (
    NAO_ENCONTRADA,
    conta_tracks,
    contagens,
    resumo_do_data_dir,
    texto_do_chip,
)


def test_conta_tracks_ignora_extensao_nao_suportada(tmp_path):
    (tmp_path / "a.mp3").touch()
    (tmp_path / "b.flac").touch()
    (tmp_path / "leiame.txt").touch()
    (tmp_path / "subpasta").mkdir()

    assert conta_tracks(str(tmp_path)) == 2


def test_conta_tracks_pasta_vazia_e_zero_nao_none(tmp_path):
    assert conta_tracks(str(tmp_path)) == 0


def test_conta_tracks_pasta_inexistente_e_none(tmp_path):
    assert conta_tracks(str(tmp_path / "nao-existe")) is None


def test_resumo_do_data_dir_pasta_inexistente_e_none(tmp_path):
    assert resumo_do_data_dir(str(tmp_path / "nao-existe")) is None


def test_resumo_do_data_dir_sem_parquet_e_zero_analises(tmp_path):
    analises, bytes_totais = resumo_do_data_dir(str(tmp_path))

    assert analises == 0
    assert bytes_totais == 0


def test_resumo_do_data_dir_soma_bytes_de_qualquer_arquivo(tmp_path):
    (tmp_path / "model.joblib").write_bytes(b"x" * 1000)
    (tmp_path / "covers").mkdir()
    (tmp_path / "covers" / "abc.jpg").write_bytes(b"y" * 500)

    _analises, bytes_totais = resumo_do_data_dir(str(tmp_path))

    assert bytes_totais == 1500


def test_texto_do_chip_campo_vazio_e_vazio():
    assert texto_do_chip("inbox", "") == ""
    assert texto_do_chip("inbox", "   ") == ""


def test_texto_do_chip_inbox_usa_vocabulario_novas(tmp_path):
    (tmp_path / "a.mp3").touch()

    assert texto_do_chip("inbox", str(tmp_path)) == "1 NOVAS"


def test_texto_do_chip_destino_usa_vocabulario_tracks(tmp_path):
    (tmp_path / "a.mp3").touch()
    (tmp_path / "b.mp3").touch()

    assert texto_do_chip("up", str(tmp_path)) == "2 TRACKS"


def test_texto_do_chip_pasta_ausente(tmp_path):
    assert texto_do_chip("up", str(tmp_path / "sumiu")) == NAO_ENCONTRADA


def test_texto_do_chip_data_dir(tmp_path):
    assert texto_do_chip("data_dir", str(tmp_path)) == "0 ANÁLISES · 0 MB"


def test_contagens_uma_entrada_por_chave(tmp_path):
    (tmp_path / "inbox").mkdir()
    (tmp_path / "up").mkdir()

    resultado = contagens(
        {"inbox": str(tmp_path / "inbox"), "up": str(tmp_path / "up"), "root": ""}
    )

    assert resultado == {"inbox": "0 NOVAS", "up": "0 TRACKS", "root": ""}


def test_conta_tracks_nao_calcula_sha1(tmp_path, monkeypatch):
    """A regra da spec: a contagem e barata, nunca le o conteudo do arquivo."""
    import hashlib

    (tmp_path / "a.mp3").write_bytes(b"conteudo")

    chamado = []
    original = hashlib.sha1

    def _sha1_espiao(*args, **kwargs):
        chamado.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(hashlib, "sha1", _sha1_espiao)

    conta_tracks(str(tmp_path))

    assert chamado == []
