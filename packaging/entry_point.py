"""Ponto de entrada do executavel gerado pelo PyInstaller.

Nao usa o `dj = trackclassifier.cli:main` de pyproject.toml porque o
PyInstaller precisa de um script real (nao um console-script instalado) para
analisar como raiz da arvore de imports.
"""

import atexit
import faulthandler
import multiprocessing
import os
import sys
from pathlib import Path

from trackclassifier.cli import main


def _ativa_faulthandler() -> None:
    """Grava o traceback Python de um SIGSEGV, inclusive dentro de um worker.

    Existe por causa do segfault documentado na skill de concorrencia (gufunc
    do numba registrado no dispatcher do numpy, EXC_BAD_ACCESS em
    generic_wrapped_legacy_loop) -- sem isto, a unica evidencia e um .ips do
    sistema sem nenhum frame Python. Mas nao e especifico aquele bug: qualquer
    SIGSEGV futuro, de qualquer causa, tambem passa a deixar traceback.

    Um arquivo por PID: os workers do scan sao spawn, cada um reexecuta este
    arquivo do zero, e um unico arquivo compartilhado teria ate 8 processos
    truncando/escrevendo ao mesmo tempo -- perderia exatamente o traceback do
    worker que crashar sob carga real, que e o unico cenario em que isto
    importa. O arquivo vazio de uma saida normal e apagado no atexit; o que
    sobrar em ~/.trackclassifier/ e sinal de que algo morreu antes de chegar
    la.
    """
    pasta = Path.home() / ".trackclassifier"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"crash-{os.getpid()}.log"
    arquivo = caminho.open("w")
    faulthandler.enable(file=arquivo)

    def _remove_se_vazio() -> None:
        if caminho.stat().st_size == 0:
            caminho.unlink(missing_ok=True)

    atexit.register(_remove_se_vazio)


if __name__ == "__main__":
    # A ordem aqui importa: freeze_support() nunca retorna quando o processo
    # e um worker spawn (chama spawn_main() e sys.exit() por dentro) -- se o
    # faulthandler fosse ativado depois, todo worker ficaria sem instrumento.
    _ativa_faulthandler()

    # Obrigatorio antes de qualquer coisa: o ProcessPoolExecutor do scan cria
    # workers relancando ESTE executavel, e sem freeze_support() cada worker
    # entra no main() normal e cai no argparse com os argumentos internos do
    # multiprocessing ("dj: error: argument comando: invalid choice:
    # 'from multiprocessing.resource_tracker import main;main(12)'"), matando
    # o pool inteiro. Fora do bundle a chamada e um no-op.
    multiprocessing.freeze_support()
    sys.exit(main())
