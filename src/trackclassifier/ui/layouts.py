"""Helpers de layout compartilhados entre abas.

`secao()` nomeia um idioma que se repetia sem nome em varios arquivos:
QWidget + QVBoxLayout(margens zero, espacamento fixo) agrupando um
conjunto de widgets/layouts construidos de UMA VEZ (nao serve pra quem
precisa continuar acrescentando filho depois de construido, nem pra quem
precisa de fator de estica por item -- review_tab.ReviewTab._bloco e o
caso: o `1` em `addWidget(self._waveform, 1)` nao tem como pedir aqui, e
forcar esse chamador a caber no molde teria trocado um bug por outro).
Promovido para ca depois de aparecer independente em settings_form.py e
model_tab.py -- extrair antes disso teria sido generalidade sem uso.
"""

from PySide6.QtWidgets import QLayout, QVBoxLayout, QWidget


def secao(*itens: QWidget | QLayout, espaco: int) -> QWidget:
    """Agrupa itens (widgets OU layouts) num QWidget com QVBoxLayout.

    Aceita QLayout alem de QWidget porque settings_form.SettingsForm
    (_monta_modelo) precisa somar um QHBoxLayout aos widgets da secao --
    forcar esse chamador a embrulhar sozinho antes de passar seria mais
    codigo espalhado do que esta checagem centralizada.
    """
    caixa = QWidget()
    dentro = QVBoxLayout(caixa)
    dentro.setContentsMargins(0, 0, 0, 0)
    dentro.setSpacing(espaco)
    for item in itens:
        if isinstance(item, QLayout):
            dentro.addLayout(item)
        else:
            dentro.addWidget(item)
    return caixa
