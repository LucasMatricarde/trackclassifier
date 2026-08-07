"""Matriz de confusao colorida por severidade ordinal, nao por contagem.

As tres classes sao ordenadas. Confundir neutra com animada e um deslize;
confundir lento com animada e um erro grave. `ordinal_mae` ja pesa isso, e
a matriz de texto anterior tratava toda celula fora da diagonal igual -- o
dado estava la e a tela escondia.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..colors import tinta
from ..tokens import (
    COLOR_BORDER_DEFAULT,
    COLOR_CLASSIFICATION_NEUTRO_BG,
    COLOR_CLASSIFICATION_NEUTRO_TEXT,
    COLOR_STATE_DANGER,
    COLOR_SURFACE_2,
    COLOR_TEXT_DISABLED,
    COLOR_TEXT_PRIMARY,
    FONT_SIZE_MICRO,
    RADIUS_XS,
    SPACE_2,
    SPACE_3,
    SPACE_5,
    classification_base,
)
from ..typography import aplica_tracking, estiliza_label
from ..viewmodel import LABELS_EM_ORDEM

#: Rotulo do dominio -> nome da classe no design system. Mesma tabela de
#: delegates.py, pelo mesmo motivo: tokens.py e gerado e nao pode conhecer
#: o dominio, e viewmodel.py nao pode conhecer o design system.
_CLASSE = {"+1": "animada", "neutra": "neutro", "-1": "lento"}

_ALTURA_CELULA = 44
_ALTURA_CABECALHO = 20
_LARGURA_ROTULO = 64
#: Opacidade da tinta de danger no erro grave. 12% e o bastante para o
#: vermelho ler como fundo sem competir com o numero em cima.
_ALFA_GRAVE = 0.12
#: Lado do quadrado da legenda.
_AMOSTRA = 10


def severidade(i: int, j: int) -> int:
    """Distancia ordinal entre a classe real e a prevista."""
    return abs(i - j)


def _estilo_da_celula(i: int, j: int, valor: int) -> str:
    distancia = severidade(i, j)
    if distancia == 0:
        fundo, frente = COLOR_SURFACE_2, COLOR_TEXT_PRIMARY
        borda = f"border: 1px solid {COLOR_BORDER_DEFAULT};"
    elif distancia == 1:
        fundo, frente = COLOR_CLASSIFICATION_NEUTRO_BG, COLOR_CLASSIFICATION_NEUTRO_TEXT
        borda = ""
    else:
        fundo, frente = tinta(COLOR_STATE_DANGER, _ALFA_GRAVE), COLOR_STATE_DANGER
        borda = ""
    # Zero apaga o numero DEPOIS da cor de severidade, nao no lugar dela:
    # o fundo continua dizendo onde a celula fica na escala, e so o valor
    # para de chamar atencao. Senao uma matriz zerada vira um bloco cinza.
    if valor == 0:
        frente = COLOR_TEXT_DISABLED
    return f"background: {fundo}; color: {frente}; border-radius: {RADIUS_XS}px; {borda}"


class ConfusionMatrix(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        titulo = QLabel()
        titulo.setObjectName("MicroLabel")
        estiliza_label(titulo, "Matriz de confusao")

        convencao = QLabel()
        convencao.setObjectName("MicroLabel")
        estiliza_label(convencao, "real x previsto")
        # Mais apagada que o titulo: e a legenda da convencao, nao o nome
        # do card. Sem isso as duas competem pela mesma leitura.
        convencao.setStyleSheet(f"color: {COLOR_TEXT_DISABLED};")

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(SPACE_3)
        cabecalho.addWidget(titulo)
        cabecalho.addWidget(convencao)
        cabecalho.addStretch(1)

        self.grade = QWidget()
        grade = QGridLayout(self.grade)
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setSpacing(SPACE_2)
        grade.setColumnMinimumWidth(0, _LARGURA_ROTULO)
        for coluna in range(1, 4):
            grade.setColumnStretch(coluna, 1)

        for indice, rotulo in enumerate(LABELS_EM_ORDEM):
            grade.addWidget(self._rotulo(rotulo, _ALTURA_CABECALHO), 0, indice + 1)
            grade.addWidget(
                self._rotulo(rotulo, _ALTURA_CELULA, direita=True), indice + 1, 0
            )

        self._celulas: dict[tuple[int, int], QLabel] = {}
        for i in range(3):
            for j in range(3):
                celula = QLabel("0")
                celula.setObjectName("Numeric")
                celula.setAlignment(Qt.AlignmentFlag.AlignCenter)
                celula.setFixedHeight(_ALTURA_CELULA)
                celula.setStyleSheet(_estilo_da_celula(i, j, 0))
                self._celulas[(i, j)] = celula
                grade.addWidget(celula, i + 1, j + 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_5)
        layout.addLayout(cabecalho)
        layout.addWidget(self.grade)
        layout.addWidget(self._legenda())
        layout.addStretch(1)

    def _rotulo(self, texto: str, altura: int, direita: bool = False) -> QLabel:
        rotulo = QLabel(texto)
        rotulo.setObjectName("MicroLabel")
        # Tracking sim, caixa alta nao: "-1", "neutra" e "+1" sao o
        # vocabulario do dominio (labels.Label), e "NEUTRA" nao e um
        # rotulo que existe em lugar nenhum do sistema.
        aplica_tracking(rotulo)
        rotulo.setFixedHeight(altura)
        horizontal = (
            Qt.AlignmentFlag.AlignRight if direita else Qt.AlignmentFlag.AlignHCenter
        )
        rotulo.setAlignment(horizontal | Qt.AlignmentFlag.AlignVCenter)
        # A cor do rotulo e a da classe, nao a do micro-label: e o unico
        # lugar da grade onde a classe aparece nomeada.
        rotulo.setStyleSheet(
            f"color: {classification_base(_CLASSE[texto])}; font-size: {FONT_SIZE_MICRO};"
        )
        return rotulo

    def _legenda(self) -> QWidget:
        """Sem legenda, a escala de cor e adivinhacao."""
        faixa = QWidget()
        layout = QHBoxLayout(faixa)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_3)
        for distancia, texto in (
            (0, "acerto"),
            (1, "erro leve · 1 classe"),
            (2, "erro grave · 2 classes"),
        ):
            amostra = QLabel()
            amostra.setFixedSize(_AMOSTRA, _AMOSTRA)
            # valor=1 de proposito: a amostra mostra a cor cheia da faixa,
            # nao o tratamento de celula zerada.
            amostra.setStyleSheet(_estilo_da_celula(0, distancia, 1))
            item = QLabel()
            item.setObjectName("MicroLabel")
            estiliza_label(item, texto)
            layout.addWidget(amostra)
            layout.addWidget(item)
            layout.addSpacing(SPACE_3)
        layout.addStretch(1)
        return faixa

    def celula(self, i: int, j: int) -> QLabel:
        """Acesso por (real, previsto) -- e o que o teste inspeciona."""
        return self._celulas[(i, j)]

    def set_confusion(self, confusion: tuple[tuple[int, ...], ...] | None) -> None:
        # Modelo nao treinado esconde a grade inteira em vez de mostrar
        # nove zeros: matriz zerada e um resultado, "ainda nao ha matriz"
        # e outra coisa.
        self.grade.setVisible(confusion is not None)
        if confusion is None:
            return
        for i, linha in enumerate(confusion):
            for j, valor in enumerate(linha):
                celula = self._celulas[(i, j)]
                celula.setText(str(valor))
                celula.setStyleSheet(_estilo_da_celula(i, j, valor))
