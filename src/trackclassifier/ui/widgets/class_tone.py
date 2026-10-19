"""Vocabulario de cor de classe, em um lugar so.

O mesmo conceito tem tres nomes no projeto e nenhum deles e o do outro: o
rotulo que vem do dominio (`-1` / `neutra` / `+1`), o sufixo que o QSS le como
propriedade dinamica (`[class="low"]`) e o nome que
`tokens.classification_base` entende (`lento` / `neutro` / `animada`). Sem esta
tabela, cada widget que precise de mais de um deles escreve o mapa de novo --
o `class_balance.py` chegou a ter dois no mesmo arquivo, e o chip de classe
seria o terceiro.
"""

from ..tokens import classification_base

#: (rotulo do dominio, sufixo do QSS, nome em tokens.classification_base).
#: Mesma ordem de LABEL_ORDER, que e a ordem em que o balanco e os chips
#: aparecem na tela.
_CLASSES = (
    ("-1", "low", "lento"),
    ("neutra", "neutral", "neutro"),
    ("+1", "high", "animada"),
)

_TONE = {rotulo: tone for rotulo, tone, _ in _CLASSES}
_TOKEN = {rotulo: token for rotulo, _, token in _CLASSES}


def tone_do_rotulo(rotulo: str) -> str | None:
    """Sufixo da propriedade `class` do QSS. None quando nao e classe.

    None e um resultado legitimo, e nao um erro: e o que o chip "Todos" e um
    cabecalho de tabela precisam, porque nao representam classe nenhuma e nao
    devem ganhar cor de classe por acidente.
    """
    return _TONE.get(rotulo)


def cor_base_do_rotulo(rotulo: str) -> str:
    """Matiz cheia da classe, para quem pinta a mao (Meter, delegate).

    `classification_base` e nao `classification_colors`: o par (bg, text) e do
    chip, que tem fundo proprio; aqui o que se pinta e uma barra de 6px sobre o
    fundo da tela, e ali o bg sumiria.
    """
    return classification_base(_TOKEN[rotulo])
