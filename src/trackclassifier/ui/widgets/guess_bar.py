"""Faixa do palpite: escala ordinal, classe, confianca e o aviso.

A confianca era texto dentro de um QLabel ("Palpite: +1 confianca 0.82").
Vira medidor porque e a informacao mais acionavel da tela: e ela que
explica por que ESTA track veio na frente na fila. `TrackService.queue()`
ordena por confianca crescente -- mostra primeiro o que o modelo menos
sabe -- e nada na tela anterior comunicava isso.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..tokens import (
    COLOR_STATE_WARNING,
    COLOR_TEXT_SECONDARY,
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_WEIGHT_MEDIUM,
    SPACE_5,
    SPACE_6,
    classification_colors,
)
from ..typography import estiliza_label
from .meter import Meter
from .ordinal_scale import OrdinalScale

_CLASSE = {"+1": "animada", "neutra": "neutro", "-1": "lento"}

#: Abaixo disto a barra de confianca vira warning. E o mesmo limiar que a
#: spec da Revisao usa: 0.4 separa "o modelo tem opiniao" de "o modelo
#: esta chutando", e o DJ precisa saber em qual dos dois esta.
LIMIAR_ATENCAO = 0.4

#: Largura maxima do trilho, do mockup. Nao estica pela largura da janela:
#: um medidor de 800px de largura nao le melhor que um de 260, so ocupa
#: mais.
_LARGURA_TRILHO = 260
_ALTURA_TRILHO = 2


class GuessBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # objectName + a regra centralizada `QWidget#Sidebar, #PlayerBar,
        # #GuessBar` em app.qss/build_tokens.py -- e o mesmo painel
        # (COLOR_SURFACE_1, RADIUS_MD) que PlayerBar ja usava, entao o fundo
        # mora num lugar so em vez de duplicado aqui num setStyleSheet
        # local. WA_StyledBackground continua necessario: sem ele o Qt
        # descarta `background` de uma subclasse de QWidget sem paintEvent
        # proprio, e a faixa ficava sem painel nenhum.
        self.setObjectName("GuessBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        titulo = QLabel()
        titulo.setObjectName("MicroLabel")
        estiliza_label(titulo, "Palpite")

        self.escala = OrdinalScale()

        self.classe = QLabel("")
        self.classe.setObjectName("Numeric")

        self.medidor = Meter(COLOR_TEXT_SECONDARY, _ALTURA_TRILHO)
        self.medidor.setAccessibleName("Confianca do palpite")
        # Largura FIXA, nao maxima: com maximumWidth mais stretch, o layout
        # reservava a largura sobrando da janela para o medidor, ele pintava
        # so 260 dela e o "confianca 0.82" ficava boiando a uns 60px do fim
        # do trilho, como se fosse outro campo.
        self.medidor.setFixedWidth(_LARGURA_TRILHO)

        self.numero = QLabel("")
        self.numero.setObjectName("Numeric")
        self.numero.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};"
        )

        self.aviso = QLabel("")
        self.aviso.setObjectName("MicroLabel")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_5, 10, SPACE_5, 10)
        layout.setSpacing(SPACE_6)
        layout.addWidget(titulo)
        layout.addWidget(self.escala)
        layout.addWidget(self.classe)
        layout.addWidget(self.medidor)
        layout.addWidget(self.numero)
        layout.addStretch(1)
        layout.addWidget(self.aviso)

    def set_guess(
        self, rotulo: str | None, confianca: float | None, *, low_confidence: bool
    ) -> None:
        """Sem palpite, a faixa some inteira.

        Modelo nao treinado nao tem opiniao, e uma faixa vazia com o rotulo
        "PALPITE" sugeriria que ele tem uma e a tela nao conseguiu mostrar.
        Os tres alvos de decisao continuam ativos: classificar e justamente
        o que treina.
        """
        self.setVisible(rotulo is not None)
        if rotulo is None:
            return

        self.escala.set_label(rotulo)
        _, cor = classification_colors(_CLASSE[rotulo])
        self.classe.setText(rotulo)
        self.classe.setStyleSheet(
            f"color: {cor}; font-size: {FONT_SIZE_BODY};"
            f"font-weight: {FONT_WEIGHT_MEDIUM};"
        )

        valor = confianca or 0.0
        self.medidor.set_fraction(valor)
        self.numero.setText(f"confianca {valor:.2f}")

        self.aviso.setVisible(low_confidence)
        # estiliza_label e nao setText: o objectName MicroLabel so entrega a
        # cor, o tamanho e a mono -- caixa alta e tracking sao aplicados em
        # codigo (o QSS do Qt nao tem text-transform nem letter-spacing), e
        # sem eles este era o unico micro-label da tela em caixa baixa.
        estiliza_label(
            self.aviso,
            "Modelo com poucos exemplos · confianca reduzida pela metade"
            if low_confidence
            else "",
        )
        # Warning abaixo do limiar: a cor e o que faz "0.31" ser lido como
        # um problema sem o usuario precisar lembrar onde fica o corte.
        self.medidor.set_color(
            COLOR_STATE_WARNING if valor < LIMIAR_ATENCAO else COLOR_TEXT_SECONDARY
        )
