"""Widget de campo de configuracao: rotulo, ponto de cor, chip, campo, botao, erro."""

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ..counts import NAO_ENCONTRADA
from ..tokens import FONT_TRACKING_WIDE, SPACE_2, SPACE_3, classification_base
from ..typography import aplica_tracking, estiliza_label, repolir, texto_de_label

_TITULOS = {
    "inbox": "Pasta de entrada",
    "root": "Criar a estrutura em",
    "up": "+1",
    "neutral": "neutra",
    "down": "-1",
    "data_dir": "Pasta de dados do app",
}

_TITULOS_DE_DIALOGO = {
    "inbox": "Escolha a pasta de entrada",
    "root": "Escolha onde criar a estrutura",
    "up": "Escolha a pasta do destino +1",
    "neutral": "Escolha a pasta do destino neutra",
    "down": "Escolha a pasta do destino -1",
    "data_dir": "Escolha a pasta de dados do app",
}

_CLASSE_DO_DESTINO = {"up": "animada", "neutral": "neutro", "down": "lento"}

_PONTO = 7


class SettingsField(QWidget):
    """Uma linha do formulario, com tudo que pertence ao campo.

    Rotulo, ponto de cor da classe, chip de contagem, campo, botao e erro
    moram no MESMO widget de proposito: esconder o modo raiz passa a ser
    setVisible() nesta linha, sem o QFormLayout.setRowVisible que a versao
    anterior precisava para nao deixar o rotulo orfao na tela.
    """

    changed = Signal()

    def __init__(self, chave: str, escolher_pasta: Callable[[str, str], str], parent=None) -> None:
        super().__init__(parent)
        self.chave = chave
        self._escolher_pasta = escolher_pasta

        self.rotulo = _rotulo_de_campo(_TITULOS[chave])
        classe = _CLASSE_DO_DESTINO.get(chave)
        if classe is not None:
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
        self.campo.setObjectName("FieldPath")
        self.campo.textChanged.connect(self._on_text_changed)

        self.botao = QPushButton()
        estiliza_label(self.botao, "Escolher")
        self.botao.clicked.connect(self.escolher)

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
        linha.addWidget(self.botao)

        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(SPACE_2)
        fora.addLayout(topo)
        fora.addLayout(linha)
        fora.addWidget(self._erro)

    def _on_text_changed(self, texto: str) -> None:
        self.changed.emit()

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
        self._erro.setVisible(bool(mensagem))
        self.campo.setProperty("state", "invalid" if mensagem else "")
        repolir(self.campo)

    def mostra_chip(self, texto: str) -> None:
        self.chip.setVisible(bool(texto))
        self.chip.setText(texto_de_label(texto))
        self.chip.setProperty("state", "danger" if texto == NAO_ENCONTRADA else "")
        repolir(self.chip)

    def chip_do_campo(self) -> str:
        return self.chip.text() if not self.chip.isHidden() else ""

    def erro(self) -> str:
        return self._erro.text() if not self._erro.isHidden() else ""


def _rotulo_de_campo(texto: str) -> QLabel:
    rotulo = QLabel(texto)
    rotulo.setObjectName("FieldLabel")
    return rotulo
