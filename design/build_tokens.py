#!/usr/bin/env python3
"""Gera web/src/styles/tokens.css a partir de design-tokens.json.

Rode sempre que mexer no JSON:
    uv run python design/build_tokens.py

Plugue no pre-commit para nunca ficarem dessincronizados.
"""

from __future__ import annotations

import json
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


OUT_WEB = ROOT.parent / "web" / "src" / "styles"


def build_css(tokens):
    """CSS variables para o front web (web/src/styles/tokens.css).

    Emite o dump completo do JSON com os nomes CSS naturais e, em seguida,
    os aliases dos nomes legados que o web herdou do primeiro spike --
    remapear os componentes de uma vez era arriscado, e o alias deixa cada
    tela migrar no seu tempo sem que o arquivo volte a divergir do JSON.
    """
    lines = [
        f"/* {BANNER} */",
        "",
        ":root {",
    ]
    section = None
    for path, value, _desc in tokens:
        if path[0] != section:
            section = path[0]
            lines.append(f"  /* --- {section} --- */")
        lines.append(f"  {css_name(path)}: {value};")

    # Aliases: somente nomes legados do web que NAO existem no JSON. A
    # primeira versao deste bloco remapeava nomes que o JSON tambem emite
    # (--space-*, --radius-md, --font-size-caption...) -- colisao em :root
    # fez o alias sobrescrever o token e criou cadeias (--space-1 -> ...
    # -> --space-8 = 32px para todo espacamento) e auto-referencias
    # circulares (--size-art-review: var(--size-art-review) = invalido).
    # Onde o nome colide, o CSS do web foi reescrito para usar o nome do
    # JSON; aqui ficam so os nomes exclusivos do web.
    lines += [
        "",
        "  /* === Aliases legados do web (nomes que nao existem no JSON) === */",
        "",
        "  /* superficies */",
        "  --color-bg: var(--color-surface-0);",
        "  --color-bg-elevated: var(--color-surface-1);",
        "  --color-surface-selection: var(--color-surface-hover);",
        "  --color-text: var(--color-text-primary);",
        "  --color-border-focus: var(--color-accent-base);",
        "",
        "  /* classificacao: o web usa --color-class-*, o JSON classification.* */",
        "  --color-class-lento: var(--color-classification-lento-base);",
        "  --color-class-lento-bg: var(--color-classification-lento-bg);",
        "  --color-class-lento-text: var(--color-classification-lento-text);",
        "  --color-class-neutro: var(--color-classification-neutro-base);",
        "  --color-class-neutro-bg: var(--color-classification-neutro-bg);",
        "  --color-class-neutro-text: var(--color-classification-neutro-text);",
        "  --color-class-animada: var(--color-classification-animada-base);",
        "  --color-class-animada-bg: var(--color-classification-animada-bg);",
        "  --color-class-animada-text: var(--color-classification-animada-text);",
        "",
        "  /* camelot: o web usa --camelot-N */",
    ]
    lines += [
        f"  --camelot-{n}: var(--color-camelot-{n});" for n in range(1, 13)
    ]
    lines += [
        "",
        "  /* tipografia */",
        "  --font-sans: var(--font-family-sans);",
        "  --font-mono: var(--font-family-mono);",
        "  --font-size-numeric: var(--font-size-body);",
        "  --font-size-heading: var(--font-size-title);",
        "  --letter-spacing-label: var(--font-tracking-wide);",
        "",
        "  /* movimento */",
        "  --transition-fast: var(--motion-fast)ms var(--motion-ease);",
        "}",
    ]
    return "\n".join(lines) + "\n"


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    tokens = flatten(data)

    OUT_WEB.mkdir(parents=True, exist_ok=True)
    (OUT_WEB / "tokens.css").write_text(build_css(tokens), encoding="utf-8")

    print(f"{len(tokens)} tokens -> web/src/styles/tokens.css")


if __name__ == "__main__":
    main()
