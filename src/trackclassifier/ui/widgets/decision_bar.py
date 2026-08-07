"""Rodape da Revisao: os tres alvos de decisao e a legenda de atalhos.

O digito vive DENTRO do alvo, e nao numa legenda separada. Isso faz do
botao e da tecla a mesma afordancia visual, em vez de duas coisas que o
usuario precisa correlacionar. Classificar centenas de tracks com o mouse
e inviavel -- o alvo desenhado e o que ensina a tecla, nao um substituto
dela.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from ..tokens import (
    COLOR_BORDER_DEFAULT,
    COLOR_BORDER_STRONG,
    COLOR_BORDER_SUBTLE,
    COLOR_SURFACE_1,
    COLOR_TEXT_DISABLED,
    COLOR_TEXT_PRIMARY,
    FONT_FAMILY_MONO,
    FONT_FAMILY_SANS,
    FONT_SIZE_CAPTION,
    FONT_SIZE_LARGE,
    FONT_SIZE_SMALL,
    FONT_TRACKING_WIDE,
    FONT_WEIGHT_MEDIUM,
    RADIUS_SM,
    SIZE_CONTROL_BASE,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
    SPACE_7,
    SPACE_8,
    classification_colors,
)
from ..typography import aplica_tracking, estiliza_label
from ..viewmodel import LABELS_EM_ORDEM

_CLASSE = {"+1": "animada", "neutra": "neutro", "-1": "lento"}

_ALTURA_ALVO = 40

#: Os atalhos, na ordem em que a barra os lista. As teclas tem que bater
#: com o que MainWindow._registra_atalhos registra de verdade -- uma
#: legenda que promete uma tecla que nao existe e pior que legenda nenhuma.
#:
#: O mockup escreve "Z desfazer", e nao da para cumprir: QShortcut com
#: contexto WindowShortcut roda ANTES da entrega normal do evento, entao um
#: "Z" solto roubaria a letra do campo de busca da Biblioteca -- digitar
#: "zenith" ali desfaria seis decisoes. Por isso Ctrl+Z (que o Qt mapeia
#: para Cmd no macOS sozinho) e a legenda diz a verdade.
_ATALHOS = (("espaco", "tocar"), ("← →", "navegar"), ("ctrl+Z", "desfazer"))


class _Alvo(QPushButton):
    """QPushButton que se dimensiona pelo layout interno, e nao pelo texto.

    QPushButton.sizeHint() e calculado a partir de text() e icon() -- ele
    ignora o layout dos filhos. Como os dois textos do alvo sao QLabel (para
    o digito e o rotulo terem cores diferentes), o botao nascia com a
    largura de um botao sem texto nenhum e recortava os dois.
    """

    def sizeHint(self):  # noqa: N802 (assinatura do Qt)
        return self.layout().sizeHint()

    def minimumSizeHint(self):  # noqa: N802 (assinatura do Qt)
        return self.layout().minimumSize()


class DecisionBar(QWidget):
    #: Rotulo do dominio ("-1" | "neutra" | "+1").
    decidido = Signal(str)
    bloco_pedido = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(64)
        # WA_StyledBackground: o Qt descarta o `background` de uma subclasse
        # de QWidget que nao reimplementa paintEvent, e o rodape ficava com
        # o fundo da janela em vez do painel. O seletor "DecisionBar" impede
        # que o fundo e a borda descam para os filhos -- sem ele, cada
        # legenda ganhava a mesma faixa clara atras de si e o rodape virava
        # uma fileira de caixinhas.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"DecisionBar {{ background: {COLOR_SURFACE_1};"
            f" border-top: 1px solid {COLOR_BORDER_SUBTLE}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_6, 0, SPACE_6, 0)
        layout.setSpacing(SPACE_4)

        self._alvos: dict[str, _Alvo] = {}
        #: alvo -> (label do digito, label do rotulo, cor da classe). Existe
        #: por causa de set_enabled_targets: os dois textos sao QLabel
        #: filhos, e QLabel nao herda o estado desabilitado do QPushButton
        #: pai -- sem repintar aqui, a fila vazia deixava tres alvos mortos
        #: com o texto ainda em cor cheia.
        self._textos: dict[_Alvo, tuple[QLabel, QLabel, str]] = {}
        #: None ate a primeira chamada de set_enabled_targets. Evita repintar
        #: os 3 alvos (6 QLabel.setStyleSheet) a cada tecla de navegacao
        #: (pular/voltar chamam isto a cada seta, mesmo com a fila cheia o
        #: tempo todo) quando o estado habilitado/desabilitado nao mudou.
        self._habilitados: bool | None = None
        for indice, rotulo in enumerate(LABELS_EM_ORDEM):
            alvo = self._alvo(str(indice + 1), rotulo)
            self._alvos[rotulo] = alvo
            layout.addWidget(alvo)

        # Respiro grande entre os alvos e a legenda: sao duas coisas
        # diferentes (o que se pode fazer agora vs. o que mais existe), e
        # com o espaco padrao o "espaco" cola no alvo "3 +1" e le como um
        # quarto botao.
        layout.addSpacing(SPACE_8)
        layout.addWidget(self._divisor())
        layout.addSpacing(SPACE_3)
        for tecla, acao in _ATALHOS:
            layout.addWidget(self._atalho(tecla, acao))
        layout.addStretch(1)

        self.botao_bloco = QPushButton()
        # Sans em caixa baixa, ao contrario de todo outro botao do app: este
        # nao e um rotulo curto de painel, e uma frase com um numero dentro
        # ("Aprovar em bloco (confianca >= 0.75)"). Em mono de 10px com
        # tracking widest ela virava uma faixa de 340px berrando no canto,
        # com mais peso visual que os tres alvos que sao a acao principal.
        self.botao_bloco.setFixedHeight(SIZE_CONTROL_BASE)
        self.botao_bloco.setStyleSheet(
            f"border: 1px solid {COLOR_BORDER_STRONG};"
            f"border-radius: {RADIUS_SM}px;"
            f"padding: 0px {SPACE_5}px;"
            f"font-family: {FONT_FAMILY_SANS}; font-size: {FONT_SIZE_SMALL};"
            # min-height explicito descontando a borda (1px em cima e
            # embaixo) -- mesmo motivo do botao Escanear em window.py: sem
            # isto o min-height:28px do QPushButton generico do app.qss
            # soma com a borda no polish() e a altura real vira 30px, nao
            # os 28 que setFixedHeight pediu.
            f"min-height: {SIZE_CONTROL_BASE - 2}px;"
        )
        self.botao_bloco.clicked.connect(self.bloco_pedido)
        layout.addWidget(self.botao_bloco)

    def _alvo(self, digito: str, rotulo: str) -> _Alvo:
        """Digito em cor de texto, rotulo na cor da classe -- lado a lado.

        Os dois num QPushButton com texto so nao dava: `color` no QSS veste
        a string inteira, e o digito saia da mesma cor da classe. Pintar
        so o rotulo e o que faz o "1" ler como TECLA e o "-1" como CLASSE.
        Os QLabel sao transparentes ao mouse para o clique continuar sendo
        do botao.
        """
        _, cor = classification_colors(_CLASSE[rotulo])
        alvo = _Alvo()
        alvo.setFixedHeight(_ALTURA_ALVO)
        alvo.setCursor(Qt.CursorShape.PointingHandCursor)
        # O botao nao tem text(): o conteudo vive em dois QLabel filhos (ver
        # docstring do metodo). Sem accessibleName explicito, um leitor de
        # tela nao anuncia nada para o alvo principal de decisao da tela.
        alvo.setAccessibleName(f"{digito}  {rotulo}")

        caixa = QHBoxLayout(alvo)
        caixa.setContentsMargins(SPACE_6, 0, SPACE_6, 0)
        caixa.setSpacing(SPACE_4)

        texto_digito = QLabel(digito)
        texto_digito.setStyleSheet(
            f"font-family: {FONT_FAMILY_MONO}; font-size: {FONT_SIZE_LARGE};"
            f"font-weight: {FONT_WEIGHT_MEDIUM};"
        )

        texto_rotulo = QLabel(rotulo)
        texto_rotulo.setStyleSheet(
            f"font-family: {FONT_FAMILY_MONO}; font-size: {FONT_SIZE_CAPTION};"
        )
        aplica_tracking(texto_rotulo, FONT_TRACKING_WIDE)

        for texto in (texto_digito, texto_rotulo):
            texto.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            caixa.addWidget(texto)

        self._textos[alvo] = (texto_digito, texto_rotulo, cor)
        # Habilitado por padrao: a fila so se sabe vazia depois do primeiro
        # set_state do servico, e ate la um alvo com aparencia de
        # desabilitado mentiria sobre um estado que ainda nao existe.
        self._pinta_alvo(alvo, habilitados=True)
        alvo.clicked.connect(lambda _=False, r=rotulo: self.decidido.emit(r))
        return alvo

    def _pinta_alvo(self, alvo: _Alvo, *, habilitados: bool) -> None:
        """Cor do texto E da borda, nas duas cores certas para o estado.

        `alvo.setStyleSheet()` e uma folha de INSTANCIA: ela vence qualquer
        regra `QPushButton:disabled` do app.qss para as propriedades que
        declara, mesmo com pseudo-classe mais especifica do lado do app --
        e a folha do app.qss so declara `border-color`, nao `border` inteiro,
        entao um `border` daqui sem a variante desabilitada deixava a
        moldura sempre na cor "clicavel" (COLOR_BORDER_STRONG), mesmo com o
        alvo desabilitado e o texto ja apagado. Repintar a borda aqui, junto
        do texto, e o que fecha os dois estados.
        """
        cor_borda = COLOR_BORDER_STRONG if habilitados else COLOR_BORDER_SUBTLE
        alvo.setStyleSheet(
            f"border: 1px solid {cor_borda}; border-radius: {RADIUS_SM}px; padding: 0px;"
        )
        texto_digito, texto_rotulo, cor = self._textos[alvo]
        texto_digito.setStyleSheet(
            f"font-family: {FONT_FAMILY_MONO}; font-size: {FONT_SIZE_LARGE};"
            f"font-weight: {FONT_WEIGHT_MEDIUM};"
            f"color: {COLOR_TEXT_PRIMARY if habilitados else COLOR_TEXT_DISABLED};"
        )
        texto_rotulo.setStyleSheet(
            f"font-family: {FONT_FAMILY_MONO}; font-size: {FONT_SIZE_CAPTION};"
            f"color: {cor if habilitados else COLOR_TEXT_DISABLED};"
        )

    def _divisor(self) -> QFrame:
        """Fio vertical entre os alvos e a legenda: um separa o que se
        clica do que so se le."""
        linha = QFrame()
        linha.setFrameShape(QFrame.Shape.VLine)
        linha.setFixedSize(1, SPACE_7)
        linha.setStyleSheet(f"background: {COLOR_BORDER_DEFAULT}; border: none;")
        return linha

    def _atalho(self, tecla: str, acao: str) -> QLabel:
        """Uma linha so por atalho, em micro-label muted.

        Era um bloco de dois andares com a tecla em cima do verbo. Tres
        deles em sequencia desenhavam tres caixas do tamanho dos alvos ao
        lado -- e o rodape passava a ter seis botoes aparentes, dos quais
        so tres clicavam. Legenda e texto, nao controle.
        """
        rotulo = QLabel()
        rotulo.setObjectName("MicroLabel")
        estiliza_label(rotulo, f"{tecla} {acao}")
        # Margem propria: sem ela as tres legendas encostam umas nas outras
        # e leem como uma frase so.
        rotulo.setContentsMargins(SPACE_3, 0, SPACE_3, 0)
        return rotulo

    def set_bulk_label(self, limiar: float) -> None:
        # "≥" e nao ">=": o simbolo e o do mockup, e a regra de portugues sem
        # acento do repositorio e sobre diacritico, nao sobre operador
        # matematico. A caixa de confirmacao continua com ">=" -- ali o texto
        # e frase, nao rotulo de instrumento.
        self.botao_bloco.setText(f"Aprovar em bloco (confianca ≥ {limiar})")

    def set_enabled_targets(self, habilitados: bool) -> None:
        """Fila vazia desabilita os tres alvos -- nao ha o que classificar.

        Modelo nao treinado NAO desabilita: classificar e justamente o que
        treina, e travar os alvos ali criaria um impasse.
        """
        if habilitados == self._habilitados:
            # pular()/voltar() (setas) chamam isto a cada tecla mesmo sem a
            # fila mudar de vazia para nao-vazia -- sem este guard, cada
            # seta refazia 3 stylesheets de borda + 6 de QLabel a toa.
            return
        self._habilitados = habilitados
        for alvo in self._alvos.values():
            alvo.setEnabled(habilitados)
            self._pinta_alvo(alvo, habilitados=habilitados)
