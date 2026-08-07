"""Bloco centralizado para tela sem conteudo.

Existe porque as tres abas abrem vazias -- e uma frase no canto superior
esquerdo dentro de um vazio de altura inteira e o que o app mostrava antes.
A acao opcional e o ponto: "Fila vazia. Use Escanear" manda o usuario
procurar um botao; um botao Escanear aqui dispara o scan.

Sao ACOES no plural, com variante, e nao um botao primario fixo: o mockup
06 pede neutro no Modelo ("Ir para a revisao" nao e a acao principal
daquela tela, e classificar) e DOIS neutros na busca sem resultado. O sinal
carrega o rotulo porque, com dois botoes, um sinal sem argumento obrigaria
a aba a adivinhar qual deles foi clicado.
"""

from collections.abc import Sequence
from typing import NamedTuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..tokens import SPACE_4, SPACE_5
from ..typography import estiliza_label


class Acao(NamedTuple):
    rotulo: str
    #: Valor da propriedade dinamica `variant` do QSS. "primary" e o
    #: contorno de acento; "base" e o botao neutro (a ausencia da
    #: propriedade tambem daria neutro, mas nomear e o que deixa a
    #: escolha visivel no call site).
    variante: str = "primary"


class EmptyState(QWidget):
    acao_clicada = Signal(str)

    def __init__(
        self,
        titulo: str,
        subtitulo: str = "",
        acoes: Sequence[Acao] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._titulo = QLabel(titulo)
        self._titulo.setObjectName("TrackTitle")
        self._titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # RichText e nao PlainText: a busca sem resultado destaca o termo
        # dentro da PRIMEIRA linha (ver LibraryTab._texto_sem_resultado).
        self._titulo.setTextFormat(Qt.TextFormat.RichText)

        self._subtitulo = QLabel(subtitulo)
        self._subtitulo.setObjectName("Hint")
        self._subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # RichText e nao PlainText: a busca sem resultado destaca o termo e
        # o filtro DENTRO da frase, e tres QLabel emendados nao alinham na
        # mesma baseline nem quebram linha juntos.
        self._subtitulo.setTextFormat(Qt.TextFormat.RichText)
        self._subtitulo.setVisible(bool(subtitulo))

        self._botoes: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACE_5)
        layout.addStretch(1)
        layout.addWidget(self._titulo)
        layout.addWidget(self._subtitulo)

        if acoes:
            faixa = QHBoxLayout()
            faixa.setSpacing(SPACE_4)
            faixa.addStretch(1)
            for acao in acoes:
                botao = QPushButton()
                # Rotulo de botao fala mono/caixa alta no app inteiro -- ver
                # ui/typography.py.
                estiliza_label(botao, acao.rotulo)
                botao.setProperty("variant", acao.variante)
                # O rotulo ORIGINAL viaja no sinal: quem escuta comparou com
                # a string que passou, nao com a versao em caixa alta.
                botao.clicked.connect(
                    lambda _=False, rotulo=acao.rotulo: self.acao_clicada.emit(rotulo)
                )
                self._botoes[acao.rotulo] = botao
                faixa.addWidget(botao)
            faixa.addStretch(1)
            # Os stretches dos dois lados, e nao AlignHCenter: num
            # QVBoxLayout o botao esticaria a largura inteira e leria como
            # faixa de fundo, nao como botao.
            layout.addLayout(faixa)

        layout.addStretch(1)

    def set_texto(self, titulo: str, subtitulo: str = "") -> None:
        self._titulo.setText(titulo)
        self._subtitulo.setText(subtitulo)
        self._subtitulo.setVisible(bool(subtitulo))

    def rotulos_das_acoes(self) -> tuple[str, ...]:
        return tuple(self._botoes)

    def subtitulo_visivel(self) -> bool:
        return not self._subtitulo.isHidden()

    def texto_do_titulo(self) -> str:
        return self._titulo.text()

    def texto_do_subtitulo(self) -> str:
        return self._subtitulo.text()

    def acionar(self, rotulo: str) -> None:
        """Aciona um botao pelo rotulo. Existe para o teste percorrer o
        mesmo caminho do clique real."""
        self._botoes[rotulo].click()
