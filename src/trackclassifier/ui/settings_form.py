"""Formulario de configuracao, sem chrome de dialogo.

Um widget so, usado em dois lugares: dentro do FirstRunDialog na primeira
abertura e dentro da aba Configuracao depois. Toda a validacao mora em
config.validate_settings (puro, sem Qt) -- aqui so ha desenho e ligacao de
sinal, que e o que permite testar as regras sem QApplication.

A tela conta o FLUXO do dado, nao lista campos. As quatro secoes estao na
ordem em que o arquivo percorre o app -- entrada, destinos, dados do app,
modelo -- porque o formulario anterior alinhava inbox/up/neutral/down/
data_dir como cinco caminhos equivalentes, e eles nao sao: quatro sao pasta
de musica, um e cache, e tres RECEBEM ARQUIVO MOVIDO. Classificar chama
apply.move_to_folder; e a operacao mais consequente do app, e a unica coisa
que o formulario antigo nunca dizia.
"""

from collections.abc import Callable

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import NOMES_DE_PASTA, SettingsDraft, SettingsError, validate_settings
from ..labels import LABEL_ORDER
from .counts import NAO_ENCONTRADA
from .counts_worker import ContadorEmSegundoPlano
from .tokens import (
    FONT_TRACKING_WIDE,
    SIZE_CONTROL_BASE,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
    SPACE_7,
    classification_base,
)
from .typography import aplica_tracking, estiliza_label, repolir, texto_de_label

#: Rotulo do campo na tela. Os destinos usam o vocabulario do dominio
#: (-1 / neutra / +1, os mesmos das teclas 1/2/3 e do chip da lista), nunca
#: as chaves da config (down/neutral/up) -- essas chaves nao aparecem em
#: nenhuma outra tela do app.
_TITULOS = {
    "inbox": "Pasta de entrada",
    "root": "Criar a estrutura em",
    "up": "+1",
    "neutral": "neutra",
    "down": "-1",
    "data_dir": "Pasta de dados do app",
}

#: Titulo da janela do seletor de pasta. Separado de _TITULOS porque abrir
#: uma janela chamada "-1" nao diz nada.
_TITULOS_DE_DIALOGO = {
    "inbox": "Escolha a pasta de entrada",
    "root": "Escolha onde criar a estrutura",
    "up": "Escolha a pasta do destino +1",
    "neutral": "Escolha a pasta do destino neutra",
    "down": "Escolha a pasta do destino -1",
    "data_dir": "Escolha a pasta de dados do app",
}

#: Familia de cor de classificacao por chave de destino -- a mesma que o
#: chip da lista e os alvos da Revisao usam. E o que faz o mapeamento
#: pasta<->classe se explicar sozinho.
_CLASSE_DO_DESTINO = {"up": "animada", "neutral": "neutro", "down": "lento"}

#: Lado do ponto de cor da classe.
_PONTO = 7

#: Largura maxima da coluna de conteudo. O formulario e uma coluna de
#: leitura, nao uma tabela: esticado na largura da janela, o campo de
#: caminho vira uma regua de 1500px e o par rotulo/chip se afasta tanto que
#: deixa de ser par -- o chip "128 NOVAS" fica no outro extremo da tela do
#: rotulo que ele conta.
LARGURA_MAXIMA = 760

#: Distancia entre secoes. Nao ha token de 18: e space.5 mais space.3, a
#: mesma soma que separa os blocos no mockup. O espacamento DENTRO de uma
#: secao e space.4 -- e a diferenca entre os dois que faz cabecalho, ajuda
#: e campos lerem como um bloco so.
_ENTRE_SECOES = SPACE_5 + SPACE_3

#: Largura dos dois campos numericos da secao Modelo. Um numero de ate
#: quatro digitos com as setas do spin: esticar ate a coluna inteira daria
#: 700px de caixa para "10".
_LARGURA_NUMERICO = 96

#: Espera antes de mandar contar. Contar e I/O e o campo revalida a cada
#: tecla: sem isto, digitar um caminho de 40 caracteres dispara 40 varreduras
#: de pasta.
DEBOUNCE_MS = 300


class _CampoDePasta(QWidget):
    """Uma linha do formulario, com tudo que pertence ao campo.

    Rotulo, ponto de cor da classe, chip de contagem, campo, botao e erro
    moram no MESMO widget de proposito: esconder o modo raiz passa a ser
    setVisible() nesta linha, sem o QFormLayout.setRowVisible que a versao
    anterior precisava para nao deixar o rotulo orfao na tela.
    """

    changed = Signal()

    def __init__(self, chave: str, escolher_pasta, parent=None) -> None:
        super().__init__(parent)
        self.chave = chave
        self._escolher_pasta = escolher_pasta

        self.rotulo = _rotulo_de_campo(_TITULOS[chave])
        classe = _CLASSE_DO_DESTINO.get(chave)
        if classe is not None:
            # Cor vinda do token, nunca de um literal: o ponto e o rotulo
            # do destino carregam exatamente a cor que a track vai receber
            # como chip depois de classificada.
            cor = classification_base(classe)
            self.rotulo.setStyleSheet(f"color: {cor};")
            self.ponto = QLabel()
            self.ponto.setFixedSize(_PONTO, _PONTO)
            self.ponto.setStyleSheet(f"background: {cor}; border-radius: {_PONTO // 2}px;")
        else:
            self.ponto = None

        self.chip = QLabel("")
        self.chip.setObjectName("Chip")
        aplica_tracking(self.chip, FONT_TRACKING_WIDE)
        self.chip.setVisible(False)

        self.campo = QLineEdit()
        # objectName e altura fixa porque o par campo/botao precisa fechar na
        # MESMA altura de controle, e nenhum dos dois chega la sozinho: o
        # `min-height` do Qt Style Sheets e caixa de CONTEUDO, entao ele SOMA
        # com padding e borda -- o QPushButton generico (min-height 28 mais
        # 6px de padding em cima e embaixo mais 1px de borda) media 42px na
        # tela ao lado de um QLineEdit que, sem min-height nenhum, media ~31.
        # Aqui a altura total e fixada em codigo e o QSS zera o padding
        # vertical desses dois objectName (ver design/build_tokens.py).
        self.campo.setObjectName("FieldPath")
        self.campo.setFixedHeight(SIZE_CONTROL_BASE)
        self.campo.textChanged.connect(self.changed)

        botao = QPushButton()
        botao.setObjectName("FieldBrowse")
        botao.setFixedHeight(SIZE_CONTROL_BASE)
        estiliza_label(botao, "Escolher")
        # Contorno neutro, nao a variante de acento: ha um botao destes por
        # campo, e seis botoes laranja na mesma tela anulariam o acento.
        botao.clicked.connect(self.escolher)

        self._erro = QLabel("")
        self._erro.setObjectName("FieldError")
        self._erro.setVisible(False)

        topo = QHBoxLayout()
        topo.setContentsMargins(0, 0, 0, 0)
        topo.setSpacing(SPACE_3)
        if self.ponto is not None:
            topo.addWidget(self.ponto)
        topo.addWidget(self.rotulo)
        topo.addStretch(1)
        topo.addWidget(self.chip)

        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(SPACE_2)
        linha.addWidget(self.campo, 1)
        linha.addWidget(botao)

        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(SPACE_2)
        fora.addLayout(topo)
        fora.addLayout(linha)
        fora.addWidget(self._erro)

    def escolher(self) -> None:
        caminho = self._escolher_pasta(_TITULOS_DE_DIALOGO[self.chave], self.campo.text())
        if caminho:
            self.campo.setText(caminho)

    def texto(self) -> str:
        return self.campo.text()

    def set_texto(self, valor: str) -> None:
        self.campo.setText(valor)

    def mostra_erro(self, mensagem: str) -> None:
        self._erro.setText(mensagem)
        # setVisible(False) em vez de texto vazio: um QLabel vazio ainda
        # ocupa a altura da linha, e o formulario pularia de altura a cada
        # tecla digitada enquanto o caminho esta incompleto.
        self._erro.setVisible(bool(mensagem))
        # A borda vermelha e propriedade dinamica, nao objectName: o mesmo
        # campo alterna entre valido e invalido a cada tecla, e o Qt so
        # reavalia o seletor depois do unpolish/polish.
        self.campo.setProperty("state", "invalid" if mensagem else "")
        repolir(self.campo)

    def mostra_chip(self, texto: str) -> None:
        # Chip ausente, nunca "carregando": enquanto a contagem nao chegou
        # nao ha nada de verdadeiro para dizer, e um spinner por campo
        # transformaria digitar um caminho num teatro de seis spinners.
        self.chip.setVisible(bool(texto))
        self.chip.setText(texto_de_label(texto))
        self.chip.setProperty("state", "danger" if texto == NAO_ENCONTRADA else "")
        repolir(self.chip)

    def texto_do_chip(self) -> str:
        # Mesma razao de erro(): chip escondido nao esta na tela, entao
        # devolver o texto residual mentiria para quem pergunta.
        return self.chip.text() if not self.chip.isHidden() else ""

    def erro(self) -> str:
        # isHidden() em vez de isVisible(): o formulario nunca recebe show()
        # nos testes (offscreen), e isVisible() so reflete a hierarquia
        # depois de o topo ser mostrado -- o mesmo caso de campo_visivel em
        # SettingsForm. isHidden() e a flag explicita setada por
        # setVisible/hide, independente do pai.
        return self._erro.text() if not self._erro.isHidden() else ""


def _abre_dialogo_de_pasta(titulo: str, atual: str) -> str:
    return QFileDialog.getExistingDirectory(None, titulo, atual)


def _cabecalho(texto: str) -> QLabel:
    rotulo = QLabel()
    rotulo.setObjectName("SectionHeader")
    estiliza_label(rotulo, texto)
    return rotulo


def _ajuda(texto: str) -> QLabel:
    rotulo = QLabel(texto)
    rotulo.setObjectName("Hint")
    rotulo.setWordWrap(True)
    return rotulo


def _rotulo_de_campo(texto: str) -> QLabel:
    """Rotulo de um campo: caption em texto secundario.

    Um degrau abaixo do texto do proprio campo de proposito -- o valor
    (o caminho) e o que se le na tela; o rotulo so diz de que caminho se
    trata. Os destinos sobrescrevem a cor com a da classe, pelo estilo
    inline, e herdam so o tamanho daqui.
    """
    rotulo = QLabel(texto)
    rotulo.setObjectName("FieldLabel")
    return rotulo


def _campo_numerico() -> QSpinBox:
    """Spin de largura fixa, na mesma altura de controle do resto da tela.

    Mesma razao de _CampoDePasta: `min-height` no QSS soma com o padding, e
    sem a altura fixa o spin fica mais alto que o campo de caminho logo
    acima dele.
    """
    campo = QSpinBox()
    campo.setObjectName("FieldNumber")
    campo.setRange(1, 1000)
    campo.setFixedSize(_LARGURA_NUMERICO, SIZE_CONTROL_BASE)
    return campo


def _coluna_numerica(titulo: str, campo: QSpinBox) -> QWidget:
    """Rotulo em cima, campo embaixo -- a mesma forma de _CampoDePasta."""
    caixa = QWidget()
    dentro = QVBoxLayout(caixa)
    dentro.setContentsMargins(0, 0, 0, 0)
    dentro.setSpacing(SPACE_2)
    dentro.addWidget(_rotulo_de_campo(titulo))
    dentro.addWidget(campo)
    return caixa


def _secao(*itens) -> QWidget:
    """Agrupa cabecalho, ajuda e campos de uma secao num widget so.

    O espacamento interno (space.4) e menor que o de entre secoes
    (_ENTRE_SECOES): com um valor unico para os dois, tudo fica a mesma
    distancia de tudo e o formulario vira uma lista plana de doze widgets
    em vez de quatro blocos.
    """
    caixa = QWidget()
    dentro = QVBoxLayout(caixa)
    dentro.setContentsMargins(0, 0, 0, 0)
    dentro.setSpacing(SPACE_4)
    for item in itens:
        if isinstance(item, QLayout):
            dentro.addLayout(item)
        else:
            dentro.addWidget(item)
    return caixa


class SettingsForm(QWidget):
    #: Emitido quando o formulario passa a ser, ou deixa de ser, valido.
    validity_changed = Signal(bool)

    def __init__(
        self,
        escolher_pasta: Callable[[str, str], str] | None = None,
        contar: Callable[[dict[str, str]], dict[str, str]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # Injetavel por causa do teste: QFileDialog.getExistingDirectory abre
        # uma janela modal nativa e travaria a suite. Com o callable injetado
        # da para exercitar o botao "Escolher" pelo caminho real do widget.
        escolher = escolher_pasta or _abre_dialogo_de_pasta

        self._valido = False
        self._campos: dict[str, _CampoDePasta] = {}

        self._contador = ContadorEmSegundoPlano(self, contar=contar)
        self._contador.pronto.connect(self.set_counts)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._pede_contagem)

        for chave in ("inbox", "root", "up", "neutral", "down", "data_dir"):
            self._campos[chave] = _CampoDePasta(chave, escolher)

        self._modo_raiz = QCheckBox("Nao tenho as pastas ainda - criar a estrutura para mim")
        self._modo_raiz.toggled.connect(self._alterna_modo)

        self._ajuda_raiz = _ajuda(
            "Serão criadas as subpastas "
            + ", ".join(NOMES_DE_PASTA.values())
            + " dentro da pasta escolhida."
        )

        self._retrain = _campo_numerico()
        self._min_exemplos = _campo_numerico()

        for campo in self._campos.values():
            campo.changed.connect(self._revalida)
        self._retrain.valueChanged.connect(self._revalida)
        self._min_exemplos.valueChanged.connect(self._revalida)

        # Teto de largura, nao largura fixa: numa janela estreita a coluna
        # encolhe junto; numa larga ela para de crescer e o formulario fica
        # ancorado a esquerda, como no mockup.
        self.setMaximumWidth(LARGURA_MAXIMA)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(_ENTRE_SECOES)
        self._monta_entrada(layout)
        self._monta_destinos(layout)
        self._monta_dados(layout)
        self._monta_modelo(layout)
        layout.addStretch(1)

        self._alterna_modo(False)

    # ---- montagem ------------------------------------------------------

    def _monta_entrada(self, layout: QVBoxLayout) -> None:
        layout.addWidget(
            _secao(
                _cabecalho("Entrada"),
                # A frase que o formulario anterior nunca dava, no lugar em
                # que ela muda uma decisao: antes de apontar as pastas.
                _ajuda(
                    "Classificar MOVE o arquivo: ele sai da entrada e vai para a pasta "
                    "do rótulo escolhido. Não é cópia."
                ),
                self._campos["inbox"],
            )
        )

    def _monta_destinos(self, layout: QVBoxLayout) -> None:
        # O modo raiz num card com borda de acento, nao numa linha solta no
        # meio do formulario: e o caminho feliz de quem nunca usou o app, e
        # decide se os tres campos abaixo aparecem ou nao.
        card = QFrame()
        card.setObjectName("Card")
        card.setProperty("accent", "true")
        dentro = QVBoxLayout(card)
        dentro.setContentsMargins(SPACE_5, SPACE_5, SPACE_5, SPACE_5)
        dentro.setSpacing(SPACE_4)
        dentro.addWidget(self._modo_raiz)
        dentro.addWidget(self._ajuda_raiz)
        dentro.addWidget(self._campos["root"])

        # Os tres destinos num container proprio, e nao soltos na secao: o
        # modo raiz esconde os tres de uma vez, e um container escondido
        # tambem leva embora o espacamento em volta dele -- tres widgets
        # escondidos soltos deixariam tres buracos de space.4 na secao.
        self._grupo_destinos = QWidget()
        coluna = QVBoxLayout(self._grupo_destinos)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(SPACE_5)
        # LABEL_ORDER, nao a ordem das chaves da config: -1, neutra, +1 e a
        # escala ordinal do dominio, a mesma das teclas 1/2/3.
        for rotulo in LABEL_ORDER:
            chave = next(k for k, v in NOMES_DE_PASTA.items() if v == rotulo.value)
            coluna.addWidget(self._campos[chave])

        self._ajuda_destinos = _ajuda(
            "Trocar um destino não move o que já foi classificado: o próximo "
            "scan apenas passa a ler de outro lugar."
        )

        layout.addWidget(
            _secao(
                _cabecalho("Destinos"),
                card,
                self._grupo_destinos,
                self._ajuda_destinos,
            )
        )

    def _monta_dados(self, layout: QVBoxLayout) -> None:
        layout.addWidget(
            _secao(
                _cabecalho("Dados do app"),
                _ajuda("Cache de análises, modelo e capas. Não é pasta de música."),
                self._campos["data_dir"],
            )
        )

    def _monta_modelo(self, layout: QVBoxLayout) -> None:
        # Duas colunas lado a lado com o rotulo EM CIMA do campo, e nao um
        # QFormLayout: o QFormLayout alinha o rotulo a direita e estica o
        # spin ate o fim da linha, o que jogava "Retreinar a cada" para o
        # meio da tela e deixava as duas caixas na borda oposta. Aqui os
        # dois campos ficam onde o olho ja esta -- na margem esquerda, junto
        # com todos os outros rotulos da tela.
        numericos = QHBoxLayout()
        numericos.setContentsMargins(0, 0, 0, 0)
        numericos.setSpacing(SPACE_7)
        numericos.addWidget(_coluna_numerica("Retreinar a cada", self._retrain))
        numericos.addWidget(_coluna_numerica("Mínimo de exemplos", self._min_exemplos))
        numericos.addStretch(1)

        layout.addWidget(_secao(_cabecalho("Modelo"), numericos))

    # ---- estado --------------------------------------------------------

    def set_draft(self, draft: SettingsDraft) -> None:
        self._modo_raiz.setChecked(draft.create_under_root)
        for chave in ("inbox", "root", "up", "neutral", "down", "data_dir"):
            self._campos[chave].set_texto(getattr(draft, chave))
        self._retrain.setValue(draft.retrain_every)
        self._min_exemplos.setValue(draft.min_examples)
        self._revalida()

    def draft(self) -> SettingsDraft:
        return SettingsDraft(
            inbox=self._campos["inbox"].texto(),
            up=self._campos["up"].texto(),
            neutral=self._campos["neutral"].texto(),
            down=self._campos["down"].texto(),
            data_dir=self._campos["data_dir"].texto(),
            retrain_every=self._retrain.value(),
            min_examples=self._min_exemplos.value(),
            create_under_root=self._modo_raiz.isChecked(),
            root=self._campos["root"].texto(),
        )

    def is_valid(self) -> bool:
        return self._valido

    # ---- erros e chips -------------------------------------------------

    def show_errors(self, erros: list[SettingsError]) -> None:
        por_campo = {erro.field: erro.message for erro in erros}
        for chave, campo in self._campos.items():
            campo.mostra_erro(por_campo.get(chave, ""))

    def erro_do_campo(self, chave: str) -> str:
        return self._campos[chave].erro()

    def set_counts(self, contagens: dict) -> None:
        for chave, texto in contagens.items():
            campo = self._campos.get(chave)
            if campo is not None:
                campo.mostra_chip(texto)

    def chip_do_campo(self, chave: str) -> str:
        return self._campos[chave].texto_do_chip()

    def campo_visivel(self, chave: str) -> bool:
        # isHidden() em vez de isVisible(): o widget nunca recebe show() nos
        # testes (offscreen), e isVisible() so reflete a hierarquia depois
        # de o topo ser mostrado -- setVisible(True) num filho nao basta.
        # isHidden() e o estado explicito setado por setVisible/hide, o que
        # e o que _alterna_modo de fato controla.
        return not self._campos[chave].isHidden()

    # ---- interno -------------------------------------------------------

    def escolher_para_o_teste(self, chave: str) -> None:
        """Aciona o botao Escolher do campo. Existe para o teste chamar o
        mesmo caminho que o clique real percorre."""
        self._campos[chave].escolher()

    def _alterna_modo(self, criar: bool) -> None:
        # Uma chamada por linha, e nada de setRowVisible: rotulo, ponto,
        # chip e erro moram dentro do proprio _CampoDePasta, entao esconder
        # a linha esconde tudo que pertence a ela. Era esse acoplamento com
        # o QFormLayout que deixava o rotulo orfao na tela.
        self._campos["root"].setVisible(criar)
        self._ajuda_raiz.setVisible(criar)
        # O container E cada campo: esconder so o container tiraria os tres
        # da tela, mas campo_visivel() -- que decide o que vai para a
        # contagem -- le a flag do proprio campo, e um filho de um pai
        # escondido continua com isHidden() False.
        self._grupo_destinos.setVisible(not criar)
        for chave in ("up", "neutral", "down"):
            self._campos[chave].setVisible(not criar)
        self._ajuda_destinos.setVisible(not criar)
        self._revalida()

    def _revalida(self) -> None:
        erros = validate_settings(self.draft())
        valido = not erros
        if valido != self._valido:
            self._valido = valido
            self.validity_changed.emit(valido)
        # start() num QTimer ja rodando reinicia a contagem: digitar rapido
        # dispara uma varredura so, no fim da digitacao.
        self._debounce.start()

    def _pede_contagem(self) -> None:
        caminhos = {
            chave: campo.texto()
            for chave, campo in self._campos.items()
            if self.campo_visivel(chave)
        }
        self._contador.pedir(caminhos)
