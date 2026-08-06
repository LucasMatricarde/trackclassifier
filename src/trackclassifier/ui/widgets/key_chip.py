"""Chip da tonalidade, colorido pela roda de Camelot.

A cor nao e decoracao: a posicao na roda e o que diz se duas tracks mixam
bem, entao keys vizinhas tem cores vizinhas e o olho encontra o par antes de
ler o texto.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from ...keys import Key, KeyNotation, format_key
from ..tokens import COLOR_TEXT_INVERSE, RADIUS_SM, SPACE_2, camelot_color


class KeyChip(QLabel):
    """Rotulo com fundo colorido. QLabel e nao QWidget pintado a mao porque
    o texto e o unico conteudo -- QSS resolve o resto."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key: Key | None = None
        self._notation = KeyNotation.CAMELOT
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._repinta()

    def set_key(self, key: Key | None) -> None:
        self._key = key
        self._repinta()

    def set_notation(self, notation: KeyNotation) -> None:
        self._notation = notation
        self._repinta()

    def _repinta(self) -> None:
        self.setText(format_key(self._key, self._notation))
        if self._key is None:
            # Sem key, sem cor: um chip colorido vazio sugeriria que a track
            # tem tonalidade e o app so nao soube formatar.
            self.setStyleSheet("")
            return
        fundo = camelot_color(self._key.camelot_number)
        self.setStyleSheet(
            f"background: {fundo}; color: {COLOR_TEXT_INVERSE}; "
            f"border-radius: {RADIUS_SM}px; padding: 0px {SPACE_2}px;"
        )
