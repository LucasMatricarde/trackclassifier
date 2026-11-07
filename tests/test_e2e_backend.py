"""O backend descartavel dos E2E precisa recusar uma porta ja ocupada (issue #98)."""

import socket

import pytest

from .e2e_backend import main, porta_ocupada


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_porta_ocupada_enxerga_quem_escuta():
    with socket.socket() as servidor:
        servidor.bind(("127.0.0.1", 0))
        servidor.listen()
        assert porta_ocupada(servidor.getsockname()[1]) is True


def test_porta_ocupada_false_com_a_porta_livre():
    assert porta_ocupada(_porta_livre()) is False


def test_main_aborta_antes_de_montar_quando_a_porta_esta_ocupada(tmp_path, monkeypatch):
    with socket.socket() as servidor:
        servidor.bind(("127.0.0.1", 0))
        servidor.listen()
        porta = servidor.getsockname()[1]
        argv = ["e2e_backend", "--dir", str(tmp_path), "--port", str(porta)]
        monkeypatch.setattr("sys.argv", argv)
        with pytest.raises(SystemExit) as saida:
            main()
    assert "ja esta em uso" in str(saida.value)
    # Abortou antes de montar o servico: nada de mp3 nem pastas na raiz.
    assert list(tmp_path.iterdir()) == []
