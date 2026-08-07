"""Falhas de analise agrupadas por categoria.

Quarenta arquivos com "ffmpeg nao encontrado" sao UM problema, nao
quarenta. A lista plana anterior fazia o usuario rolar quarenta linhas
para descobrir que ha uma coisa a consertar -- e o agrupamento so passou
a ser possivel depois que FailedItem ganhou categoria, porque `reason`
carrega o nome do arquivo e e unica por linha.
"""

from collections import defaultdict

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..colors import tinta
from ..tokens import (
    COLOR_STATE_DANGER,
    COLOR_SURFACE_1,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_SMALL,
    RADIUS_SM,
    RADIUS_XS,
    SPACE_3,
    SPACE_4,
    SPACE_5,
)
from ..typography import estiliza_label, texto_de_label

#: Quantos nomes cabem numa linha antes de virar "+N". Cinco e o que o
#: mockup mostra sem estourar a largura do card -- e nomes reais de promo
#: sao bem mais longos que os do mockup.
_ARQUIVOS_VISIVEIS = 5
_ALFA_BADGE = 0.12


def agrupa(failures: tuple[tuple[str, str, str], ...]) -> list[tuple[str, list[str]]]:
    """(categoria, arquivos), maior grupo primeiro."""
    por_categoria: dict[str, list[str]] = defaultdict(list)
    for filename, _reason, category in failures:
        por_categoria[category].append(filename)
    return sorted(por_categoria.items(), key=lambda item: -len(item[1]))


class FailureList(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        titulo = QLabel()
        titulo.setObjectName("MicroLabel")
        estiliza_label(titulo, "Falhas de analise")

        self.resumo = QLabel("")
        self.resumo.setObjectName("MicroLabel")

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(SPACE_5)
        cabecalho.addWidget(titulo)
        cabecalho.addWidget(self.resumo)
        cabecalho.addStretch(1)

        self._cards = QVBoxLayout()
        self._cards.setContentsMargins(0, 0, 0, 0)
        self._cards.setSpacing(SPACE_3)

        self._badges: list[QLabel] = []
        self._arquivos: list[QLabel] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_4)
        layout.addLayout(cabecalho)
        layout.addLayout(self._cards)
        layout.addStretch(1)

    def badge(self, indice: int) -> QLabel:
        return self._badges[indice]

    def arquivos(self, indice: int) -> QLabel:
        return self._arquivos[indice]

    def total_de_grupos(self) -> int:
        return len(self._badges)

    def set_failures(self, failures: tuple[tuple[str, str, str], ...]) -> None:
        self._limpa()
        # Secao some inteira sem falhas. Uma lista vazia com "nenhuma
        # falha" ocupa espaco para dizer que nao ha o que dizer.
        self.setVisible(bool(failures))
        if not failures:
            return

        grupos = agrupa(failures)
        self.resumo.setText(
            texto_de_label(f"{len(failures)} arquivos · {len(grupos)} motivos")
        )
        for categoria, arquivos in grupos:
            self._cards.addWidget(self._card(categoria, arquivos))

    def _limpa(self) -> None:
        # set_failures roda a cada atualizacao de estado da aba: sem isto
        # os cards do scan anterior empilhariam abaixo dos novos.
        self._badges.clear()
        self._arquivos.clear()
        while self._cards.count():
            item = self._cards.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _card(self, categoria: str, arquivos: list[str]) -> QWidget:
        badge = QLabel(str(len(arquivos)))
        badge.setObjectName("Numeric")
        badge.setStyleSheet(
            f"color: {COLOR_STATE_DANGER};"
            f"background: {tinta(COLOR_STATE_DANGER, _ALFA_BADGE)};"
            f"border-radius: {RADIUS_XS}px; padding: 2px 6px;"
            f"font-size: {FONT_SIZE_CAPTION};"
        )
        self._badges.append(badge)

        motivo = QLabel(categoria)
        motivo.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_SMALL};")

        topo = QHBoxLayout()
        topo.setContentsMargins(0, 0, 0, 0)
        topo.setSpacing(SPACE_5)
        topo.addWidget(badge)
        topo.addWidget(motivo)
        topo.addStretch(1)

        texto = " · ".join(arquivos[:_ARQUIVOS_VISIVEIS])
        if len(arquivos) > _ARQUIVOS_VISIVEIS:
            texto += f" · +{len(arquivos) - _ARQUIVOS_VISIVEIS}"
        nomes = QLabel(texto)
        nomes.setObjectName("Numeric")
        nomes.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION};")
        self._arquivos.append(nomes)

        card = QWidget()
        card.setStyleSheet(f"background: {COLOR_SURFACE_1}; border-radius: {RADIUS_SM}px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(SPACE_3)
        layout.addLayout(topo)
        layout.addWidget(nomes)
        return card
