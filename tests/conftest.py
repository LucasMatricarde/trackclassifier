import os

import pytest

# Precisa acontecer antes de qualquer import de PySide6: o Qt le a variavel
# na criacao do QApplication e o CI nao tem display. Em conftest.py porque
# aqui roda antes da coleta dos modulos de teste.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """QApplication unica para a sessao inteira.

    O Qt aceita apenas uma instancia por processo, e destrui-la entre
    testes deixa widgets orfaos que derrubam a coleta seguinte.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
