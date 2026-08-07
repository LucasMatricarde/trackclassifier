"""Chip da tonalidade, colorido pela roda de Camelot.

A cor nao e decoracao: a posicao na roda e o que diz se duas tracks mixam
bem, entao keys vizinhas tem cores vizinhas e o olho encontra o par antes de
ler o texto.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from ...keys import Key, KeyNotation, format_key
from ..tokens import (
    COLOR_TEXT_INVERSE,
    COLOR_TEXT_MUTED,
    FONT_FAMILY_MONO,
    FONT_SIZE_BODY,
    RADIUS_XS,
    SPACE_1,
    SPACE_3,
    camelot_color,
)

#: A key e numero que se alinha em coluna (ver $regra-de-uso.mono-para-numero
#: no design-tokens.json), entao a familia precisa vir daqui: o chip nao tem
#: objectName no QSS, e sem isto herda a sans do QWidget base.
#:
#: O padding entra aqui, e nao so no branch com key: quando o chip fica sem
#: padding no estado vazio, sua altura encolhe uns pixels em relacao ao
#: estado colorido -- e como review_tab.py alinha essa coluna por AlignBottom
#: independente das outras (BPM/Duracao/Restam, de altura fixa), o rotulo
#: "KEY" pulava verticalmente ao navegar de uma track sem key para uma com
#: key. Padding constante mantem a altura do chip constante nos dois estados.
_BASE = (
    f"font-family: {FONT_FAMILY_MONO}; font-size: {FONT_SIZE_BODY};"
    f" padding: {SPACE_1}px {SPACE_3}px;"
)


class KeyChip(QLabel):
    """Rotulo com fundo colorido. QLabel e nao QWidget pintado a mao porque
    o texto e o unico conteudo -- QSS resolve o resto."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key: Key | None = None
        self._notation = KeyNotation.CAMELOT
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # "11A" sozinho nao diz de que grandeza e -- o chip comunica isso
        # pela cor, que um leitor de tela nao le.
        self.setAccessibleName("Tonalidade")
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
            # tem tonalidade e o app so nao soube formatar. O travessao fica
            # muted para nao competir com os numeros ao lado, que sao dado.
            self.setStyleSheet(f"{_BASE} color: {COLOR_TEXT_MUTED};")
            return
        fundo = camelot_color(self._key.camelot_number)
        self.setStyleSheet(
            f"{_BASE} background: {fundo}; color: {COLOR_TEXT_INVERSE}; "
            f"border-radius: {RADIUS_XS}px;"
        )
