"""Cor derivada de token, para nao nascer literal de cor novo.

O teste que varre `ui/` procura `#RRGGBB` -- entao escrever
`"rgba(240,87,92,0.12)"` a mao passaria por ele. E mesmo assim seria a
paleta duplicada: no dia em que o vermelho mudar no JSON, o literal fica
para tras sem ninguem perceber. Derivar do token e o que amarra os dois.

Existe porque a v0.2 usa a mesma cor com alfa em varios lugares (o fundo
do erro grave na matriz, o badge de contagem das falhas) e o JSON nao
carrega uma entrada por opacidade -- isso multiplicaria a paleta por
quantas transparencias a tela precisar.
"""


def tinta(cor: str, alpha: float) -> str:
    """COLOR_STATE_DANGER, 0.12 -> 'rgba(240,87,92,0.12)'.

    O exemplo nomeia o token em vez de escrever o hex: a varredura de
    `test_nenhum_hex_fora_do_json` e por linha e nao distingue docstring
    de codigo -- e nem deveria, ja que um hex no exemplo envelhece igual.

    Aceita so hex de seis digitos: os tokens de borda ja sao rgba, e
    passar um deles aqui e erro de chamada, nao caso a tratar.
    """
    if not (0.0 <= alpha <= 1.0):
        raise ValueError(f"alpha fora de [0, 1]: {alpha}")
    if not (cor.startswith("#") and len(cor) == 7):
        raise ValueError(f"esperado hex de seis digitos, veio: {cor}")
    r, g, b = (int(cor[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"
