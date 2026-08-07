"""Fundo de card num QWidget subclasse -- e a unica forma de errar aqui.

Qt so pinta o `background` do QSS sozinho para a classe QWidget PURA. Numa
subclasse (todo card deste app e uma: TechDetail, DecisionBar, GuessBar), o
mesmo `background:` no setStyleSheet fica mudo ate o widget passar por um
paintEvent proprio ou WA_StyledBackground ser ligado a mao -- sem isto o card
fica com metade do fundo pintado e a outra metade vazando a cor da janela por
tras. O sintoma so aparece com o app rodando: um grab() isolado de teste forca
esse paint por outro caminho e mostra o fundo certo mesmo quebrado.

`model_tab._card()` nunca precisou disto porque devolve uma instancia direta
de QWidget(), nao uma subclasse -- e o unico jeito de nao pagar esse imposto e
nao ter uma classe propria. Todo widget com __init__ proprio paga.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


def aplica_superficie(widget: QWidget, cor: str, radius: int | None = None) -> None:
    """Pinta o fundo de `widget` com `cor` (e `radius` px de cantos, se dado)
    e liga o atributo que faz essa pintura valer numa subclasse de QWidget."""
    regra = f"background: {cor};"
    if radius is not None:
        regra += f" border-radius: {radius}px;"
    widget.setStyleSheet(regra)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
