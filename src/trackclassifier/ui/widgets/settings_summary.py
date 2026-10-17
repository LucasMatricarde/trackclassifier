"""Read-only summary of the current settings draft."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...config import SettingsDraft
from ..tokens import SPACE_5, SPACE_6


class SettingsSummary(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsSummary")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(290)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        heading = QLabel("Resumo para salvar")
        heading.setObjectName("DashboardSectionTitle")
        layout.addWidget(heading)
        note = QLabel("As alteracoes entram em vigor ao clicar Salvar.")
        note.setObjectName("DashboardMuted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self._paths = QLabel()
        self._model = QLabel()
        for section, label in (("Pastas", self._paths), ("Modelo", self._model)):
            title = QLabel(section)
            title.setObjectName("DashboardCaption")
            layout.addWidget(title)
            label.setObjectName("DashboardMuted")
            label.setWordWrap(True)
            layout.addWidget(label)
        layout.addStretch(1)

    def set_draft(self, draft: SettingsDraft) -> None:
        def short_path(value: str | None) -> str:
            if not value:
                return "—"
            parts = Path(value).parts
            return f"…/{'/'.join(parts[-2:])}" if len(parts) > 2 else value

        self._paths.setText(
            f"Entrada: {short_path(draft.inbox)}\n"
            f"-1: {short_path(draft.down)}\n"
            f"neutra: {short_path(draft.neutral)}\n"
            f"+1: {short_path(draft.up)}\n"
            f"Dados: {short_path(draft.data_dir)}"
        )
        self._model.setText(
            f"Retreinar a cada {draft.retrain_every} musicas\n"
            f"Minimo de {draft.min_examples} exemplos por classe"
        )
