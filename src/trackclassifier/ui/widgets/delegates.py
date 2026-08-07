"""Delegates da tabela. Tudo que QSS nao alcanca e pintado aqui."""

from PySide6.QtCore import QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from ..colors import para_qcolor
from ..tokens import (
    COLOR_BORDER_DEFAULT,
    COLOR_STATE_DANGER,
    COLOR_SURFACE_2,
    COLOR_SURFACE_WAVEFORM,
    COLOR_TEXT_DISABLED,
    COLOR_TEXT_INVERSE,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY_MONO,
    RADIUS_SM,
    RADIUS_XS,
    SIZE_ART_ROW_COMFORTABLE,
    SIZE_ROW_COMFORTABLE,
    SIZE_WAVE_BAR,
    SPACE_4,
    camelot_color,
    classification_base,
)
from ..viewmodel import LABELS_EM_ORDEM, TrackRow
from .thumbs import load_thumbnail
from .waveform_render import PixmapCache, load_peaks, render_bands, render_curve

#: Quanto o artista e menor que o titulo. O mockup usa 12px/11px na linha
#: -- a razao e ~0.92, um ponto de diferenca no tamanho base da tabela.
_ESCALA_ARTISTA = 0.92

#: Travessao no lugar do artista ausente. O mesmo que track_model.SEM_DADO
#: usa nas colunas de texto -- repetido aqui para nao importar o modelo, que
#: importa este arquivo (ciclo).
SEM_ARTISTA = "—"

#: Segmento da escala ordinal. 9x9 com gap 3, do LEIA-ME do pack. Nenhum
#: dos dois cai na escala de espaco (SPACE_1 e 2, SPACE_2 e 4) porque nao
#: sao espacamento de layout -- sao a dimensao de um glifo desenhado, do
#: mesmo tipo que SIZE_WAVE_BAR.
_LADO_SEGMENTO = 9
_GAP_SEGMENTO = 3
#: Largura da coluna de classe, do LEIA-ME. Repetida aqui porque o
#: sizeHint roda antes de a aba aplicar as larguras do track_model.
_LARGURA_CLASSE = 72

#: Altura da faixa da onda por densidade, do LEIA-ME. SIZE_WAVE_ROW (24) e
#: da v0.1 e nao serve a nenhuma das duas: a rodada 3a fechou em 28 e 20.
SIZE_WAVE_ROW_COMFORTABLE = 28
SIZE_WAVE_ROW_COMPACT = 20

#: Role customizado: os delegates pedem a TrackRow inteira por aqui, em vez
#: de reconstruir dados a partir das strings de DisplayRole.
TRACK_ROLE = Qt.ItemDataRole.UserRole + 1

#: Rotulo do dominio (labels.Label) -> nome do chip no design system.
#: A traducao mora aqui porque tokens.py e gerado e nao pode conhecer o
#: dominio, e viewmodel.py nao pode conhecer o design system.
_CHIP = {"+1": "animada", "neutra": "neutro", "-1": "lento"}
_TEXTO = {"+1": "+1", "neutra": "neutra", "-1": "-1"}


class _DelegateComFundo(QStyledItemDelegate):
    """Base dos delegates que pintam a celula inteira a mao.

    QStyledItemDelegate.paint desenha o fundo do item (selecao, hover, linha
    alternada) antes do conteudo. Um paint() sobrescrito que nunca chama a
    base pinta so o conteudo, e o fundo some -- na tabela da Biblioteca isso
    aparece como a linha selecionada se apagando exatamente sob as colunas
    Onda e Classificacao, as duas que tem delegate. Redesenhar pelo proprio
    QStyle (e nao com uma cor fixa) e o que mantem app.qss no comando:
    selection-background-color de la continua valendo.
    """

    def _pinta_fundo(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        opcao = QStyleOptionViewItem(option)
        self.initStyleOption(opcao, index)
        # initStyleOption puxa o texto do DisplayRole. Estas colunas nao tem
        # nenhum, mas zerar deixa explicito que aqui so o fundo e desenhado.
        opcao.text = ""
        estilo = opcao.widget.style() if opcao.widget else QApplication.style()
        estilo.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, opcao, painter, opcao.widget
        )


class WaveformDelegate(_DelegateComFundo):
    """Pinta a mini onda da linha. RGB quando ha buckets, mono quando nao.

    O pixmap e cacheado por (sha1, largura, altura). O paint() nunca
    decodifica audio nem recalcula a curva -- so faz drawPixmap.

    **Este delegate nao PEDE computo de buckets.** Quem pede e a aba, olhando
    o viewport (`LibraryTab._pede_peaks_visiveis`). A versao anterior emitia
    daqui, uma vez por sha1, e a dedup por sha1 parecia suficiente -- nao era:
    rolar uma biblioteca de 354 tracks pintava as 300 sem buckets uma vez cada
    e enfileirava 300 computos de ~0,4 s na thread do servico. Essa thread e a
    MESMA que atende decide/undo/train, e os slots dela sao servidos em ordem
    de chegada: depois de um scroll ate o fim, teclar 1/2/3 ficava sem resposta
    por ~2 minutos. paint() nao tem como saber o que continua na tela, e a aba
    tem -- por isso a decisao subiu de camada.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        margin: int = 4,
        altura: int = SIZE_WAVE_ROW_COMFORTABLE,
    ) -> None:
        super().__init__(parent)
        self._cache = PixmapCache(capacity=256)
        self._margin = margin
        #: Altura da faixa desenhada, independente da altura da celula: a
        #: onda e uma caixa centrada de 28 (comfortable) ou 20 (compact),
        #: nao a celula inteira menos margem. Amarrar a altura da linha
        #: faria a onda esticar junto com qualquer folga de layout.
        self._altura = altura
        #: sha1 -> caminho, aprendido via registrar_peaks sem passar por um
        #: refresh completo (que resetaria a selecao da tabela inteira).
        #: Prevalece sobre TrackRow.peaks_path, que so seria atualizado no
        #: proximo refresh de verdade.
        self._peaks_locais: dict[str, str] = {}
        #: sha1 -> motivo. Alimentado pela aba a partir de service.failures().
        #: A falha e estado DE LINHA: o usuario ve qual track falhou sem
        #: trocar para a aba Modelo.
        self._falhas: dict[str, str] = {}

    def registrar_falha(self, sha1: str, motivo: str) -> None:
        self._falhas[sha1] = motivo

    def limpar_falhas(self) -> None:
        self._falhas.clear()

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        # Sempre antes de qualquer `return`: uma celula sem onda para desenhar
        # continua sendo uma celula selecionavel.
        self._pinta_fundo(painter, option, index)

        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None:
            return

        rect = QRect(0, 0, max(0, option.rect.width() - self._margin * 2), self._altura)
        rect.moveCenter(option.rect.center())
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # A caixa vem SEMPRE, antes de decidir o que vai dentro: e ela que
        # reserva o espaco e faz o layout nao pular quando a analise chega
        # durante o scroll. Sem ela, a linha pendente parece erro de render.
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLOR_SURFACE_WAVEFORM))
        painter.drawRoundedRect(rect, float(RADIUS_XS), float(RADIUS_XS))
        painter.restore()

        motivo = self._falhas.get(linha.sha1)
        if motivo is not None:
            painter.save()
            painter.setPen(QColor(COLOR_STATE_DANGER))
            painter.drawText(
                rect.adjusted(self._margin, 0, -self._margin, 0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                QFontMetrics(option.font).elidedText(
                    motivo, Qt.TextElideMode.ElideRight, rect.width() - self._margin * 2
                ),
            )
            painter.restore()
            return

        caminho_peaks = self._peaks_locais.get(linha.sha1) or linha.peaks_path
        # A chave inclui se o render e RGB ou mono: sem isso, o pixmap mono
        # cacheado continuaria sendo servido depois de os buckets chegarem, e
        # a linha so viraria colorida ao ser redimensionada. O modo vem da
        # EXISTENCIA do caminho, nao do sucesso de load_peaks -- checar o
        # cache primeiro e so ler o disco no miss e o que faz paint() nao
        # decodificar nada a cada quadro durante o scroll.
        modo = "rgb" if caminho_peaks is not None else "mono"
        chave = (f"{linha.sha1}:{modo}", rect.width(), rect.height())
        pixmap = self._cache.get(chave)

        if pixmap is None:
            picos = load_peaks(caminho_peaks)
            if picos is not None:
                pixmap = render_bands(
                    picos, QSize(rect.width(), rect.height()), bar_width=SIZE_WAVE_BAR, gap=0
                )
            elif linha.energy_curve:
                pixmap = render_curve(
                    linha.energy_curve,
                    QSize(rect.width(), rect.height()),
                    bar_width=SIZE_WAVE_BAR,
                    gap=0,
                )
            if pixmap is not None:
                self._cache.put(chave, pixmap)

        if pixmap is not None:
            painter.drawPixmap(rect.topLeft(), pixmap)

    def registrar_peaks(self, sha1: str, caminho: str) -> None:
        """Chamado pela aba quando peaks_ready dispara para esta sha1."""
        self._peaks_locais[sha1] = caminho

    def tem_peaks(self, sha1: str) -> bool:
        """Se a aba ja registrou buckets para esta sha1 desde o ultimo refresh.

        A aba consulta antes de pedir computo: `TrackRow.peaks_path` so seria
        atualizado no proximo refresh completo, entao sem isto uma track que
        acabou de ganhar buckets seria pedida de novo enquanto continuasse no
        viewport.
        """
        return sha1 in self._peaks_locais

    def clear_cache(self) -> None:
        self._cache.clear()


class CoverDelegate(_DelegateComFundo):
    """A capa como bloco ancora da linha, em coluna propria.

    Ate a v0.1 a capa era desenhada dentro do TitleDelegate. O efeito era
    o titulo comecar em x variavel: quando o jpeg falhava ao abrir, o
    placeholder tinha outra largura e a coluna inteira dancava. Coluna
    separada de largura fixa resolve por construcao.

    O pixmap e cacheado por (sha1, largura, altura) no mesmo TIPO de cache do
    render da onda (PixmapCache), mas em instancia PROPRIA -- compartilhar o
    LRU colidiria a chave (sha1, w, h) entre a onda e a capa de uma mesma
    track. paint() roda dezenas de vezes por segundo durante o scroll, e
    abrir o jpeg do disco em cada chamada transforma a rolagem em I/O.

    A leitura em si mora em `thumbs.py`, que prefere o thumb reduzido em disco
    a capa original -- e la que esta o motivo, com os numeros medidos.

    **Dois estados, nao tres.** A spec previa "carregando" como um terceiro
    visual (caixa vazia em surface.1) e ele nao existe nesta arquitetura:
    `load_thumbnail` e sincrono dentro do paint, entao ou a miniatura sai
    naquele quadro ou nao ha capa. Implementar o terceiro estado seria
    codigo que nenhum caminho alcanca.
    """

    def __init__(self, parent: QWidget | None = None, lado: int = SIZE_ART_ROW_COMFORTABLE):
        super().__init__(parent)
        # Capacidade bem acima da onda (256): uma miniatura de 38px ocupa
        # ~4 KB, entao cobrir uma biblioteca inteira custa poucos MB. Com 256
        # o cache nao cabia as 354 linhas do acervo real, e uma segunda
        # passada de scroll redecodificava o que a primeira ja tinha lido.
        self._cache = PixmapCache(capacity=1024)
        self._lado = lado
        #: Contador de leituras de disco. Existe para o teste provar que o
        #: cache esta sendo usado; nada na UI depende dele.
        self._leituras = 0

    def _miniatura(self, linha: TrackRow, lado: int) -> QPixmap | None:
        if linha.cover_path is None:
            return None

        chave = (linha.sha1, lado, lado)
        pixmap = self._cache.get(chave)
        if pixmap is not None:
            return pixmap

        self._leituras += 1
        pixmap = load_thumbnail(linha.cover_path, lado)
        if pixmap is None:
            # Arquivo corrompido ou formato que o Qt nao abre. Cai no
            # placeholder em vez de deixar a celula sem nada.
            return None

        self._cache.put(chave, pixmap)
        return pixmap

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        self._pinta_fundo(painter, option, index)

        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None:
            return

        lado = min(self._lado, option.rect.height())
        if lado <= 0:
            return
        arte = QRect(0, 0, lado, lado)
        arte.moveCenter(option.rect.center())

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        miniatura = self._miniatura(linha, lado)
        if miniatura is not None:
            painter.drawPixmap(arte, miniatura)
        else:
            # Inicial do titulo em mono, nao um icone generico: um mesmo
            # icone repetido em 341 linhas vira ruido e compete com as
            # capas reais. E NAO tingir com a cor de Camelot -- fica bonito
            # e mente, porque pareceria que a capa carrega significado
            # quando ela so esta ausente.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLOR_SURFACE_2))
            painter.drawRoundedRect(arte, float(RADIUS_SM), float(RADIUS_SM))
            fonte = QFont(option.font)
            fonte.setFamily(FONT_FAMILY_MONO.split(",")[0])
            painter.setFont(fonte)
            painter.setPen(QColor(COLOR_TEXT_DISABLED))
            painter.drawText(arte, Qt.AlignmentFlag.AlignCenter, _inicial(linha))
        painter.restore()

    def clear_cache(self) -> None:
        self._cache.clear()


def _inicial(linha: TrackRow) -> str:
    """Primeira letra do titulo EXIBIDO, e nao do nome do arquivo.

    Numa biblioteca de promos metade dos arquivos comeca com "01_" ou
    "A1-", e a inicial viraria "0" em metade das linhas -- o que nao
    distingue nada, que e a unica coisa que a inicial precisa fazer.
    """
    for caractere in linha.display_title:
        if caractere.isalnum():
            return caractere.upper()
    return "?"


class TitleDelegate(_DelegateComFundo):
    """Titulo em peso medio e artista em text.secondary, na mesma linha.

    A capa saiu daqui na Fase 2 e virou CoverDelegate. O artista entrou:
    ate a v0.1 era coluna propria, e no mockup 3a os dois dividem a mesma
    coluna elastica -- titulo primeiro, artista logo depois em cor mais
    apagada, como um credito.

    O titulo tem prioridade no elide: com pouca largura, o artista some
    antes. Um titulo cortado no meio identifica menos que um titulo
    inteiro sem artista.
    """

    def __init__(self, parent: QWidget | None = None, margin: int = 6) -> None:
        super().__init__(parent)
        self._margin = margin
        #: Distancia entre titulo e artista. O mockup usa 8 (SPACE_4).
        self._gap = SPACE_4

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        self._pinta_fundo(painter, option, index)

        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None:
            return

        rect = option.rect.adjusted(self._margin, 0, -self._margin, 0)
        if rect.width() <= 0:
            return

        fonte_titulo = QFont(option.font)
        fonte_titulo.setWeight(QFont.Weight.Medium)
        metricas_titulo = QFontMetrics(fonte_titulo)
        titulo = metricas_titulo.elidedText(
            linha.display_title, Qt.TextElideMode.ElideRight, rect.width()
        )
        largura_titulo = metricas_titulo.horizontalAdvance(titulo)

        painter.save()
        painter.setFont(fonte_titulo)
        painter.setPen(option.palette.text().color())
        painter.drawText(
            rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, titulo
        )

        sobra = rect.width() - largura_titulo - self._gap
        if sobra > 0:
            fonte_artista = QFont(option.font)
            fonte_artista.setPointSizeF(fonte_artista.pointSizeF() * _ESCALA_ARTISTA)
            metricas_artista = QFontMetrics(fonte_artista)
            # Travessao quando nao ha artista: string vazia deixaria um
            # buraco que parece bug de render, e a coluna e a mesma para
            # linhas com e sem tag.
            artista = metricas_artista.elidedText(
                linha.artist or SEM_ARTISTA, Qt.TextElideMode.ElideRight, sobra
            )
            painter.setFont(fonte_artista)
            painter.setPen(QColor(COLOR_TEXT_SECONDARY))
            painter.drawText(
                rect.adjusted(largura_titulo + self._gap, 0, 0, 0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                artista,
            )
        painter.restore()


class ClassificationDelegate(_DelegateComFundo):
    """Escala ordinal de tres segmentos, na ordem de LABEL_ORDER.

    Substitui o chip de texto da v0.1. Duas razoes:

    - As tres classes sao ORDENADAS. Uma escala de tres posicoes carrega
      isso na forma; um chip com o texto "+1" nao carrega nada alem do
      texto, e o olho tem que traduzir.
    - O chip colorido competia com o chip de Camelot na coluna ao lado.
      Dois retangulos coloridos de largura parecida, um do lado do outro,
      leem como a mesma familia de informacao -- e nao sao.

    Sem classe, os tres contornos continuam desenhados. Pendente e "nenhum
    aceso", nao "coluna vazia": a caixa reservada mantem as colunas
    seguintes alinhadas e nao parece erro de render.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lado = _LADO_SEGMENTO
        self._gap = _GAP_SEGMENTO

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        # Idem WaveformDelegate: o fundo vem antes de qualquer desistencia.
        self._pinta_fundo(painter, option, index)

        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None:
            return

        # A previsao acende igual a classificacao manual: para quem olha a
        # lista, "o modelo acha que e +1" e "eu disse que e +1" ocupam a
        # mesma posicao na escala. A distincao entre as duas e a coluna de
        # classificacao vs. a fila da Revisao, nao a cor do segmento.
        rotulo = linha.label or linha.predicted
        aceso = LABELS_EM_ORDEM.index(rotulo) if rotulo in LABELS_EM_ORDEM else None

        largura = self._lado * 3 + self._gap * 2
        origem = option.rect.center().x() - largura // 2
        topo = option.rect.center().y() - self._lado // 2

        painter.save()
        for posicao in range(3):
            quadro = QRect(
                origem + posicao * (self._lado + self._gap), topo, self._lado, self._lado
            )
            if posicao == aceso:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(classification_base(_CHIP[LABELS_EM_ORDEM[posicao]])))
                painter.drawRect(quadro)
            else:
                # Contorno sem preenchimento: um segmento apagado com fundo
                # leria como um quarto estado ("meio aceso").
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(para_qcolor(COLOR_BORDER_DEFAULT))
                painter.drawRect(quadro.adjusted(0, 0, -1, -1))
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(_LARGURA_CLASSE, SIZE_ROW_COMFORTABLE)


class KeyDelegate(_DelegateComFundo):
    """Chip da tonalidade, colorido pela posicao na roda de Camelot.

    O texto vem do DisplayRole (o modelo ja formatou na notacao corrente);
    aqui so se desenha o fundo colorido. Sem key, nao ha chip -- o travessao
    do DisplayRole e desenhado como texto simples, porque um chip cinza
    sugeriria que a track tem tonalidade e o app so nao soube formatar.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius = 4.0
        self._padding_h = 6
        self._padding_v = 3

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        self._pinta_fundo(painter, option, index)

        linha: TrackRow | None = index.data(TRACK_ROLE)
        if linha is None:
            return

        texto = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if not texto:
            return

        metricas = QFontMetrics(option.font)
        largura = metricas.horizontalAdvance(texto) + self._padding_h * 2
        altura = metricas.height() + self._padding_v * 2
        chip = QRect(0, 0, largura, altura)
        chip.moveCenter(option.rect.center())

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if linha.key is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(camelot_color(linha.key.camelot_number)))
            painter.drawRoundedRect(chip, self._radius, self._radius)
            painter.setPen(QColor(COLOR_TEXT_INVERSE))
        else:
            painter.setPen(option.palette.text().color())
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, texto)
        painter.restore()
