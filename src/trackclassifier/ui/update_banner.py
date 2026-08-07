"""Faixa fina no topo da janela avisando que ha versao nova.

Faixa e nao dialogo modal de proposito: descobrir atualizacao e um evento do
app, nao do usuario. Um modal no meio de uma sessao de revisao interrompe o
unico fluxo que o app existe para servir.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget

from .tokens import COLOR_ACCENT_BG, COLOR_ACCENT_TEXT, SPACE_4, SPACE_5
from .typography import estiliza_label


class UpdateBanner(QWidget):
    atualizar_clicado = Signal()
    dispensar_clicado = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UpdateBanner")
        # Cor vem de tokens.py: literal hex em ui/ quebra
        # test_tokens.py::test_nenhum_hex_fora_do_json.
        self.setStyleSheet(
            f"#UpdateBanner {{ background: {COLOR_ACCENT_BG}; }}"
            f"#UpdateBanner QLabel {{ color: {COLOR_ACCENT_TEXT}; }}"
        )
        # O seletor por #UpdateBanner + regra pra QLabel filho nao cabe na
        # assinatura de aplica_superficie (ui/surface.py) -- mas a mesma
        # regra do Qt vale: sem isto, esta subclasse de QWidget nao pinta o
        # `background` sozinha no paint normal.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._texto = QLabel("")
        self._barra = QProgressBar()
        self._barra.setVisible(False)
        self._barra.setMaximumWidth(160)

        self._botao = QPushButton()
        estiliza_label(self._botao, "Atualizar")
        self._botao.setProperty("variant", "primary")
        self._botao.clicked.connect(self.atualizar_clicado)

        self._fechar = QPushButton("✕")
        self._fechar.setProperty("variant", "ghost")
        self._fechar.clicked.connect(self.dispensar_clicado)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_4, SPACE_4, SPACE_4)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self._texto)
        layout.addStretch(1)
        layout.addWidget(self._barra)
        layout.addWidget(self._botao)
        layout.addWidget(self._fechar)

        self.hide()

    def texto(self) -> str:
        return self._texto.text()

    def mostra(self, versao: str) -> None:
        self._texto.setText(f"Versao {versao} disponivel.")
        self._barra.setVisible(False)
        self._botao.setEnabled(True)
        self.show()

    def mostra_progresso(self, feito: int, total: int) -> None:
        self._botao.setEnabled(False)
        self._barra.setVisible(True)
        # total 0 e o servidor nao ter mandado Content-Length: barra
        # indeterminada em vez de uma barra travada em 0%, que le como
        # download parado.
        self._barra.setRange(0, total)
        self._barra.setValue(feito)
        self._texto.setText("Baixando a atualizacao...")

    def esconde(self) -> None:
        self.hide()

    def acionar(self) -> None:
        """Aciona Atualizar. Existe para o teste percorrer o clique real."""
        self._botao.click()

    def dispensar(self) -> None:
        """Aciona o ✕. Mesmo motivo de acionar()."""
        self._fechar.click()
