"""Capa de track com cantos arredondados.

QLabel nao recorta pixmap: border-radius no QSS arredonda o FUNDO do
label, mas a imagem continua retangular desenhada por cima -- era por isso
que a capa da Revisao saia quadrada mesmo com o token de raio aplicado.
O recorte precisa de QPainter com clip path, entao a capa vira um widget
que se pinta. Usado pela ReviewHeader (raio control, a excecao de 8px do
mockup) e pela fila (raio sm).
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget


class CoverArt(QWidget):
    def __init__(self, tamanho: int, raio: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(tamanho, tamanho)
        self._raio = raio
        self._pixmap = QPixmap()

    def set_cover(self, caminho: str | None) -> None:
        """Troca a imagem; esconde o widget quando a track nao tem capa."""
        self._pixmap = QPixmap(caminho) if caminho else QPixmap()
        self.setVisible(not self._pixmap.isNull())
        self.update()

    def tem_capa(self) -> bool:
        return not self._pixmap.isNull()

    def paintEvent(self, _evento) -> None:
        if self._pixmap.isNull():
            return
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        moldura = QPainterPath()
        moldura.addRoundedRect(0, 0, self.width(), self.height(), self._raio, self._raio)
        pintor.setClipPath(moldura)
        # Escala cobrindo o quadrado e corta o excesso no centro: capas
        # quase-quadradas (720x700) nao podem deformar nem deixar faixa.
        dpr = self.devicePixelRatioF()
        alvo = self.size() * dpr
        escalada = self._pixmap.scaled(
            alvo,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        escalada.setDevicePixelRatio(dpr)
        x = (self.width() - escalada.width() / dpr) / 2
        y = (self.height() - escalada.height() / dpr) / 2
        pintor.drawPixmap(int(x), int(y), escalada)
        pintor.end()
