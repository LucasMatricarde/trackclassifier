"""Guarda o modo de falha mais provavel do design system: editar o JSON e
esquecer de rodar build_tokens.py, deixando tokens.py e app.qss velhos."""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GERADOS = [
    RAIZ / "src" / "trackclassifier" / "ui" / "tokens.py",
    RAIZ / "src" / "trackclassifier" / "ui" / "app.qss",
]


def test_arquivos_gerados_estao_em_dia_com_o_json():
    antes = {caminho: caminho.read_text(encoding="utf-8") for caminho in GERADOS}

    subprocess.run(
        [sys.executable, str(RAIZ / "design" / "build_tokens.py")],
        check=True,
        capture_output=True,
    )

    for caminho, conteudo in antes.items():
        assert caminho.read_text(encoding="utf-8") == conteudo, (
            f"{caminho.name} esta dessincronizado de design-tokens.json. "
            "Rode: uv run python design/build_tokens.py"
        )


def test_nenhum_hex_fora_do_json():
    """Nenhum literal de cor pode existir fora dos tokens."""
    import re

    padrao = re.compile(r"#[0-9A-Fa-f]{6}\b")
    ui = RAIZ / "src" / "trackclassifier" / "ui"
    permitidos = {ui / "tokens.py", ui / "app.qss"}

    ofensores = []
    for caminho in ui.rglob("*.py"):
        if caminho in permitidos:
            continue
        for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
            if padrao.search(linha):
                ofensores.append(f"{caminho.relative_to(RAIZ)}:{numero}")

    assert ofensores == [], f"hex fora de design-tokens.json: {ofensores}"
