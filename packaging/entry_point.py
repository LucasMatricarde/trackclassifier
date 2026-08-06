"""Ponto de entrada do executavel gerado pelo PyInstaller.

Nao usa o `dj = trackclassifier.cli:main` de pyproject.toml porque o
PyInstaller precisa de um script real (nao um console-script instalado) para
analisar como raiz da arvore de imports.
"""

import multiprocessing
import sys

from trackclassifier.cli import main

if __name__ == "__main__":
    # Obrigatorio antes de qualquer coisa: o ProcessPoolExecutor do scan cria
    # workers relancando ESTE executavel, e sem freeze_support() cada worker
    # entra no main() normal e cai no argparse com os argumentos internos do
    # multiprocessing ("dj: error: argument comando: invalid choice:
    # 'from multiprocessing.resource_tracker import main;main(12)'"), matando
    # o pool inteiro. Fora do bundle a chamada e um no-op.
    multiprocessing.freeze_support()
    sys.exit(main())
