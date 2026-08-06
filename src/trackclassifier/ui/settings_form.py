"""Formulario de configuracao, sem chrome de dialogo.

Um widget so, usado em dois lugares: dentro do FirstRunDialog na primeira
abertura e dentro da aba Configuracao depois. Toda a validacao mora em
config.validate_settings (puro, sem Qt) -- aqui so ha desenho e ligacao de
sinal, que e o que permite testar as regras sem QApplication.
"""

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import NOMES_DE_PASTA, SettingsDraft, SettingsError, validate_settings
from .tokens import SPACE_2, SPACE_5, SPACE_6

_TITULOS = {
    "inbox": "Pasta de entrada",
    "root": "Criar a estrutura em",
    "up": "Destino +1",
    "neutral": "Destino neutra",
    "down": "Destino -1",
    "data_dir": "Dados do app",
}


class _CampoDePasta(QWidget):
    """Linha do formulario: campo de texto, botao Escolher e erro embaixo."""

    changed = Signal()

    def __init__(self, chave: str, escolher_pasta, parent=None) -> None:
        super().__init__(parent)
        self.chave = chave
        self._escolher_pasta = escolher_pasta

        self.campo = QLineEdit()
        self.campo.textChanged.connect(self.changed)

        botao = QPushButton("Escolher...")
        botao.clicked.connect(self.escolher)

        self._erro = QLabel("")
        self._erro.setObjectName("FieldError")
        self._erro.setVisible(False)

        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(SPACE_2)
        linha.addWidget(self.campo, 1)
        linha.addWidget(botao)

        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(SPACE_2)
        fora.addLayout(linha)
        fora.addWidget(self._erro)

    def escolher(self) -> None:
        caminho = self._escolher_pasta(_TITULOS[self.chave], self.campo.text())
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

    def erro(self) -> str:
        # isHidden() em vez de isVisible(): o formulario nunca recebe show()
        # nos testes (offscreen), e isVisible() so reflete a hierarquia
        # depois de o topo ser mostrado -- o mesmo caso de campo_visivel em
        # SettingsForm. isHidden() e a flag explicita setada por
        # setVisible/hide, independente do pai.
        return self._erro.text() if not self._erro.isHidden() else ""


def _abre_dialogo_de_pasta(titulo: str, atual: str) -> str:
    return QFileDialog.getExistingDirectory(None, titulo, atual)


class SettingsForm(QWidget):
    #: Emitido quando o formulario passa a ser, ou deixa de ser, valido.
    validity_changed = Signal(bool)

    def __init__(
        self,
        escolher_pasta: Callable[[str, str], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # Injetavel por causa do teste: QFileDialog.getExistingDirectory abre
        # uma janela modal nativa e travaria a suite. Com o callable injetado
        # da para exercitar o botao "Escolher" pelo caminho real do widget.
        escolher = escolher_pasta or _abre_dialogo_de_pasta

        self._valido = False
        self._campos: dict[str, _CampoDePasta] = {}

        self._modo_raiz = QCheckBox("Nao tenho as pastas ainda - criar a estrutura para mim")
        self._modo_raiz.toggled.connect(self._alterna_modo)

        self._ajuda_raiz = QLabel(
            "Serao criadas as subpastas "
            + ", ".join(NOMES_DE_PASTA.values())
            + " dentro da pasta escolhida."
        )
        self._ajuda_raiz.setObjectName("Hint")

        self._retrain = QSpinBox()
        self._retrain.setRange(1, 1000)
        self._min_exemplos = QSpinBox()
        self._min_exemplos.setRange(1, 1000)

        formulario = QFormLayout()
        formulario.setSpacing(SPACE_5)
        for chave in ("inbox",):
            self._campos[chave] = _CampoDePasta(chave, escolher)
            formulario.addRow(_TITULOS[chave], self._campos[chave])

        formulario.addRow("", self._modo_raiz)

        for chave in ("root", "up", "neutral", "down", "data_dir"):
            self._campos[chave] = _CampoDePasta(chave, escolher)
            formulario.addRow(_TITULOS[chave], self._campos[chave])

        formulario.addRow("Retreinar a cada", self._retrain)
        formulario.addRow("Minimo de exemplos", self._min_exemplos)

        for campo in self._campos.values():
            campo.changed.connect(self._revalida)
        self._retrain.valueChanged.connect(self._revalida)
        self._min_exemplos.valueChanged.connect(self._revalida)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addLayout(formulario)
        layout.addWidget(self._ajuda_raiz)
        layout.addStretch(1)

        self._alterna_modo(False)

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

    # ---- erros ---------------------------------------------------------

    def show_errors(self, erros: list[SettingsError]) -> None:
        por_campo = {erro.field: erro.message for erro in erros}
        for chave, campo in self._campos.items():
            campo.mostra_erro(por_campo.get(chave, ""))

    def erro_do_campo(self, chave: str) -> str:
        return self._campos[chave].erro()

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
        self._campos["root"].setVisible(criar)
        self._ajuda_raiz.setVisible(criar)
        for chave in ("up", "neutral", "down"):
            self._campos[chave].setVisible(not criar)
        self._revalida()

    def _revalida(self) -> None:
        erros = validate_settings(self.draft())
        valido = not erros
        if valido != self._valido:
            self._valido = valido
            self.validity_changed.emit(valido)
