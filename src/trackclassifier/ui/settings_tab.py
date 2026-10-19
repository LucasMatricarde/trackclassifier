"""Aba Configuracao: o mesmo SettingsForm do primeiro uso, mais Salvar.

Um formulario so nos dois papeis -- uma validacao, uma copia da regra de
qual pasta pode ser igual a qual.
"""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    ConfigError,
    SettingsDraft,
    SettingsError,
    apply_all_drafts,
    load_config,
    read_raw,
    save_config,
    validate_settings,
)
from .counts import conta_tracks
from .settings_form import SettingsForm
from .tokens import SPACE_4, SPACE_5, SPACE_6
from .typography import estiliza_label
from .widgets.settings_summary import SettingsSummary

_MOTIVO_SCAN = "Aguarde o scan terminar para salvar."


class SettingsTab(QWidget):
    #: Carrega o Config recem-gravado. object porque Signal nao aceita uma
    #: dataclass arbitraria como tipo declarado.
    config_saved = Signal(object)
    #: (nome do perfil ativo) -- emitido quando o usuario troca de perfil no
    #: seletor deste formulario. window.py liga ao worker.switch_profile.
    profile_changed = Signal(str)

    def __init__(self, caminho: Path, escolher_pasta=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._caminho = Path(caminho)
        self._escaneando = False
        self._drafts: dict[str, SettingsDraft] = {}
        self._active_profile: str = ""

        self.form = SettingsForm(escolher_pasta=escolher_pasta)
        self._carrega_drafts()
        self.form.validity_changed.connect(lambda _valido: self._atualiza_botao())
        self.summary = SettingsSummary()
        self.summary.set_draft(self._draft_ativo())
        self.form.validity_changed.connect(
            lambda _valid: self.summary.set_draft(self._draft_ativo())
        )

        self._botao = QPushButton()
        estiliza_label(self._botao, "Salvar")
        self._botao.setProperty("variant", "primary")
        self._botao.clicked.connect(self.salvar)

        self._motivo = QLabel("")
        self._motivo.setObjectName("Hint")

        rodape = QHBoxLayout()
        rodape.setSpacing(SPACE_4)
        rodape.addWidget(self._motivo)
        rodape.addStretch(1)
        rodape.addWidget(self._botao)

        rolagem = QScrollArea()
        rolagem.setWidget(self.form)
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        heading = QLabel("Configuracoes")
        heading.setObjectName("ReviewTrackTitle")
        layout.addWidget(heading)

        # Seletor de perfil: troca entre perfis existentes, ou cria um novo.
        sel = QHBoxLayout()
        sel.setSpacing(SPACE_4)
        sel.addWidget(QLabel("Perfil:"))
        self._seletor = QComboBox()
        self._seletor.setMinimumWidth(200)
        self._btn_novo = QPushButton("Novo")
        estiliza_label(self._btn_novo, "Novo")
        self._btn_excluir = QPushButton("Excluir")
        estiliza_label(self._btn_excluir, "Excluir")
        self._btn_excluir.setEnabled(False)
        sel.addWidget(self._seletor, 1)
        sel.addWidget(self._btn_novo)
        sel.addWidget(self._btn_excluir)
        layout.addLayout(sel)

        body = QHBoxLayout()
        body.setSpacing(SPACE_5)
        body.addWidget(rolagem, 1)
        body.addWidget(self.summary)
        layout.addLayout(body, 1)
        layout.addLayout(rodape)

        self._atualiza_botao()
        self._atualiza_seletor()
        self._seletor.currentTextChanged.connect(self._troca_perfil)
        self._btn_novo.clicked.connect(self._novo_perfil)
        self._btn_excluir.clicked.connect(self._exclui_perfil)

    def _carrega_drafts(self) -> None:
        from ..config import drafts_from_raw

        raw = read_raw(self._caminho)
        self._drafts = drafts_from_raw(raw)
        try:
            config_existente = load_config(self._caminho)
        except ConfigError:
            config_existente = None
        if config_existente is not None:
            self._active_profile = config_existente.active_profile
        elif self._drafts:
            self._active_profile = next(iter(self._drafts))
        else:
            self._active_profile = "default"
        self.form.set_draft(self._draft_ativo())

    def _draft_ativo(self) -> SettingsDraft:
        return self._drafts.get(
            self._active_profile,
            SettingsDraft(
                inbox="", up="", neutral="", down="",
                data_dir="", retrain_every=10, min_examples=15,
                create_under_root=False, root="", name=self._active_profile,
            ),
        )

    def _atualiza_seletor(self) -> None:
        nomes = sorted(self._drafts.keys())
        self._seletor.blockSignals(True)
        self._seletor.clear()
        self._seletor.addItems(nomes)
        self._seletor.setCurrentText(self._active_profile)
        self._seletor.blockSignals(False)
        self._btn_excluir.setEnabled(len(nomes) > 1)

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

        # Salva o draft editado no slot de perfil ativo antes de aplicar.
        self._drafts[self._active_profile] = rascunho

        config = apply_all_drafts(self._drafts, self._active_profile, self._caminho)
        save_config(self._caminho, config)
        try:
            gravado = load_config(self._caminho)
        except ConfigError as erro:
            self.form.show_errors([SettingsError("inbox", str(erro))])
            return
        self.config_saved.emit(gravado)
        self.profile_changed.emit(gravado.active_profile)

    def _atualiza_botao(self) -> None:
        self._botao.setEnabled(self.form.is_valid() and not self._escaneando)

    # ---- perfil ----------------------------------------------------------

    def _troca_perfil(self, nome: str) -> None:
        if nome not in self._drafts:
            return
        # Persistir o draft editado do perfil anterior antes de trocar, para
        # nao perder digitacao nao salva.
        if self._active_profile in self._drafts:
            self._drafts[self._active_profile] = self.form.draft()
        self._active_profile = nome
        self.form.set_draft(self._draft_ativo())

    def _novo_perfil(self) -> None:
        """Cria um perfil vazio (copia do ativo) e entra nele."""
        origem = self._draft_ativo()
        nome_novo = "perfil"
        contador = 2
        while nome_novo in self._drafts:
            nome_novo = f"perfil{contador}"
            contador += 1
        novo = SettingsDraft(
            inbox=origem.inbox, up=origem.up, neutral=origem.neutral, down=origem.down,
            data_dir=origem.data_dir, retrain_every=origem.retrain_every,
            min_examples=origem.min_examples, create_under_root=origem.create_under_root,
            root=origem.root, name=nome_novo,
        )
        self._drafts[nome_novo] = novo
        self._active_profile = nome_novo
        self._atualiza_seletor()
        self.form.set_draft(novo)

    def _exclui_perfil(self) -> None:
        """Remove o perfil ativo. Guarda contra apagar o ultimo ou um perfil
        que tem tracks classificadas.
        """
        if len(self._drafts) <= 1:
            self._motivo.setText("Nao e possivel excluir o ultimo perfil.")
            return
        perfil = self._draft_ativo()
        # Scan guard: nao exclui se ha tracks nas pastas deste perfil.
        total = conta_tracks(perfil.inbox) or 0
        for chave in ("up", "neutral", "down"):
            total += conta_tracks(getattr(perfil, chave)) or 0
        if total > 0:
            self._motivo.setText(
                f"O perfil tem {total} track(s). Remova-as antes de excluir."
            )
            return

        nome_excluido = self._active_profile
        del self._drafts[nome_excluido]
        # Troca para outro perfil como proximo ativo.
        self._active_profile = next(iter(self._drafts))
        self._atualiza_seletor()
        self.form.set_draft(self._draft_ativo())
