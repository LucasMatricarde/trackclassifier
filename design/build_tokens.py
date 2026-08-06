#!/usr/bin/env python3
"""Gera tokens.py e app.qss a partir de design-tokens.json.

Rode sempre que mexer no JSON:
    uv run python design/build_tokens.py

Plugue no pre-commit para nunca ficarem dessincronizados.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "design-tokens.json"

BANNER = "Gerado por build_tokens.py a partir de design-tokens.json. Nao edite a mao."


def flatten(node, prefix=()):
    """Achata a arvore em [(('color','text','primary'), '#F2F2F5'), ...]."""
    out = []
    for key, val in node.items():
        if key.startswith("$"):
            continue
        path = prefix + (key,)
        if isinstance(val, dict):
            if "value" in val:
                out.append((path, str(val["value"]), val.get("desc")))
            else:
                out.extend(flatten(val, path))
    return out


def css_name(path):
    return "--" + "-".join(p.replace("_", "-") for p in path)


def py_name(path):
    return "_".join(p.upper() for p in path)


def px(value):
    """'12px' -> 12 ; '1.25' -> 1.25 ; devolve None se nao for numerico."""
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)(px|ms)?", value.strip())
    if not m:
        return None
    num = float(m.group(1))
    return int(num) if num.is_integer() else num


def build_py(tokens):
    lines = [
        f'"""{BANNER}"""',
        "",
        "from typing import Final",
        "",
    ]
    section = None
    for path, value, _desc in tokens:
        if path[0] != section:
            primeira_secao = section is None
            section = path[0]
            prefixo = "" if primeira_secao else "\n"
            lines.append(f"{prefixo}# --- {section} ---")
        num = px(value) if path[0] in ("size", "space", "radius", "motion") else None
        if num is not None:
            lines.append(f"{py_name(path)}: Final = {num}")
        else:
            lines.append(f'{py_name(path)}: Final = "{value}"')

    lines += [
        "",
        "",
        "def classification_colors(label: str) -> tuple[str, str]:",
        '    """Devolve (bg, text) do chip para \'animada\' | \'neutro\' | \'lento\'."""',
        "    table = {",
        '        "animada": (COLOR_CLASSIFICATION_ANIMADA_BG, COLOR_CLASSIFICATION_ANIMADA_TEXT),',
        '        "neutro": (COLOR_CLASSIFICATION_NEUTRO_BG, COLOR_CLASSIFICATION_NEUTRO_TEXT),',
        '        "lento": (COLOR_CLASSIFICATION_LENTO_BG, COLOR_CLASSIFICATION_LENTO_TEXT),',
        "    }",
        "    return table[label.lower()]",
        "",
        "",
        "def camelot_color(number: int) -> str:",
        '    """Cor da posicao 1-12 na roda de Camelot. Levanta fora da faixa."""',
        "    return {",
    ] + [
        f"        {n}: COLOR_CAMELOT_{n}," for n in range(1, 13)
    ] + [
        "    }[number]",
        "",
    ]
    return "\n".join(lines)


def build_qss(tokens):
    """QSS nao tem variaveis, entao expandimos os valores no template."""
    t = {css_name(p): v for p, v, _ in tokens}
    template = """/* {banner} */

QWidget {{
    background: {surface0};
    color: {textPrimary};
    font-family: {fontSans};
    font-size: {fontSmall};
}}

QWidget#Sidebar, QWidget#PlayerBar {{
    background: {surface1};
    border: none;
}}

QLabel#SectionLabel {{
    color: {textMuted};
    font-size: {fontCaption};
    padding: {space5} {space4} {space3} {space4};
}}

QLabel#Hint {{
    color: {textMuted};
    font-size: {fontCaption};
}}

QLabel#FieldError {{
    color: {stateDanger};
    font-size: {fontCaption};
}}

QLabel#TrackTitle {{ color: {textPrimary}; font-weight: {weightMedium}; }}
QLabel#TrackArtist {{ color: {textSecondary}; font-size: {fontCaption}; }}
QLabel#Numeric {{ font-family: {fontMono}; color: {textPrimary}; }}
QLabel#KeyChip {{
    font-family: {fontMono};
    color: {accentText};
    background: {accentBg};
    border-radius: {radiusSm};
    padding: 1px {space3};
}}

QLineEdit {{
    background: {surface2};
    border: 1px solid {borderDefault};
    border-radius: {radiusMd};
    padding: {space3} {space4};
    selection-background-color: {accentBase};
    selection-color: {textInverse};
}}
QLineEdit:focus {{ border-color: {accentBase}; }}
QLineEdit::placeholder {{ color: {textMuted}; }}

QPushButton {{
    background: transparent;
    border: 1px solid {borderDefault};
    border-radius: {radiusMd};
    color: {textPrimary};
    padding: {space3} {space5};
    min-height: {control};
}}
QPushButton:hover {{ background: {surface2}; border-color: {borderStrong}; }}
QPushButton:pressed {{ background: {surface3}; }}
QPushButton:disabled {{ color: {textDisabled}; border-color: {borderSubtle}; }}
QPushButton[variant="primary"] {{
    background: {accentBase};
    border-color: {accentBase};
    color: {textInverse};
}}
QPushButton[variant="primary"]:hover {{ background: {accentHover}; }}
QPushButton[variant="ghost"] {{ border-color: transparent; }}
QPushButton[variant="ghost"]:hover {{ background: {surface2}; }}

QTableView, QTreeView, QListView {{
    background: {surface0};
    alternate-background-color: {surface0};
    border: none;
    gridline-color: transparent;
    outline: none;
    selection-background-color: {surface2};
    selection-color: {textPrimary};
}}
QTableView::item {{
    border-bottom: 1px solid {borderSubtle};
    padding: 0px {space4};
}}
QTableView::item:hover {{ background: {surface1}; }}

QHeaderView::section {{
    background: {surface0};
    color: {textMuted};
    font-size: {fontCaption};
    border: none;
    border-bottom: 1px solid {borderDefault};
    padding: {space3} {space4};
}}

QScrollBar:vertical {{
    background: transparent;
    width: {space4};
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {borderStrong};
    border-radius: {radiusXs};
    min-height: {space7};
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{
    background: {surface3};
    color: {textPrimary};
    border: 1px solid {borderDefault};
    border-radius: {radiusSm};
    padding: {space2} {space4};
}}
"""
    return template.format(
        banner=BANNER,
        surface0=t["--color-surface-0"],
        surface1=t["--color-surface-1"],
        surface2=t["--color-surface-2"],
        surface3=t["--color-surface-3"],
        textPrimary=t["--color-text-primary"],
        textSecondary=t["--color-text-secondary"],
        textMuted=t["--color-text-muted"],
        textDisabled=t["--color-text-disabled"],
        textInverse=t["--color-text-inverse"],
        borderSubtle=t["--color-border-subtle"],
        borderDefault=t["--color-border-default"],
        borderStrong=t["--color-border-strong"],
        stateDanger=t["--color-state-danger"],
        accentBase=t["--color-accent-base"],
        accentHover=t["--color-accent-hover"],
        accentBg=t["--color-accent-bg"],
        accentText=t["--color-accent-text"],
        fontSans=t["--font-family-sans"],
        fontMono=t["--font-family-mono"],
        fontCaption=t["--font-size-caption"],
        fontSmall=t["--font-size-small"],
        weightMedium=t["--font-weight-medium"],
        space2=t["--space-2"],
        space3=t["--space-3"],
        space4=t["--space-4"],
        space5=t["--space-5"],
        space7=t["--space-7"],
        radiusXs=t["--radius-xs"],
        radiusSm=t["--radius-sm"],
        radiusMd=t["--radius-md"],
        control=t["--size-control"],
    )


OUT = ROOT.parent / "src" / "trackclassifier" / "ui"


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    tokens = flatten(data)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tokens.py").write_text(build_py(tokens), encoding="utf-8")
    (OUT / "app.qss").write_text(build_qss(tokens), encoding="utf-8")

    print(f"{len(tokens)} tokens -> ui/tokens.py, ui/app.qss")


if __name__ == "__main__":
    main()
