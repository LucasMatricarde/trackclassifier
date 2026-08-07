"""Guarda gramatical do bug que motivou ui/surface.py.

Qt so pinta o `background` do QSS sozinho para a classe QWidget PURA. Numa
subclasse, a mesma regra fica muda no paint normal ate WA_StyledBackground
ser ligado a mao -- sem isto o card fica com metade do fundo pintado e a
outra metade vazando a cor da janela por tras, um sintoma que so aparece com
o app rodando (um grab() isolado de teste forca esse paint por outro caminho
e esconde o bug). O commit que descobriu isso corrigiu um widget so
(TechDetail) e deixou os irmaos (DecisionBar, GuessBar) quebrados -- este
teste varre TODA subclasse de QWidget em ui/, nao so a que ja foi vista
quebrando, para que o proximo card com fundo proprio nao repita o erro.
"""

import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UI = RAIZ / "src" / "trackclassifier" / "ui"

_BACKGROUND = re.compile(r"background\s*:", re.IGNORECASE)
#: aplica_superficie() (ui/surface.py) ja liga o atributo por dentro -- um
#: `self.setAttribute(...)` direto tambem conta, e o caso do UpdateBanner,
#: cujo QSS por #objectName nao cabe na assinatura do helper.
_LIGA_O_ATRIBUTO = re.compile(r"WA_StyledBackground|aplica_superficie\(\s*self\b")


def _classes_qwidget(caminho: Path, texto: str):
    arvore = ast.parse(texto, filename=str(caminho))
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef) and any(
            isinstance(base, ast.Name) and base.id == "QWidget" for base in no.bases
        ):
            yield no


def test_subclasse_com_fundo_proprio_liga_wa_styled_background():
    ofensores = []
    for caminho in UI.rglob("*.py"):
        texto = caminho.read_text(encoding="utf-8")
        for classe in _classes_qwidget(caminho, texto):
            trecho = ast.get_source_segment(texto, classe) or ""
            tem_fundo_proprio = "self.setStyleSheet" in trecho and _BACKGROUND.search(trecho)
            if tem_fundo_proprio and not _LIGA_O_ATRIBUTO.search(trecho):
                ofensores.append(f"{caminho.relative_to(RAIZ)}:{classe.name}")

    assert ofensores == [], (
        f"QWidget com fundo proprio sem WA_StyledBackground: {ofensores}. "
        "Sem isto o fundo so pinta por acidente num grab() isolado, nao no "
        "app rodando -- use aplica_superficie() (ui/surface.py)."
    )
