"""Aba Modelo: metricas, matriz, balanco, retreino e falhas de analise.

A aba tem o melhor dado do app -- acuracia leave-one-out, erro ordinal,
matriz calibrada -- e ate a v0.2 despejava tudo em dois QLabel alinhados
por f"{valor:>8}". O redesenho nao adiciona calculo nenhum: expoe tres
coisas que ja existiam no servico e nunca chegavam a tela (o balanco de
classes, o progresso ate o retreino automatico e o motivo de o retreino
estar indisponivel) e da forma ao que ja aparecia.

O desenho de cada bloco mora num widget proprio em widgets/; aqui fica o
layout e a traducao de ModelState. Tres cards com pintura propria num
arquivo so devolveriam este modulo ao tamanho de settings_form.py.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .layouts import secao
from .surface import aplica_superficie
from .tokens import (
    COLOR_STATE_DANGER,
    COLOR_SURFACE_1,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SECONDARY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    RADIUS_SM,
    SPACE_2,
    SPACE_3,
    SPACE_5,
    SPACE_6,
)
from .typography import estiliza_label, texto_de_label
from .viewmodel import ModelState
from .widgets.class_balance import ClassBalance
from .widgets.confusion_matrix import ConfusionMatrix
from .widgets.empty_state import Acao, EmptyState
from .widgets.failure_list import FailureList
from .widgets.meter import Meter
from .widgets.tech_detail import TechDetail

#: Larguras fixas da primeira faixa. A matriz fica no meio com flex: e a
#: unica que ganha em ser larga -- metricas e balanco sao listas curtas.
_LARGURA_METRICAS = 280
_LARGURA_BALANCO = 300
_ALTURA_TRILHO = 3
#: Teto do trilho de progresso, do mockup. Mesmo motivo do medidor de
#: confianca da Revisao (guess_bar._LARGURA_TRILHO): esticado pela largura
#: da janela, um filete de 3px atravessando 700px le como regua divisoria
#: da faixa, nao como a barra que o rotulo logo abaixo esta explicando.
_LARGURA_CONTADOR = 340
_PADDING_CARD = (16, 14, 16, 14)
#: A faixa de acao e mais rasa que um card de dado: ela tem uma linha so.
_PADDING_FAIXA = (16, 12, 16, 12)


def _card(
    *, largura: int | None = None, padding: tuple[int, int, int, int] = _PADDING_CARD
) -> tuple[QWidget, QVBoxLayout]:
    """Superficie de card da v0.2. Devolve (widget, layout) porque quem
    chama sempre precisa dos dois e buscar o layout depois e ruido."""
    widget = QWidget()
    aplica_superficie(widget, COLOR_SURFACE_1, RADIUS_SM)
    if largura is not None:
        widget.setFixedWidth(largura)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(*padding)
    layout.setSpacing(SPACE_5)
    return widget, layout


class ModelTab(QWidget):
    train_requested = Signal()
    #: Pedido de ir para a aba Revisao. A aba nao troca de aba sozinha: quem
    #: e dona do QTabWidget e a MainWindow, e um widget que mexe no pai
    #: acopla os dois na direcao errada.
    review_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        faixa_cards = QHBoxLayout()
        faixa_cards.setSpacing(SPACE_5)
        faixa_cards.addWidget(self._card_metricas())
        faixa_cards.addWidget(self._card_matriz(), 1)
        faixa_cards.addWidget(self._card_balanco())

        # Fora de _conteudo de proposito. FailureList e a UNICA superficie do
        # app inteiro que mostra service.failures() (nenhum outro lugar em
        # src/trackclassifier/ui exibe falha de scan) -- se ela morasse
        # dentro de _conteudo, o early-return de set_state para n_examples==0
        # a esconderia junto com os cards de metrica, e uma biblioteca fresca
        # que acabou de escanear (zero exemplos rotulados ainda, mas com
        # ffmpeg faltando ou arquivos corrompidos) nao teria NENHUM jeito de
        # o usuario descobrir o que falhou -- violando o proprio invariante
        # do repo de que erro de borda "degrada e reporta", nunca so degrada
        # em silencio. set_failures() com tupla vazia esconde o widget
        # sozinho (FailureList.set_failures), entao mante-lo sempre visivel
        # aqui nao pinta nada quando nao ha falha.
        self.falhas = FailureList()
        self.detalhe = TechDetail()

        # Tudo que so faz sentido com exemplo rotulado vira um widget so --
        # mesmo movimento de ReviewTab._bloco. Com zero exemplos, tres cards
        # zerados nao informam nada: so ocupam a tela com estrutura vazia.
        self._conteudo = QWidget()
        interno = QVBoxLayout(self._conteudo)
        interno.setContentsMargins(0, 0, 0, 0)
        interno.setSpacing(SPACE_5)
        interno.addLayout(faixa_cards)
        interno.addWidget(self._faixa_acao())

        self._vazio = EmptyState(
            "Nenhum exemplo rotulado",
            "Classifique tracks na Revisao para o modelo ter o que aprender.",
            # Neutro, e nao acento: a acao principal desta tela e retreinar,
            # e o botao de acento ja e dela. Aqui o botao so aponta o
            # caminho -- o trabalho acontece na outra aba.
            (Acao("Ir para a revisao", "base"),),
        )
        self._vazio.acao_clicada.connect(lambda _rotulo: self.review_requested.emit())
        self._vazio.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        # _vazio ganha o stretch: e ele quem precisa se centrar no espaco
        # sobrando quando a aba abre sem exemplo nenhum. _conteudo fica sem
        # stretch de proposito -- ver o addStretch(1) abaixo, que e quem
        # absorve a sobra quando HA exemplo.
        layout.addWidget(self._vazio, 1)
        layout.addWidget(self._conteudo)
        layout.addWidget(self.falhas)
        # A sobra de altura vai para este stretch, nao para os cards nem
        # para a lista de falhas: os dois ja mostram tudo o que tem na
        # altura natural, e esticar qualquer um dos dois so afasta o rodape
        # do resto da tela. E o que impede os tres cards do topo de inflar
        # para ~500px quando a secao de falhas some -- _card() nao precisa
        # de QSizePolicy proprio pra isso, e um teria o efeito colateral de
        # tirar dos cards do topo a altura igual que faixa_cards (QHBoxLayout)
        # da de graca.
        layout.addStretch(1)
        layout.addWidget(self.detalhe)

    # --- construcao ---

    def _card_metricas(self) -> QWidget:
        cartao, layout = _card(largura=_LARGURA_METRICAS)

        titulo = QLabel()
        titulo.setObjectName("MicroLabel")
        estiliza_label(titulo, "Metricas")

        self.metricas = QWidget()
        numeros = QVBoxLayout(self.metricas)
        numeros.setContentsMargins(0, 0, 0, 0)
        numeros.setSpacing(SPACE_5)
        self.exemplos = self._linha_metrica(numeros, "Exemplos rotulados")
        self.acuracia = self._linha_metrica(numeros, "Acuracia (leave-one-out)")
        self.erro_ordinal = self._linha_metrica(numeros, "Erro ordinal medio")

        # Duas linhas em dois pesos, nao um paragrafo so: a primeira e o
        # estado ("nao treinado"), a segunda e a consequencia. No mesmo
        # tamanho e na mesma cor, o olho le as duas como um aviso longo e
        # nao acha o estado.
        self.sem_treino = QWidget()
        sem_treino = QVBoxLayout(self.sem_treino)
        sem_treino.setContentsMargins(0, 0, 0, 0)
        sem_treino.setSpacing(SPACE_3)

        estado = QLabel("Modelo ainda nao treinado.")
        estado.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SMALL};"
        )
        consequencia = QLabel(
            "Metricas aparecem depois do primeiro retreino. O balanco e as "
            "falhas ja valem agora."
        )
        consequencia.setWordWrap(True)
        consequencia.setStyleSheet(
            f"color: {COLOR_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION};"
        )
        sem_treino.addWidget(estado)
        sem_treino.addWidget(consequencia)

        layout.addWidget(titulo)
        layout.addWidget(self.metricas)
        layout.addWidget(self.sem_treino)
        layout.addStretch(1)
        return cartao

    def _linha_metrica(self, layout: QVBoxLayout, rotulo: str) -> QLabel:
        """Rotulo a esquerda, numero grande em mono tabular a direita."""
        nome = QLabel(rotulo)
        nome.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};"
        )

        valor = QLabel("")
        valor.setObjectName("Numeric")
        valor.setStyleSheet(f"font-size: {FONT_SIZE_TITLE};")

        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        # Alinhamento pela linha de base, nao pelo centro: 11px ao lado de
        # 18px centralizados deixam o rotulo boiando acima da base do
        # numero, e as tres linhas do card param de formar coluna.
        linha.addWidget(nome, 0, Qt.AlignmentFlag.AlignBaseline)
        linha.addStretch(1)
        linha.addWidget(valor, 0, Qt.AlignmentFlag.AlignBaseline)
        layout.addLayout(linha)
        return valor

    def _card_matriz(self) -> QWidget:
        cartao, layout = _card()
        self.matriz = ConfusionMatrix()
        layout.addWidget(self.matriz)
        return cartao

    def _card_balanco(self) -> QWidget:
        cartao, layout = _card(largura=_LARGURA_BALANCO)
        self.balanco = ClassBalance()
        layout.addWidget(self.balanco)
        return cartao

    def _faixa_acao(self) -> QWidget:
        cartao, layout = _card(padding=_PADDING_FAIXA)
        faixa = QHBoxLayout()
        faixa.setContentsMargins(0, 0, 0, 0)
        faixa.setSpacing(SPACE_6)

        self.botao_retreinar = QPushButton()
        estiliza_label(self.botao_retreinar, "Retreinar")
        self.botao_retreinar.setProperty("variant", "primary")
        self.botao_retreinar.clicked.connect(self.train_requested)

        self.motivo = QLabel("")
        self.motivo.setWordWrap(True)
        self.motivo.setStyleSheet(
            f"color: {COLOR_STATE_DANGER}; font-size: {FONT_SIZE_CAPTION};"
        )

        # Neutro, nao acento: o retreino automatico e um relogio andando,
        # nao a acao que se quer que o usuario tome. O acento ja esta no
        # botao ao lado, que e a acao.
        self._trilho = Meter(COLOR_TEXT_SECONDARY, _ALTURA_TRILHO)
        # O valor do trilho so existe como largura de pixel, e o default do
        # Meter ("Medidor") nao diz de que. Mesmo tratamento do medidor de
        # confianca da Revisao.
        self._trilho.setAccessibleName("Progresso ate o retreino automatico")

        self.progresso = QLabel("")
        self.progresso.setObjectName("MicroLabel")

        # Trilho e rotulo empilhados: o numero explica a barra, e separar
        # os dois em colunas obrigaria o olho a correlacionar.
        self.contador = secao(self._trilho, self.progresso, espaco=SPACE_2)
        self.contador.setMaximumWidth(_LARGURA_CONTADOR)

        self.aviso = QLabel("")
        self.aviso.setObjectName("MicroLabel")
        self.aviso.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        faixa.addWidget(self.botao_retreinar)
        faixa.addWidget(self.motivo)
        faixa.addWidget(self.contador)
        # A sobra da faixa fica entre o contador e o aviso: o aviso e um
        # rodape de canto, e o contador tem largura propria.
        faixa.addStretch(1)
        faixa.addWidget(self.aviso)
        layout.addLayout(faixa)
        return cartao

    # --- estado ---

    def set_state(self, state: ModelState) -> None:
        # n_examples, e nao class_counts: sao a mesma informacao aqui, mas
        # n_examples e o campo que nomeia a condicao ("nenhum exemplo
        # rotulado") e nao depende da ordem das classes.
        vazio = state.n_examples == 0
        self._vazio.setVisible(vazio)
        self._conteudo.setVisible(not vazio)
        # Antes do early-return: falhas de scan nao dependem de haver
        # exemplo rotulado (ver o comentario em __init__ sobre self.falhas
        # ficar fora de _conteudo).
        self.falhas.set_failures(state.failures)
        if vazio:
            # Nada abaixo daqui tem o que mostrar, e set_confusion/
            # set_counts com tudo zerado so repintariam widgets escondidos.
            return

        treinado = state.accuracy is not None
        self.metricas.setVisible(treinado)
        self.sem_treino.setVisible(not treinado)
        if treinado:
            self.exemplos.setText(str(state.n_examples))
            self.acuracia.setText(f"{state.accuracy * 100:.1f}%")
            self.erro_ordinal.setText(f"{state.ordinal_mae:.3f}")

        self.matriz.set_confusion(state.confusion)
        self.balanco.set_counts(state.class_counts)

        bloqueado = state.train_blocked_reason is not None
        self.botao_retreinar.setEnabled(not bloqueado)
        self.motivo.setText(state.train_blocked_reason or "")
        self.motivo.setVisible(bloqueado)
        # O contador promete um retreino automatico que nao acontece
        # enquanto faltar classe -- os dois juntos se contradizem.
        self.contador.setVisible(not bloqueado)
        self.progresso.setText(
            texto_de_label(
                f"{state.decisions_since_train} / {state.retrain_every} "
                "ate o retreino automatico"
            )
        )
        self._atualiza_trilho(state)

        self.aviso.setVisible(state.low_confidence)
        self.aviso.setText(
            texto_de_label("poucos exemplos · acuracia LOO ainda ruidosa")
            if state.low_confidence
            else ""
        )

        self.detalhe.set_detail(state.alpha, state.thresholds, state.extractor_name)

    def _atualiza_trilho(self, state: ModelState) -> None:
        # retrain_every 0 nao existe na config valida, mas um cache antigo
        # pode trazer -- e uma divisao por zero aqui derrubaria a aba.
        if state.retrain_every <= 0:
            self._trilho.set_fraction(0.0)
            return
        self._trilho.set_fraction(state.decisions_since_train / state.retrain_every)

    # ---- superficie de teste --------------------------------------------

    def vazio_visivel(self) -> bool:
        return not self._vazio.isHidden()

    def conteudo_visivel(self) -> bool:
        return not self._conteudo.isHidden()

    def falhas_visivel(self) -> bool:
        return not self.falhas.isHidden()

    def acionar_empty_state(self) -> None:
        self._vazio.acionar("Ir para a revisao")
