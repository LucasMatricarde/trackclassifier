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
    QFrame,
    QLabel,
    QScrollArea,
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
from .tokens import FONT_SIZE_DISPLAY, FONT_WEIGHT_MEDIUM, SPACE_5, SPACE_8
from .typography import estiliza_label

_PERGUNTA = "Onde ficam as suas tracks?"

_BOAS_VINDAS = (
    "Classificar uma track MOVE o arquivo: ele sai da pasta de entrada e vai "
    "para a pasta do rótulo escolhido. Por isso as pastas importam antes de "
    "qualquer outra coisa. Você pode mudar tudo depois na aba Configuração."
)


class FirstRunDialog(QDialog):
    def __init__(self, caminho: Path, escolher_pasta=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Track classifier")
        self._caminho = Path(caminho)
        self._config: Config | None = None

        pergunta = QLabel(_PERGUNTA)
        pergunta.setStyleSheet(
            f"font-size: {FONT_SIZE_DISPLAY}; font-weight: {FONT_WEIGHT_MEDIUM};"
        )

        intro = QLabel(_BOAS_VINDAS)
        intro.setWordWrap(True)

        self.form = SettingsForm(escolher_pasta=escolher_pasta)
        # read_raw e nao load_config: quando o config existe mas uma pasta
        # sumiu, load_config levanta e nao devolve nada aproveitavel -- o
        # usuario redigitaria os quatro caminhos por causa de um que mudou.
        self.form.set_draft(SettingsDraft.from_raw(read_raw(self._caminho)))

        self._botoes = QDialogButtonBox()
        self._comecar = self._botoes.addButton("", QDialogButtonBox.ButtonRole.AcceptRole)
        estiliza_label(self._comecar, "Comecar")
        self._comecar.setProperty("variant", "primary")
        # Botao proprio em vez de StandardButton.Cancel: o botao padrao vem
        # com o rotulo traduzido do sistema ("Cancel"/"Cancelar" conforme o
        # locale) e nao aceita a caixa alta do vocabulario sem ser
        # reescrito de qualquer jeito. Desistir da configuracao sai com
        # codigo 0 -- nao e falha, e o codigo ja tratava assim.
        self._cancelar = self._botoes.addButton("", QDialogButtonBox.ButtonRole.RejectRole)
        estiliza_label(self._cancelar, "Cancelar")
        self._botoes.accepted.connect(self.confirmar)
        self._botoes.rejected.connect(self.reject)

        self._comecar.setEnabled(self.form.is_valid())
        self.form.validity_changed.connect(self._comecar.setEnabled)

        rolagem = QScrollArea()
        rolagem.setWidget(self.form)
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        # space.8 e a margem de dialogo e de tela de primeiro uso -- era um
        # dos tokens orfaos da v0.1.
        layout.setContentsMargins(SPACE_8, SPACE_8, SPACE_8, SPACE_8)
        layout.setSpacing(SPACE_5)
        layout.addWidget(pergunta)
        layout.addWidget(intro)
        layout.addWidget(rolagem, 1)
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

        config = apply_draft(rascunho, self._caminho)
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
