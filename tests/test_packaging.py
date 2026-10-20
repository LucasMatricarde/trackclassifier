"""Coerencia entre a versao do backend e a do shell Electron.

O electron-builder grava a versao de `shell/package.json` no Info.plist do
.app, e `updates.py` compara essa versao com a do release. Se as duas
divergirem, o app empacotado se identifica com um numero que o release nao
publicou -- a checagem de atualizacao passa a mentir em toda abertura.
"""

import json
from pathlib import Path

from trackclassifier import __version__

RAIZ = Path(__file__).resolve().parent.parent


def test_versao_do_shell_acompanha_o_backend():
    pacote = json.loads(
        (RAIZ / "shell" / "package.json").read_text(encoding="utf-8")
    )

    assert pacote["version"] == __version__
