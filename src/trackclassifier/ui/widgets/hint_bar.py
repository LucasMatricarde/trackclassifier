"""Faixa de atalhos do rodape da janela.

Chrome da janela, nao da aba: e a mesma faixa em Revisao e Biblioteca, so
o texto muda. Por isso mora em MainWindow, abaixo do QTabWidget, e nao
dentro de cada aba -- duas faixas com o mesmo desenho em lugares diferentes
sairiam de sincronia na primeira mudanca de altura.

Os itens ficam alinhados A DIREITA, como no mockup: a esquerda do rodape
pertence a faixa de status, que responde outra pergunta ("como esta o
acervo") e nao pode competir por leitura com a legenda de teclas.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..tokens import SPACE_5
from ..typography import estiliza_label

#: Altura da faixa no mockup 3a. Fixa, e nao derivada do conteudo: a barra
#: precisa ocupar o mesmo espaco em toda aba, inclusive nas que nao tem
#: atalho nenhum -- senao a tabela pularia de altura ao trocar de aba.
ALTURA = 31

#: Espaco entre um item e o proximo. Maior que SPACE_5 de proposito: com o
#: espaco padrao as quatro legendas encostam e leem como uma frase so -- o
#: mesmo motivo que a DecisionBar documenta para os alvos.
ESPACO_ENTRE_ITENS = 20


class HintBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HintBar")
        # Sem isto o QWidget puro ignora background e border-top do QSS.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(ALTURA)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(SPACE_5, 0, SPACE_5, 0)
        self._layout.setSpacing(ESPACO_ENTRE_ITENS)
        self._layout.addStretch(1)
        self._rotulos: list[QLabel] = []

    def set_atalhos(self, atalhos: tuple[tuple[str, bool], ...]) -> None:
        """(texto, destacado) na ordem em que a faixa lista.

        O destaque marca a acao PRINCIPAL da aba -- classificar. Ela sobe de
        text.muted para text.secondary: as outras teclas continuam
        disponiveis, mas nao sao o que a aba existe para fazer.

        Tupla vazia esconde a faixa inteira. Uma faixa vazia ainda ocuparia
        31px e leria como um rodape quebrado.
        """
        for rotulo in self._rotulos:
            self._layout.removeWidget(rotulo)
            rotulo.deleteLater()
        self._rotulos.clear()

        for texto, destacado in atalhos:
            rotulo = QLabel()
            rotulo.setObjectName("MicroLabel")
            if destacado:
                rotulo.setProperty("tone", "secondary")
            estiliza_label(rotulo, texto)
            self._layout.addWidget(rotulo)
            self._rotulos.append(rotulo)

        self.setVisible(bool(atalhos))
