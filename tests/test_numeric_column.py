"""Testes da coluna numerica (rotulo + spin)."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from trackclassifier.config import MODELO_MAXIMO, MODELO_MINIMO
from trackclassifier.ui.tokens import SPACE_2
from trackclassifier.ui.widgets.numeric_column import (
    _LARGURA_NUMERICO,
    coluna_numerica,
    cria_campo_numerico,
)


class TestCriaCampoNumerico:
    def test_spin_com_range_correto(self, qapp):
        """Spin tem range MODELO_MINIMO..MODELO_MAXIMO."""
        spin = cria_campo_numerico()
        assert spin.minimum() == MODELO_MINIMO
        assert spin.maximum() == MODELO_MAXIMO

    def test_spin_largura_fixa(self, qapp):
        """Spin tem largura fixa _LARGURA_NUMERICO (96px)."""
        spin = cria_campo_numerico()
        assert spin.width() == _LARGURA_NUMERICO


class TestColunaNumerica:
    def test_retorna_widget_com_layout_vertical(self, qapp):
        """Retorna QWidget com QVBoxLayout."""
        spin = cria_campo_numerico()
        caixa = coluna_numerica("Retreinar a cada", spin)
        assert isinstance(caixa, QWidget)
        layout = caixa.layout()
        assert isinstance(layout, QVBoxLayout)
        assert layout.contentsMargins().left() == 0
        assert layout.contentsMargins().top() == 0
        assert layout.contentsMargins().right() == 0
        assert layout.contentsMargins().bottom() == 0

    def test_rotulo_em_cima_do_spin(self, qapp):
        """Rotulo fica em cima do spin."""
        spin = cria_campo_numerico()
        caixa = coluna_numerica("Retreinar a cada", spin)
        layout = caixa.layout()
        assert layout.count() == 2
        assert layout.itemAt(0).widget() is not spin
        assert layout.itemAt(1).widget() is spin

    def test_rotulo_tem_objectname_fieldlabel(self, qapp):
        """Rotulo tem objectName FieldLabel."""
        spin = cria_campo_numerico()
        caixa = coluna_numerica("Retreinar a cada", spin)
        rotulo = caixa.layout().itemAt(0).widget()
        assert isinstance(rotulo, QLabel)
        assert rotulo.objectName() == "FieldLabel"
        assert rotulo.text() == "Retreinar a cada"

    def test_rotulo_setbuddy_spin(self, qapp):
        """Rotulo tem setBuddy apontando para o spin (acessibilidade)."""
        spin = cria_campo_numerico()
        caixa = coluna_numerica("Retreinar a cada", spin)
        rotulo = caixa.layout().itemAt(0).widget()
        assert rotulo.buddy() is spin

    def test_espacamento_space_2(self, qapp):
        """Espacamento entre rotulo e spin e SPACE_2 (4px)."""
        spin = cria_campo_numerico()
        caixa = coluna_numerica("Retreinar a cada", spin)
        assert caixa.layout().spacing() == SPACE_2
