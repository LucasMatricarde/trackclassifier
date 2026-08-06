"""Dialogo de primeira abertura -- e de conserto de config quebrado.

Dispara pela AUSENCIA do arquivo de config, nao por uma flag "ja abriu
antes" guardada em algum lugar: o estado que importa e ter ou nao ter
configuracao utilizavel, e ele ja mora no disco.

Cobre tambem o config que existe mas ficou invalido (pasta apagada ou
renomeada). Antes isso era beco sem saida -- um QMessageBox mandando editar
um TOML e reabrir o app.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from ..config import (
    Config,
    ConfigError,
    SettingsDraft,
    apply_draft,
    load_config,
    read_raw,
    save_config,
    validate_settings,
)
from .settings_form import SettingsForm
from .tokens import SPACE_5, SPACE_6

_BOAS_VINDAS = (
    "Antes de comecar, diga onde ficam as suas tracks. "
    "Voce pode mudar isso depois na aba Configuracao."
)


class FirstRunDialog(QDialog):
    def __init__(self, caminho: Path, escolher_pasta=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Track classifier")
        self._caminho = Path(caminho)
        self._config: Config | None = None

        intro = QLabel(_BOAS_VINDAS)
        intro.setWordWrap(True)

        self.form = SettingsForm(escolher_pasta=escolher_pasta)
        # read_raw e nao load_config: quando o config existe mas uma pasta
        # sumiu, load_config levanta e nao devolve nada aproveitavel -- o
        # usuario redigitaria os quatro caminhos por causa de um que mudou.
        self.form.set_draft(SettingsDraft.from_raw(read_raw(self._caminho)))

        self._botoes = QDialogButtonBox()
        self._comecar = self._botoes.addButton("Comecar", QDialogButtonBox.ButtonRole.AcceptRole)
        self._comecar.setProperty("variant", "primary")
        self._botoes.addButton(QDialogButtonBox.StandardButton.Cancel)
        self._botoes.accepted.connect(self.confirmar)
        self._botoes.rejected.connect(self.reject)

        self._comecar.setEnabled(self.form.is_valid())
        self.form.validity_changed.connect(self._comecar.setEnabled)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addWidget(intro)
        layout.addWidget(self.form, 1)
        layout.addWidget(self._botoes)

    @property
    def config(self) -> Config | None:
        return self._config

    def confirmar(self) -> None:
        rascunho = self.form.draft()
        erros = validate_settings(rascunho)
        if erros:
            self.form.show_errors(erros)
            return
        self.form.show_errors([])

        config = apply_draft(rascunho)
        save_config(self._caminho, config)
        # Rele do disco: e o que garante que o que a janela vai usar e
        # exatamente o que foi gravado, e nao um Config em memoria que
        # divergiria de um arquivo mal gravado.
        try:
            self._config = load_config(self._caminho)
        except ConfigError as erro:
            self.form.show_errors([_erro_generico(str(erro))])
            return
        self.accept()


def _erro_generico(mensagem: str):
    from ..config import SettingsError

    return SettingsError("inbox", mensagem)
