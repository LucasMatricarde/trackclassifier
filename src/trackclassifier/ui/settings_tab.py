"""Aba Configuracao: o mesmo SettingsForm do primeiro uso, mais Salvar.

Um formulario so nos dois papeis -- uma validacao, uma copia da regra de
qual pasta pode ser igual a qual.
"""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..config import (
    ConfigError,
    SettingsDraft,
    SettingsError,
    apply_draft,
    load_config,
    read_raw,
    save_config,
    validate_settings,
)
from .settings_form import SettingsForm
from .tokens import SPACE_4, SPACE_5, SPACE_6

_MOTIVO_SCAN = "Aguarde o scan terminar para salvar."


class SettingsTab(QWidget):
    #: Carrega o Config recem-gravado. object porque Signal nao aceita uma
    #: dataclass arbitraria como tipo declarado.
    config_saved = Signal(object)

    def __init__(self, caminho: Path, escolher_pasta=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._caminho = Path(caminho)
        self._escaneando = False

        self.form = SettingsForm(escolher_pasta=escolher_pasta)
        self.form.set_draft(SettingsDraft.from_raw(read_raw(self._caminho)))
        self.form.validity_changed.connect(lambda _valido: self._atualiza_botao())

        self._botao = QPushButton("Salvar")
        self._botao.setProperty("variant", "primary")
        self._botao.clicked.connect(self.salvar)

        self._motivo = QLabel("")
        self._motivo.setObjectName("Hint")

        rodape = QHBoxLayout()
        rodape.setSpacing(SPACE_4)
        rodape.addWidget(self._motivo)
        rodape.addStretch(1)
        rodape.addWidget(self._botao)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self.form, 1)
        layout.addLayout(rodape)

        self._atualiza_botao()

    def set_scanning(self, escaneando: bool) -> None:
        self._escaneando = escaneando
        self._motivo.setText(_MOTIVO_SCAN if escaneando else "")
        self._atualiza_botao()

    def botao_habilitado(self) -> bool:
        return self._botao.isEnabled()

    def salvar(self) -> None:
        rascunho = self.form.draft()
        erros = validate_settings(rascunho)
        if erros:
            self.form.show_errors(erros)
            return
        self.form.show_errors([])

        config = apply_draft(rascunho)
        save_config(self._caminho, config)
        try:
            gravado = load_config(self._caminho)
        except ConfigError as erro:
            self.form.show_errors([SettingsError("inbox", str(erro))])
            return
        self.config_saved.emit(gravado)

    def _atualiza_botao(self) -> None:
        self._botao.setEnabled(self.form.is_valid() and not self._escaneando)
