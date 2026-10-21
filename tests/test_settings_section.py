"""Testes dos helpers de secao do formulario de configuracao."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from trackclassifier.ui.tokens import SPACE_5
from trackclassifier.ui.widgets.panel import Panel
from trackclassifier.ui.widgets.settings_section import (
    ajuda,
    cabecalho,
    rotulo_de_campo,
    secao_painel,
)


class TestSecaoPainel:
    def test_cria_panel_com_conteudo_espacado(self, qapp):
        """secao_painel cria Panel com conteudo interno espacado."""
        item1 = QLabel("Item 1")
        item2 = QLabel("Item 2")
        panel = secao_painel(item1, item2, espaco=8)

        assert isinstance(panel, Panel)
        assert panel.objectName() == "Panel"
        assert isinstance(panel.content, QVBoxLayout)
        assert panel.content.spacing() == SPACE_5
        conteudo_widget = panel.content.itemAt(0).widget()
        assert isinstance(conteudo_widget, QWidget)
        assert conteudo_widget.objectName() == "PanelSection"
        inner_layout = conteudo_widget.layout()
        assert isinstance(inner_layout, QVBoxLayout)
        assert inner_layout.spacing() == 8
        assert inner_layout.count() == 2
        assert inner_layout.itemAt(0).widget() is item1
        assert inner_layout.itemAt(1).widget() is item2

    def test_panel_section_object_name(self, qapp):
        """O conteudo interno tem objectName PanelSection."""
        panel = secao_painel(QLabel("x"), espaco=4)
        conteudo_widget = panel.content.itemAt(0).widget()
        assert conteudo_widget.objectName() == "PanelSection"


class TestCabecalho:
    def test_retorna_qlabel_com_objectname_sectionheader(self, qapp):
        """cabecalho retorna QLabel com objectName=SectionHeader."""
        rotulo = cabecalho("Entrada")
        assert isinstance(rotulo, QLabel)
        assert rotulo.objectName() == "SectionHeader"

    def test_texto_em_caixa_alta(self, qapp):
        """Texto vem em caixa alta."""
        rotulo = cabecalho("Entrada")
        assert rotulo.text() == "ENTRADA"

    def test_aplica_tracking_widest(self, qapp):
        """Aplica tracking wide (0.09em) no rotulo."""
        rotulo = cabecalho("Entrada")
        assert rotulo.font().letterSpacing() > 0


class TestAjuda:
    def test_retorna_qlabel_com_objectname_hint(self, qapp):
        """ajuda retorna QLabel com objectName=Hint."""
        rotulo = ajuda("Texto de ajuda")
        assert isinstance(rotulo, QLabel)
        assert rotulo.objectName() == "Hint"

    def test_word_wrap_true(self, qapp):
        """Word wrap esta ativado."""
        rotulo = ajuda("Texto de ajuda")
        assert rotulo.wordWrap() is True

    def test_texto_preservado(self, qapp):
        """Texto passado e preservado."""
        texto = (
            "Classificar MOVE o arquivo: ele sai da entrada e vai para "
            "a pasta do rotulo escolhido."
        )
        rotulo = ajuda(texto)
        assert rotulo.text() == texto


class TestRotuloDeCampo:
    def test_retorna_qlabel_com_objectname_fieldlabel(self, qapp):
        """rotulo_de_campo retorna QLabel com objectName=FieldLabel."""
        rotulo = rotulo_de_campo("Pasta de entrada")
        assert isinstance(rotulo, QLabel)
        assert rotulo.objectName() == "FieldLabel"

    def test_texto_preservado(self, qapp):
        """Texto passado e preservado."""
        rotulo = rotulo_de_campo("Pasta de entrada")
        assert rotulo.text() == "Pasta de entrada"

    def test_nao_aplica_caixa_alta(self, qapp):
        """Diferente de cabecalho, nao aplica caixa alta."""
        rotulo = rotulo_de_campo("Pasta de entrada")
        assert rotulo.text() == "Pasta de entrada"
