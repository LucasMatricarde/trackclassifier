"""Coluna numerica: rotulo em cima, spin fixo embaixo."""

from PySide6.QtWidgets import QSpinBox, QVBoxLayout, QWidget

from ...config import MODELO_MAXIMO, MODELO_MINIMO
from ..tokens import SPACE_2
from .settings_section import rotulo_de_campo

# Largura fixa dos dois campos numericos da secao Modelo.
# Um numero de ate quatro digitos com as setas do spin: esticar ate a
# coluna inteira daria 700px de caixa para "10".
_LARGURA_NUMERICO = 96


def cria_campo_numerico() -> QSpinBox:
    """Spin de largura fixa com range MODELO_MINIMO..MODELO_MAXIMO."""
    campo = QSpinBox()
    campo.setRange(MODELO_MINIMO, MODELO_MAXIMO)
    campo.setFixedWidth(_LARGURA_NUMERICO)
    return campo


def coluna_numerica(titulo: str, campo: QSpinBox) -> QWidget:
    """Rotulo em cima, campo embaixo — com setBuddy para acessibilidade."""
    rotulo = rotulo_de_campo(titulo)
    rotulo.setBuddy(campo)
    caixa = QWidget()
    dentro = QVBoxLayout(caixa)
    dentro.setContentsMargins(0, 0, 0, 0)
    dentro.setSpacing(SPACE_2)
    dentro.addWidget(rotulo)
    dentro.addWidget(campo)
    return caixa
