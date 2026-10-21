"""Testes do RootModeCard — card do modo 'criar estrutura'."""

from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout

from trackclassifier.ui.widgets.root_mode_card import RootModeCard
from trackclassifier.ui.widgets.settings_field import SettingsField


def _escolher_falso(titulo, atual):
    return ""


class TestRootModeCard:
    def test_card_tem_objectname_e_property_accent(self, qapp):
        """Card tem objectName='Card' e property accent=true."""
        checkbox = QCheckBox("Criar")
        ajuda = QLabel("Ajuda")
        campo_raiz = SettingsField("root", _escolher_falso)
        card = RootModeCard(checkbox, ajuda, campo_raiz)

        assert card.objectName() == "Card"
        assert card.property("accent") is True

    def test_layout_vertical_com_checkbox_ajuda_campo(self, qapp):
        """Layout vertical na ordem: checkbox, ajuda, campo_raiz."""
        checkbox = QCheckBox("Criar")
        ajuda = QLabel("Ajuda")
        campo_raiz = SettingsField("root", _escolher_falso)
        card = RootModeCard(checkbox, ajuda, campo_raiz)

        layout = card.layout()
        assert isinstance(layout, QVBoxLayout)
        assert layout.count() == 3
        assert layout.itemAt(0).widget() is checkbox
        assert layout.itemAt(1).widget() is ajuda
        assert layout.itemAt(2).widget() is campo_raiz

    def test_margins_e_spacing(self, qapp):
        """Margens SPACE_5 (12px) e spacing SPACE_4 (8px)."""
        from trackclassifier.ui.tokens import SPACE_4, SPACE_5
        checkbox = QCheckBox("Criar")
        ajuda = QLabel("Ajuda")
        campo_raiz = SettingsField("root", _escolher_falso)
        card = RootModeCard(checkbox, ajuda, campo_raiz)

        layout = card.layout()
        assert layout.contentsMargins().left() == SPACE_5
        assert layout.contentsMargins().top() == SPACE_5
        assert layout.contentsMargins().right() == SPACE_5
        assert layout.contentsMargins().bottom() == SPACE_5
        assert layout.spacing() == SPACE_4

    def test_set_visible_all_propaga_para_filhos(self, qapp):
        """set_visible_all no card esconde/mostra todos os filhos."""
        checkbox = QCheckBox("Criar")
        ajuda = QLabel("Ajuda")
        campo_raiz = SettingsField("root", _escolher_falso)
        card = RootModeCard(checkbox, ajuda, campo_raiz)

        card.set_visible_all(False)
        assert checkbox.isHidden()
        assert ajuda.isHidden()
        assert campo_raiz.isHidden()
        assert card.isHidden()

        card.set_visible_all(True)
        assert not checkbox.isHidden()
        assert not ajuda.isHidden()
        assert not campo_raiz.isHidden()
        assert not card.isHidden()

    def test_ajuda_tem_objectname_hint(self, qapp):
        """Ajuda passada e usada diretamente (ja deve ter objectName Hint)."""
        checkbox = QCheckBox("Criar")
        ajuda = QLabel("Ajuda")
        ajuda.setObjectName("Hint")
        campo_raiz = SettingsField("root", _escolher_falso)
        card = RootModeCard(checkbox, ajuda, campo_raiz)

        assert card.layout().itemAt(1).widget().objectName() == "Hint"
