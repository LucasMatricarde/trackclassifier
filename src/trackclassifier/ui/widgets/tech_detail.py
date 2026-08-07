"""Rodape tecnico recolhivel: alpha, cortes e extrator.

Sao os tres numeros reais e uteis DEPURANDO, e inuteis usando -- e a spec
da aba pede o mesmo tratamento do painel "por que este palpite" da
Revisao: resumo de uma linha quando fechado, valores nomeados quando
aberto.

A versao anterior era um card fixo com a mesma altura e o mesmo peso da
faixa de acao logo acima, competindo com ela pela atencao para mostrar o
que ninguem le. Aqui o rodape fechado e uma linha so, e o que ele custa
de tela e a altura de um botao.

O gatilho e QPushButton, nao um QWidget com mousePressEvent: assim o
rodape entra na ordem de Tab, abre com Espaco/Enter e um leitor de tela o
anuncia como controle -- de graca, so por ser botao. Mas o botao real do
app (variant="primary"/base) tem borda, padding largo e caixa alta -- o
peso certo para uma acao, errado para uma linha de metadado. Este botao
zera esse chrome todo via QSS de instancia (mais especifico que o global
QPushButton{} do app.qss) e fica so com o texto, igual a um QLabel
clicavel.

O fundo do card vem de `aplica_superficie` (ui/surface.py) -- e onde mora o
porque de precisar de WA_StyledBackground numa subclasse de QWidget como esta.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..surface import aplica_superficie
from ..tokens import (
    COLOR_SURFACE_1,
    COLOR_TEXT_DISABLED,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY_MONO,
    FONT_SIZE_CAPTION,
    RADIUS_SM,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_5,
    SPACE_8,
)

#: A seta e o unico indicador de que a linha abre. Sem ela o rodape fechado
#: parece um rotulo apagado, e ninguem clica num rotulo.
_FECHADA = "▸"
_ABERTA = "▾"

#: Sobrepoe o QPushButton generico do app.qss (borda, padding largo,
#: min-height, caixa alta): aqui o gatilho e uma linha de metadado, nao
#: uma acao, e precisa pesar igual ao "real x previsto" da matriz -- texto
#: solto, sem moldura. setStyleSheet de instancia vence o global por ser
#: mais especifico, entao isto some com o chrome sem afetar outros botoes.
_ESTILO_GATILHO = f"""
QPushButton {{
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0;
    min-height: 0;
    color: {COLOR_TEXT_MUTED};
    font-family: {FONT_FAMILY_MONO};
    font-size: {FONT_SIZE_CAPTION};
    text-align: left;
}}
QPushButton:hover {{ background: transparent; color: {COLOR_TEXT_SECONDARY}; }}
QPushButton:pressed {{ background: transparent; color: {COLOR_TEXT_SECONDARY}; }}
"""


class TechDetail(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        aplica_superficie(self, COLOR_SURFACE_1, RADIUS_SM)

        self.botao = QPushButton()
        self.botao.setStyleSheet(_ESTILO_GATILHO)
        self.botao.setCursor(Qt.CursorShape.PointingHandCursor)
        self.botao.setCheckable(True)
        self.botao.toggled.connect(self._aplica_estado)

        self.resumo = QLabel("")
        self.resumo.setObjectName("Numeric")
        self.resumo.setStyleSheet(
            f"color: {COLOR_TEXT_DISABLED}; font-size: {FONT_SIZE_CAPTION};"
        )

        cabecalho = QHBoxLayout()
        cabecalho.setContentsMargins(0, 0, 0, 0)
        cabecalho.setSpacing(SPACE_3)
        cabecalho.addWidget(self.botao)
        cabecalho.addWidget(self.resumo)
        cabecalho.addStretch(1)

        self.corpo = QWidget()
        corpo = QHBoxLayout(self.corpo)
        # A esquerda alinha com o texto do botao acima (4 do card + 12 do
        # padding do botao), nao com a borda do card.
        corpo.setContentsMargins(SPACE_5, 0, 0, SPACE_2)
        corpo.setSpacing(SPACE_8)
        self._caixa_alpha, self._alpha = self._par(corpo, "alpha")
        self._caixa_cortes, self._cortes = self._par(corpo, "cortes")
        _, self._extrator = self._par(corpo, "extrator")
        corpo.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_2, SPACE_1, SPACE_5, SPACE_1)
        layout.setSpacing(SPACE_3)
        layout.addLayout(cabecalho)
        layout.addWidget(self.corpo)

        self._aplica_estado(False)

    def _par(self, layout: QHBoxLayout, nome: str) -> tuple[QWidget, QLabel]:
        """Nome apagado, valor em destaque. Devolve (caixa, valor).

        A caixa volta junto porque o par inteiro some quando o modelo nao
        treinou -- esconder o valor e deixar o nome orfao seria pior que
        nao mostrar nada.
        """
        par = QWidget()
        linha = QHBoxLayout(par)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(SPACE_3)

        rotulo = QLabel(nome)
        rotulo.setObjectName("Numeric")
        rotulo.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};"
        )

        valor = QLabel("")
        valor.setObjectName("Numeric")
        valor.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_CAPTION};"
        )

        linha.addWidget(rotulo)
        linha.addWidget(valor)
        layout.addWidget(par)
        return par, valor

    def _aplica_estado(self, aberto: bool) -> None:
        # Caixa normal, nao caixa alta: "Detalhe tecnico" e um rotulo de
        # linha, nao um cabecalho de secao -- o tratamento MicroLabel
        # (uppercase + tracking.widest) e pesado demais para uma linha que
        # so quer ser lida, nao anunciada.
        self.botao.setText(f"{_ABERTA if aberto else _FECHADA} Detalhe tecnico")
        # Resumo e corpo dizem a mesma coisa em densidades diferentes:
        # mostrar os dois juntos e repeticao, nao contexto.
        self.corpo.setVisible(aberto)
        self.resumo.setVisible(not aberto)

    def set_detail(
        self,
        alpha: float | None,
        thresholds: tuple[float, float] | None,
        extractor_name: str,
    ) -> None:
        self.resumo.setText(resumo_tecnico(alpha, thresholds, extractor_name))

        self._caixa_alpha.setVisible(alpha is not None)
        if alpha is not None:
            self._alpha.setText(f"{alpha:.2f}")

        self._caixa_cortes.setVisible(thresholds is not None)
        if thresholds is not None:
            self._cortes.setText(f"{thresholds[0]:.3f} / {thresholds[1]:.3f}")

        self._extrator.setText(extractor_name)


def resumo_tecnico(
    alpha: float | None,
    thresholds: tuple[float, float] | None,
    extractor_name: str,
) -> str:
    """Uma linha do que so interessa depurando.

    Sem treino nao mostra alpha nem cortes: os dois tem default no
    TrackModel e exibi-los aqui os faria parecer resultado de treino.
    """
    if alpha is None or thresholds is None:
        return extractor_name
    t1, t2 = thresholds
    return f"alpha {alpha:.2f} · cortes {t1:.3f} / {t2:.3f} · {extractor_name}"
