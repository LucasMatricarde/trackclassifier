"""Alternador de N posicoes visiveis lado a lado.

Diferente de um botao unico que troca de rotulo: as duas posicoes ficam na
tela e o estado corrente e o segmento aceso. Custa o dobro de largura na
barra e paga com nao exigir que o usuario deduza o estado a partir do
rotulo -- "Compacta" num botao pode ser tanto o modo atual quanto o modo
para onde o clique leva, e so a tabela atras resolve a ambiguidade.

A caixa (borda e raio) e do container, nao de cada segmento: dar borda aos
dois desenharia uma linha dupla no meio. Ver o bloco QWidget#Segmented no
QSS gerado.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from ..tokens import SIZE_CONTROL_BASE
from ..typography import estiliza_label

#: Espessura da borda do container. As margens do layout deixam essa faixa
#: livre: sem elas o fundo do segmento aceso cobre a borda e a caixa some
#: justamente do lado que esta selecionado.
_BORDA = 1


class Segmented(QWidget):
    #: Indice do segmento que passou a valer. So dispara quando MUDA --
    #: clicar no que ja esta aceso nao emite nada.
    mudou = Signal(int)

    def __init__(self, rotulos: tuple[str, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Segmented")
        # QWidget puro nao pinta fundo nem borda vindos do QSS sem este
        # atributo -- o estilo e simplesmente ignorado e a caixa some.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(SIZE_CONTROL_BASE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(_BORDA, _BORDA, _BORDA, _BORDA)
        layout.setSpacing(0)

        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        for indice, rotulo in enumerate(rotulos):
            botao = QPushButton()
            botao.setObjectName("Segment")
            botao.setCheckable(True)
            estiliza_label(botao, rotulo)
            self._grupo.addButton(botao, indice)
            layout.addWidget(botao)

        self._grupo.button(0).setChecked(True)
        # Conectado DEPOIS do setChecked inicial: idToggled dispara na
        # marcacao, e ligar antes emitiria `mudou` durante a construcao,
        # antes de quem usa ter tido chance de se conectar.
        #
        # idToggled e nao idClicked: com o grupo exclusivo, clicar no
        # segmento ja aceso ainda conta como clique, e idClicked reemitiria
        # o mesmo indice -- na Biblioteca isso jogaria fora o cache de
        # pixmap dos delegates de graca.
        self._grupo.idToggled.connect(self._quando_alterna)

    def _quando_alterna(self, indice: int, marcado: bool) -> None:
        # Uma troca dispara duas vezes (o antigo desmarca, o novo marca).
        if marcado:
            self.mudou.emit(indice)

    def selecionado(self) -> int:
        return self._grupo.checkedId()

    def set_selecionado(self, indice: int) -> None:
        botao = self._grupo.button(indice)
        if botao is not None:
            botao.setChecked(True)
