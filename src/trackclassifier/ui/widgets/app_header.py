"""Navegacao global do dashboard e o botao de scan.

Os icones sao SVGs de ui/icons/ tintados por token (ver ui/icons.py) --
antes eram glifos unicode dentro do texto do botao, que nao escalam nem
mudam de cor com o estado, e era por isso que a aba ativa nao tinha como
ficar azul como no mockup.
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..icons import icon
from ..tokens import (
    COLOR_ACCENT_BASE,
    COLOR_ACCENT_TEXT,
    COLOR_TEXT_SECONDARY,
    SIZE_CONTROL_HEADER,
    SIZE_ICON_BASE,
    SIZE_ICON_LARGE,
    SIZE_ICON_SMALL,
    SPACE_4,
    SPACE_5,
    SPACE_6,
)

#: Icone de cada aba, na ordem em que as paginas chegam. Os nomes casam com
#: os SVGs de ui/icons/. strict=False de proposito: a aba Configuracao so
#: existe quando ha config em disco (window.py), entao os testes de fumaca
#: montam a janela com 3 paginas e o zip para no menor.
_ICONES_DAS_ABAS = ("nav-review", "nav-library", "nav-model", "nav-settings")


def _icone_com_estados(nome: str) -> QIcon:
    """O mesmo SVG nas duas cores: cinza em repouso, azul do acento ativo.

    O Qt desenha o icone de um botao marcado com QIcon.State.On -- registrar
    a variante azul nesse estado e o que faz o icone acompanhar a pill do
    NavItem sem nenhum codigo por troca de aba.
    """
    combinado = QIcon(icon(nome, COLOR_TEXT_SECONDARY, SIZE_ICON_BASE).pixmap(
        SIZE_ICON_BASE, SIZE_ICON_BASE
    ))
    combinado.addPixmap(
        icon(nome, COLOR_ACCENT_TEXT, SIZE_ICON_BASE).pixmap(SIZE_ICON_BASE, SIZE_ICON_BASE),
        QIcon.Mode.Normal,
        QIcon.State.On,
    )
    return combinado


class AppHeader(QWidget):
    page_requested = Signal(int)
    scan_requested = Signal()

    def __init__(self, pages: tuple[str, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AppHeader")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(SIZE_CONTROL_HEADER)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_4, SPACE_6, SPACE_4)
        layout.setSpacing(SPACE_5)

        logo = QLabel()
        logo.setPixmap(
            icon("logo", COLOR_ACCENT_BASE, SIZE_ICON_LARGE).pixmap(
                SIZE_ICON_LARGE, SIZE_ICON_LARGE
            )
        )
        layout.addWidget(logo)
        brand = QLabel("TrackClassifier")
        brand.setObjectName("AppBrand")
        layout.addWidget(brand)
        layout.addSpacing(SPACE_6)

        for index, (icone, page) in enumerate(zip(_ICONES_DAS_ABAS, pages, strict=False)):
            button = QPushButton(page)
            button.setObjectName("NavItem")
            button.setCheckable(True)
            button.setIcon(_icone_com_estados(icone))
            button.setIconSize(QSize(SIZE_ICON_BASE, SIZE_ICON_BASE))
            button.clicked.connect(lambda _checked=False, i=index: self.page_requested.emit(i))
            self._group.addButton(button)
            self._buttons.append(button)
            layout.addWidget(button)
        layout.addStretch(1)

        # Status de scan em duas linhas (titulo claro + contadores muted)
        # com o icone de lista do mockup a esquerda.
        status_icone = QLabel()
        status_icone.setPixmap(
            icon("status", COLOR_TEXT_SECONDARY, SIZE_ICON_SMALL).pixmap(
                SIZE_ICON_SMALL, SIZE_ICON_SMALL
            )
        )
        layout.addWidget(status_icone, 0, Qt.AlignmentFlag.AlignVCenter)
        self._status_titulo = QLabel("Pronto para escanear")
        self._status_titulo.setObjectName("HeaderStatusTitle")
        self._status_detalhe = QLabel("")
        self._status_detalhe.setObjectName("DashboardMuted")
        status_coluna = QVBoxLayout()
        status_coluna.setContentsMargins(0, 0, 0, 0)
        status_coluna.setSpacing(0)
        status_coluna.addWidget(self._status_titulo)
        status_coluna.addWidget(self._status_detalhe)
        layout.addLayout(status_coluna)
        layout.addSpacing(SPACE_4)

        self.scan_button = QPushButton()
        self.scan_button.setObjectName("ScanButton")
        self.scan_button.setProperty("variant", "primary")
        self.scan_button.setIcon(icon("scan", COLOR_ACCENT_BASE, SIZE_ICON_SMALL))
        self.scan_button.setIconSize(QSize(SIZE_ICON_SMALL, SIZE_ICON_SMALL))
        self.scan_button.clicked.connect(self.scan_requested)
        layout.addWidget(self.scan_button)
        self.set_current_index(0)

    def set_current_index(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def set_scan_label(self, label: str) -> None:
        self.scan_button.setText(label)

    def set_summary(self, tracks: int, analysed: int) -> None:
        self._status_titulo.setText("Scan concluido")
        self._status_detalhe.setText(f"{tracks} tracks · {analysed} analisadas")

    def set_progress(self, done: int, total: int) -> None:
        self._status_titulo.setText("Escaneando")
        self._status_detalhe.setText(f"{done} de {total}")
