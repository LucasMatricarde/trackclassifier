"""Chips de classe com contagem (Todos | -1 | neutra | +1).

Substituem o combo "Todos" da barra de filtros: o combo dizia "Todos" sem dizer
quantos e, com o filtro ligado, escondia que existiam outras classes no acervo
-- o chip diz as duas coisas numa leitura so.

O rotulo e a contagem sao dois QLabel filhos, e nao o texto do proprio botao,
porque `mono-para-numero` (design-tokens.json) pede o numero em mono e o rotulo
em sans: uma string so nao carrega duas fontes. As margens internas vao no
layout, nao no padding do QSS -- padding de QSS desloca o texto do botao, nao
os filhos, e os dois juntos dariam um chip torto.
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from ..tokens import SIZE_CONTROL_BASE, SPACE_3, SPACE_4
from ..viewmodel import LABELS_EM_ORDEM
from .class_tone import tone_do_rotulo

#: O chip que nao filtra nada. Mora aqui, e nao no viewmodel: e texto de tela,
#: e os unicos que precisam conhece-lo sao este widget e quem limpa um filtro.
TODOS = "Todos"


class _Chip(QPushButton):
    """QPushButton que pede a largura do CONTEUDO, nao a do texto do botao.

    QPushButton::sizeHint() sai do texto/icone (QStyle::sizeFromContents) e
    ignora o layout dos filhos. Com o texto vazio -- o conteudo do chip sao dois
    QLabel -- o padrao pedia 26px, os labels eram esmagados a 1px e o chip saia
    VAZIO na tela, so com a borda e o fundo. Nao era o QSS (nao ha min-width nem
    padding ali) nem o layout do chip: geometria so existe com o widget mostrado
    e o layout ativado, e nenhum teste que so le `.text()` chega perto disso --
    o render da Biblioteca e que mostrou (Task 1.5).

    A ALTURA continua vindo do QPushButton: o chip e `setFixedHeight`, e quem
    mede controle neste app e o QSS (min-height do QPushButton generico).
    """

    def sizeHint(self) -> QSize:
        interno = self.layout()
        if interno is None:  # antes de _cria_chip montar o layout interno
            return super().sizeHint()
        return QSize(interno.sizeHint().width(), super().sizeHint().height())

    def minimumSizeHint(self) -> QSize:
        """Piso: o chip ainda pode encolher (label elide), so nao pode nascer
        no tamanho minimo -- era exatamente o que o sizeHint padrao fazia."""
        interno = self.layout()
        if interno is None:
            return super().minimumSizeHint()
        return QSize(interno.minimumSize().width(), super().minimumSizeHint().height())


class ClassChips(QWidget):
    #: Rotulo do chip que passou a valer. So dispara quando MUDA -- clicar no
    #: chip aceso nao emite.
    mudou = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ClassChips")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_3)

        self._contagens: dict[str, QLabel] = {}
        self._botoes: dict[str, QPushButton] = {}
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        for rotulo in (TODOS, *LABELS_EM_ORDEM):
            botao = self._cria_chip(rotulo)
            self._botoes[rotulo] = botao
            self._grupo.addButton(botao)
            layout.addWidget(botao)
        layout.addStretch(1)

        self._botoes[TODOS].setChecked(True)
        # Conectado DEPOIS do setChecked inicial: buttonToggled dispara na
        # marcacao, e ligar antes emitiria `mudou` durante a construcao, antes
        # de quem usa ter tido chance de se conectar (mesma ordem do Segmented).
        self._grupo.buttonToggled.connect(self._quando_alterna)

    def _cria_chip(self, rotulo: str) -> _Chip:
        botao = _Chip(self)
        botao.setObjectName("ClassChip")
        botao.setCheckable(True)
        # Altura fixa em codigo, e nao pelo QSS: o chip fica ao lado do
        # Segmented da densidade e os dois precisam fechar na mesma linha.
        botao.setFixedHeight(SIZE_CONTROL_BASE)
        botao.setProperty("rotulo", rotulo)
        tone = tone_do_rotulo(rotulo)
        if tone is not None:
            botao.setProperty("class", tone)
        # O chip nao tem texto proprio (o conteudo sao dois QLabel filhos),
        # entao sem isto o leitor de tela anuncia so "botao".
        botao.setAccessibleName(f"Filtro {rotulo}")

        texto = QLabel(rotulo, botao)
        texto.setObjectName("ClassChipLabel")
        contagem = QLabel("0", botao)
        contagem.setObjectName("ClassChipCount")
        # Sem o atributo o clique no meio do chip morre no filho, justamente
        # onde o dedo acerta -- o rotulo ocupa a maior parte da area.
        for filho in (texto, contagem):
            filho.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            # A propriedade vai nos FILHOS tambem: o QSS pinta o texto pela cor
            # da classe, e regra de descendente (`chip[class] QLabel`) nao chega
            # no filho -- ver o bloco ClassChip em design/build_tokens.py.
            if tone is not None:
                filho.setProperty("class", tone)

        self._contagens[rotulo] = contagem
        interno = QHBoxLayout(botao)
        interno.setContentsMargins(SPACE_4, 0, SPACE_4, 0)
        interno.setSpacing(SPACE_4)
        interno.addWidget(texto)
        interno.addWidget(contagem)
        return botao

    def _quando_alterna(self, botao: QAbstractButton, marcado: bool) -> None:
        # Uma troca dispara duas vezes (o antigo desmarca, o novo marca).
        if marcado:
            self.mudou.emit(botao.property("rotulo"))

    def rotulo_ativo(self) -> str:
        botao = self._grupo.checkedButton()
        return botao.property("rotulo") if botao is not None else TODOS

    def acionar(self, rotulo: str) -> None:
        """Aciona o chip como se clicado. Rotulo desconhecido nao faz nada.

        Existe para quem precisa do RESULTADO do clique -- a aba, ao limpar um
        filtro junto com a busca -- sem fabricar um evento de mouse. Num grupo
        exclusivo o clique no chip ja aceso nao alterna nada e, por isso, nao
        emite: o mesmo vale aqui.
        """
        botao = self._botoes.get(rotulo)
        if botao is not None:
            botao.click()

    def set_contagens(self, contagens: tuple[int, ...], total: int) -> None:
        """Escreve as contagens ABSOLUTAS, nunca filtradas pela busca.

        Contagem que encolhesse junto com o filtro nao informaria nada: o numero
        existe para dizer o que HA no acervo, nao o que sobrou na tela.
        """
        for rotulo, valor in zip(LABELS_EM_ORDEM, contagens, strict=True):
            self._contagens[rotulo].setText(str(valor))
            self._botoes[rotulo].setAccessibleDescription(f"{valor} tracks")

        self._contagens[TODOS].setText(str(total))
        self._botoes[TODOS].setAccessibleDescription(f"{total} tracks")

        # Sem acervo nao ha o que filtrar: a barra inteira fica inerte.
        for botao in self._botoes.values():
            botao.setEnabled(total > 0)
        # E os chips de CLASSE saem de cena: com zero em todos, os tres nao
        # dizem nada que o EmptyState nao diga, e a primeira tela de quem abre o
        # app ficava com quatro zeros. Fica so o "Todos 0" (design, tabela de
        # Estados). O comentario anterior justificava os quatro "para a barra
        # nao mudar de largura", mas a contagem do proprio Todos ja muda a
        # largura ("0" para "463") -- e o estado vazio sempre aciona TODOS, o
        # que garante que nenhum chip escondido esta aceso.
        for rotulo in LABELS_EM_ORDEM:
            self._botoes[rotulo].setVisible(total > 0)
