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
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from ..config import (
    NOMES_DE_PASTA,
    SettingsDraft,
    SettingsError,
    validate_settings,
)
from ..labels import LABEL_ORDER
from .counts_worker import ContadorEmSegundoPlano
from .tokens import (
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
    SPACE_7,
)
from .widgets import (
    RootModeCard,
    SettingsField,
    ajuda,
    cabecalho,
    coluna_numerica,
    cria_campo_numerico,
    secao_painel,
)

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

#: Espera antes de mandar contar. Contar e I/O e o campo revalida a cada
#: tecla: sem isto, digitar um caminho de 40 caracteres dispara 40 varreduras
#: de pasta.
DEBOUNCE_MS = 300


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

        self._valido = False
        self._campos: dict[str, SettingsField] = {}

        self._contador = ContadorEmSegundoPlano(self, contar=contar)
        self._contador.pronto.connect(self.set_counts)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._pede_contagem)

        for chave in ("inbox", "root", "up", "neutral", "down", "data_dir"):
            self._campos[chave] = SettingsField(chave, escolher_pasta)
            self._campos[chave].changed.connect(self._revalida)

        self._modo_raiz = QCheckBox("Nao tenho as pastas ainda - criar a estrutura para mim")
        self._modo_raiz.toggled.connect(self._alterna_modo)

        self._ajuda_raiz = ajuda(
            "Serão criadas as subpastas "
            + ", ".join(NOMES_DE_PASTA.values())
            + " dentro da pasta escolhida."
        )

        self._retrain = cria_campo_numerico()
        self._min_exemplos = cria_campo_numerico()

        self._retrain.valueChanged.connect(self._revalida)
        self._min_exemplos.valueChanged.connect(self._revalida)

        # Campo de nome do perfil. Texto curto, validado para unicidade em
        # SettingsTab antes de salvar -- aqui so captura o input.
        self._nome = QLineEdit()
        self._nome.setObjectName("FieldName")
        self._nome.setPlaceholderText("Nome do perfil")
        self._nome.textChanged.connect(self._revalida)

        # Card do modo raiz
        self._root_card = RootModeCard(self._modo_raiz, self._ajuda_raiz, self._campos["root"])

        # Grupo dos tres destinos
        self._grupo_destinos = QWidget()
        coluna = QVBoxLayout(self._grupo_destinos)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(SPACE_5)
        # LABEL_ORDER, nao a ordem das chaves da config: -1, neutra, +1 e a
        # escala ordinal do dominio, a mesma das teclas 1/2/3.
        for rotulo in LABEL_ORDER:
            chave = next(k for k, v in NOMES_DE_PASTA.items() if v == rotulo.value)
            coluna.addWidget(self._campos[chave])

        self._ajuda_destinos = ajuda(
            "Trocar um destino não move o que já foi classificado: o próximo "
            "scan apenas passa a ler de outro lugar."
        )

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
            secao_painel(
                cabecalho("Perfil"),
                self._nome,
                cabecalho("Entrada"),
                ajuda(
                    "Classificar MOVE o arquivo: ele sai da entrada e vai para a pasta "
                    "do rótulo escolhido. Não é cópia."
                ),
                self._campos["inbox"],
                espaco=SPACE_4,
            )
        )

    def _monta_destinos(self, layout: QVBoxLayout) -> None:
        layout.addWidget(
            secao_painel(
                cabecalho("Destinos"),
                self._root_card,
                self._grupo_destinos,
                self._ajuda_destinos,
                espaco=SPACE_4,
            )
        )

    def _monta_dados(self, layout: QVBoxLayout) -> None:
        layout.addWidget(
            secao_painel(
                cabecalho("Dados do app"),
                ajuda("Cache de análises, modelo e capas. Não é pasta de música."),
                self._campos["data_dir"],
                espaco=SPACE_4,
            )
        )

    def _monta_modelo(self, layout: QVBoxLayout) -> None:
        numericos = QHBoxLayout()
        numericos.setContentsMargins(0, 0, 0, 0)
        numericos.setSpacing(SPACE_7)
        numericos.addWidget(coluna_numerica("Retreinar a cada", self._retrain))
        numericos.addWidget(coluna_numerica("Mínimo de exemplos", self._min_exemplos))
        numericos.addStretch(1)

        layout.addWidget(secao_painel(cabecalho("Modelo"), numericos, espaco=SPACE_4))

    # ---- estado --------------------------------------------------------

    def set_draft(self, draft: SettingsDraft) -> None:
        self._nome.setText(draft.name)
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
            name=self._nome.text(),
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
        return self._campos[chave].chip_do_campo()

    def campo_visivel(self, chave: str) -> bool:
        if self._campos[chave].isHidden():
            return False
        if chave in ("up", "neutral", "down"):
            return not self._grupo_destinos.isHidden()
        return True

    # ---- interno -------------------------------------------------------

    def escolher_para_o_teste(self, chave: str) -> None:
        """Aciona o botao Escolher do campo. Existe para o teste chamar o
        mesmo caminho que o clique real percorre."""
        self._campos[chave].escolher()

    def _alterna_modo(self, criar: bool) -> None:
        self._root_card.set_visible_all(criar)
        self._grupo_destinos.setVisible(not criar)
        self._ajuda_destinos.setVisible(not criar)
        self._revalida()

    def _revalida(self) -> None:
        erros = validate_settings(self.draft())
        valido = not erros
        if valido != self._valido:
            self._valido = valido
            self.validity_changed.emit(valido)
        self._debounce.start()

    def _pede_contagem(self) -> None:
        caminhos = {
            chave: campo.texto()
            for chave, campo in self._campos.items()
            if self.campo_visivel(chave)
        }
        self._contador.pedir(caminhos)
