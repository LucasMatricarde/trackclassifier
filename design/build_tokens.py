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
    # replace("-", "_") por segmento: a v0.2 introduz chaves hifenizadas
    # (surface.selection-bar, size.focus-ring, motion.playhead-fps). Sem
    # normalizar, isto gera "COLOR_SURFACE_SELECTION-BAR", que nao e
    # identificador Python valido -- SyntaxError em tokens.py, o arquivo nem
    # chega a importar. css_name() NAO passa por aqui de proposito: o hifen e
    # a convencao natural de nome CSS/QSS.
    return "_".join(p.upper().replace("-", "_") for p in path)


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
        "def classification_base(label: str) -> str:",
        '    """Cor cheia da classe para \'animada\' | \'neutro\' | \'lento\'.',
        "",
        "    Separada de classification_colors porque o par (bg, text) serve ao",
        "    chip da lista, e o ponto de cor da aba Configuracao precisa do",
        "    matiz cheio -- o bg do chip sobre o fundo do formulario some.",
        '    """',
        "    return {",
        '        "animada": COLOR_CLASSIFICATION_ANIMADA_BASE,',
        '        "neutro": COLOR_CLASSIFICATION_NEUTRO_BASE,',
        '        "lento": COLOR_CLASSIFICATION_LENTO_BASE,',
        "    }[label.lower()]",
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
    """QSS nao tem variaveis, entao expandimos os valores no template.

    font.tracking e font.case NAO saem daqui, apesar do que a spec da v0.2
    supunha: a lista de propriedades suportadas pelo Qt Style Sheets nao tem
    letter-spacing nem text-transform -- escrever as duas no QSS seria
    exatamente o tipo de token que mente sobre existir que a propria v0.2
    marcou como problema em motion.*. As duas familias saem em tokens.py e
    sao aplicadas em codigo (ui/typography.py): letter-spacing por
    QFont.setLetterSpacing e caixa alta por .upper() no texto do widget.
    """
    t = {css_name(p): v for p, v, _ in tokens}
    template = """/* {banner} */

QWidget {{
    background: {surface0};
    color: {textPrimary};
    font-family: {fontSans};
    font-size: {fontSmall};
    font-weight: {weightRegular};
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

/* Cabecalho de secao do formulario. A caixa alta e o tracking vem de
   ui/typography.py -- ver o docstring de build_qss. */
QLabel#SectionHeader {{
    color: {textSecondary};
    font-family: {fontMono};
    font-size: {fontMicro};
}}

/* Micro-label: o rotulo de 10px em caixa alta que aparece em toda tela da
   v0.2 -- nome de card, cabecalho de coluna, contador, legenda. Difere do
   SectionHeader so na cor (muted, nao secondary), que e o que separa o
   rotulo de um card do cabecalho de uma secao do formulario. Sem padding
   de proposito: quem posiciona e o layout de quem usa. A caixa alta e o
   tracking vem de ui/typography.py -- ver o docstring de build_qss. */
QLabel#MicroLabel {{
    color: {textMuted};
    font-family: {fontMono};
    font-size: {fontMicro};
}}

QLabel#Hint {{
    color: {textMuted};
    font-size: {fontCaption};
}}

QLabel#FieldError {{
    color: {stateDanger};
    font-size: {fontCaption};
}}

/* Chip de contagem ao lado do campo: quantas tracks tem mesmo naquela
   pasta. Monocromatico de proposito -- cor pertence ao dado, e o numero
   aqui e chrome de formulario. */
QLabel#Chip {{
    font-family: {fontMono};
    font-size: {fontMicro};
    color: {textMuted};
    background: {surface2};
    border-radius: {radiusXs};
    padding: 1px {space3};
}}
QLabel#Chip[state="danger"] {{
    color: {stateDanger};
    background: transparent;
    border: 1px solid {stateDanger};
}}

/* Card: o destaque do modo "criar a estrutura para mim" no primeiro uso,
   e o agrupador das secoes do formulario. */
QFrame#Card {{
    background: {surface1};
    border: 1px solid {borderDefault};
    border-radius: {radiusLg};
}}
QFrame#Card[accent="true"] {{
    border-color: {accentBase};
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
/* Campo culpado por um erro de validacao. Propriedade dinamica, nao um
   objectName: o mesmo campo alterna entre os dois estados a cada tecla. */
QLineEdit[state="invalid"] {{ border-color: {stateDanger}; }}
QLineEdit[state="invalid"]:focus {{ border-color: {stateDanger}; }}

/* Rotulo de botao fala mono/caixa alta no app inteiro -- a caixa alta e o
   tracking vem de ui/typography.py. Tratamento contorno tambem no primario:
   accent.base e classification.animada.base sao a MESMA cor na v0.2, e um
   bloco laranja solido competiria com os chips de classe e com a barra de
   selecao. */
QPushButton {{
    background: transparent;
    border: 1px solid {borderDefault};
    border-radius: {radiusMd};
    color: {textPrimary};
    font-family: {fontMono};
    font-size: {fontMicro};
    padding: {space3} {space5};
    min-height: {control};
}}
QPushButton:hover {{ background: {surface2}; border-color: {borderStrong}; }}
QPushButton:pressed {{ background: {surface3}; }}
QPushButton:disabled {{ color: {textDisabled}; border-color: {borderSubtle}; }}
/* Acao principal: mais alto e mais folgado nas laterais que o botao neutro,
   nunca mais escuro. O tamanho do rotulo e o mesmo -- o que separa os dois e
   a cor da borda e a area de clique, nao a tipografia. */
QPushButton[variant="primary"] {{
    background: transparent;
    border-color: {accentBase};
    color: {accentBase};
    padding: {space3} {space6};
    min-height: {controlAction};
}}
QPushButton[variant="primary"]:hover {{
    background: {accentBg};
    border-color: {accentHover};
    color: {accentHover};
}}
QPushButton[variant="primary"]:disabled {{
    border-color: {borderSubtle};
    color: {textDisabled};
    background: transparent;
}}
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

/* Cabecalho da tabela em micro-label: 10px mono, muted. A caixa alta vem
   de Column.header e o tracking de ui/typography.py -- o QSS nao tem
   text-transform nem letter-spacing. */
QHeaderView::section {{
    background: {surface0};
    color: {textMuted};
    font-family: {fontMono};
    font-size: {fontMicro};
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

QCheckBox {{
    color: {textPrimary};
    spacing: {space4};
}}
QCheckBox::indicator {{
    width: {space5};
    height: {space5};
    border: 1px solid {borderStrong};
    border-radius: {radiusXs};
    background: {surface2};
}}
QCheckBox::indicator:checked {{
    background: {accentBase};
    border-color: {accentBase};
}}

QSpinBox {{
    background: {surface2};
    border: 1px solid {borderDefault};
    border-radius: {radiusMd};
    color: {textPrimary};
    font-family: {fontMono};
    padding: {space2} {space3};
    min-height: {control};
}}
QSpinBox:focus {{ border-color: {accentBase}; }}
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
        fontMicro=t["--font-size-micro"],
        fontCaption=t["--font-size-caption"],
        fontSmall=t["--font-size-small"],
        weightRegular=t["--font-weight-regular"],
        weightMedium=t["--font-weight-medium"],
        space2=t["--space-2"],
        space3=t["--space-3"],
        space4=t["--space-4"],
        space5=t["--space-5"],
        space6=t["--space-6"],
        space7=t["--space-7"],
        radiusXs=t["--radius-xs"],
        radiusSm=t["--radius-sm"],
        radiusMd=t["--radius-md"],
        radiusLg=t["--radius-lg"],
        # size.control era valor unico na v0.1. O QPushButton generico usa
        # "base" (28); o botao de acao principal (Retreinar, Salvar,
        # Comecar) usa "action" (32). "primary" (36) NAO entra no QSS: e a
        # altura da barra de reproducao, que player_bar.py le direto do
        # Python. Ate esta fase o botao primario herdava aquele 36 por
        # falta de token proprio, e ficava 4px mais alto que o mockup.
        control=t["--size-control-base"],
        controlAction=t["--size-control-action"],
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
