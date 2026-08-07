"""Fonte unica da versao.

Tudo que precisa saber a versao le daqui: o metadado do pacote (via
`dynamic = ["version"]` no pyproject), o CFBundleShortVersionString do
bundle (via packaging/trackclassifier.spec) e a comparacao do updater. O
modulo fica sem import nenhum de proposito -- o spec do PyInstaller importa
este pacote antes de existir ambiente montado, e qualquer import pesado aqui
quebraria o build.
"""

__version__ = "0.2.0"
