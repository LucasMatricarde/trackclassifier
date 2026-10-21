"""Helpers de secao do formulario de configuracao."""

from PySide6.QtWidgets import QLabel

from ..layouts import secao
from ..tokens import FONT_TRACKING_WIDEST
from ..typography import aplica_tracking
from ..widgets.panel import Panel


def secao_painel(*itens, espaco: int) -> Panel:
    """Cria um Panel com conteudo interno espaçado."""
    painel = Panel()
    conteudo = secao(*itens, espaco=espaco)
    conteudo.setObjectName("PanelSection")
    painel.content.addWidget(conteudo)
    return painel


def cabecalho(texto: str) -> QLabel:
    """Cabecalho de secao: mono, caixa alta, tracking wide, cor secondary."""
    rotulo = QLabel(texto.upper())
    rotulo.setObjectName("SectionHeader")
    aplica_tracking(rotulo, FONT_TRACKING_WIDEST)
    return rotulo


def ajuda(texto: str) -> QLabel:
    """Texto de ajuda: Hint, word wrap."""
    rotulo = QLabel(texto)
    rotulo.setObjectName("Hint")
    rotulo.setWordWrap(True)
    return rotulo


def rotulo_de_campo(texto: str) -> QLabel:
    """Rotulo de um campo: caption em texto secundario."""
    rotulo = QLabel(texto)
    rotulo.setObjectName("FieldLabel")
    return rotulo
