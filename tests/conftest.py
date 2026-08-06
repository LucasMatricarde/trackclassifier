import os

# Precisa acontecer antes de qualquer import de PySide6: o Qt le a variavel
# na criacao do QApplication e o CI nao tem display. Em conftest.py porque
# aqui roda antes da coleta dos modulos de teste.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
