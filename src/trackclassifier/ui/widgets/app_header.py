"""Global dashboard navigation and scan affordance."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QWidget

from ..tokens import SIZE_CONTROL_HEADER, SPACE_4, SPACE_5, SPACE_6


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
        brand = QLabel("◈  TrackClassifier")
        brand.setObjectName("DashboardSectionTitle")
        layout.addWidget(brand)
        layout.addSpacing(SPACE_6)
        for index, (icon, page) in enumerate(
            zip(("▶", "♫", "▥", "⚙"), pages, strict=False)
        ):
            button = QPushButton(f"{icon}  {page}")
            button.setObjectName("NavItem")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, i=index: self.page_requested.emit(i))
            self._group.addButton(button)
            self._buttons.append(button)
            layout.addWidget(button)
        layout.addStretch(1)
        self._status = QLabel("Pronto para escanear")
        self._status.setObjectName("DashboardMuted")
        layout.addWidget(self._status)
        self.scan_button = QPushButton("▣  ESCANEAR")
        self.scan_button.setProperty("variant", "primary")
        self.scan_button.clicked.connect(self.scan_requested)
        layout.addWidget(self.scan_button)
        self.set_current_index(0)

    def set_current_index(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def set_scan_label(self, label: str) -> None:
        self.scan_button.setText(label)

    def set_summary(self, tracks: int, analysed: int) -> None:
        self._status.setText(f"Scan concluido  ·  {tracks} tracks · {analysed} analisadas")

    def set_progress(self, done: int, total: int) -> None:
        self._status.setText(f"Escaneando {done}/{total}")
