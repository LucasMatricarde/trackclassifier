"""O inspector da Biblioteca: a ficha tecnica da track selecionada.

O painel tem um trabalho so: dizer o que se sabe da track selecionada sem
exigir clique. Por isso a ficha e feita de pares rotulo/valor -- e nao da
linha unica de texto ("Genero: X / BPM: Y / ...") que existia antes: o olho
acha o numero pela posicao, e o valor numerico pode ficar em mono, que e a
regra do sistema para numero.

Key e Classe sao chip, nao texto: as duas sao categorias com cor propria no
resto do app (a roda de Camelot e o tom da classe), e mostrar so o texto
perderia a leitura que a tabela ja ensinou.

Sem selecao o painel mostra a mesma anatomia, vazia -- ver o estado vazio em
set_track(None). Nao ha setEnabled(False) no painel inteiro.
"""

from typing import NamedTuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...keys import KeyNotation
from ..tokens import (
    COLOR_TEXT_INVERSE,
    COLOR_TEXT_MUTED,
    FONT_FAMILY_MONO,
    RADIUS_XS,
    SPACE_1,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
)
from ..viewmodel import TrackRow, format_duration
from .class_tone import cor_base_do_rotulo
from .delegates import _inicial
from .key_chip import KeyChip
from .track_model import SEM_DADO
from .waveform_view import WaveformView

#: Valor numerico em mono, inline porque a regra do TechDetailValue no QSS
#: fixa a familia sans -- e inline ganha da folha.
_ESTILO_MONO = f"font-family: {FONT_FAMILY_MONO};"

#: O lado da capa. 120 e o do mockup: cabe na largura fixa do painel (260) com
#: os SPACE_6 de margem de cada lado e ainda deixa o titulo respirar.
_LADO_CAPA = 120

#: A capa fantasma do estado vazio: so a moldura, sem imagem. Deliberadamente
#: apagada -- um retangulo com fundo de destaque pareceria capa que nao carregou.
_ESTILO_CAPA_FANTASMA = (
    f"border: 1px solid {COLOR_TEXT_MUTED}; border-radius: {RADIUS_XS}px;"
)


class Par(NamedTuple):
    """Um par da ficha: a caixa e o valor.

    A caixa vem junto porque o par inteiro SOME quando o dado nao existe --
    esconder so o valor deixaria o nome orfao a esquerda, que e pior que nao
    mostrar nada.
    """

    caixa: QWidget
    valor: QWidget


class TrackInspector(QWidget):
    play_requested = Signal()
    classify_requested = Signal(str)
    #: Fracao da track (0..1) pedida por clique na onda.
    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TrackInspector")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(260)
        #: A linha selecionada. Guardada porque as guardas dependem dela (o
        #: clique na onda sem track -- ver _pede_seek).
        self._row: TrackRow | None = None

        self.cover = QLabel()
        self.cover.setFixedSize(_LADO_CAPA, _LADO_CAPA)
        self.cover.setScaledContents(True)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title = QLabel("Selecione uma musica")
        self.title.setObjectName("DashboardSectionTitle")
        self.title.setWordWrap(True)
        self.artist = QLabel("")
        self.artist.setObjectName("DashboardMuted")
        self.artist.setWordWrap(True)

        self.key_chip = KeyChip()
        # Camelot sempre, e explicito: o painel NAO segue o alternador de
        # notacao da tabela -- o rotulo do par diz qual notacao esta vendo, e
        # um chip que trocasse de texto sem aviso, aqui, mudaria de leitura sem
        # coluna de key ao lado para comparar.
        self.key_chip.set_notation(KeyNotation.CAMELOT)
        self.classe = self._valor()

        #: Os pares na ordem do design. "Confianca" entra sempre na montagem e
        #: so aparece quando existe: ver set_track().
        self.ficha: dict[str, Par] = {
            "Genero": self._par("Genero", self._valor()),
            "BPM": self._par("BPM", self._valor(mono=True)),
            "Key (Camelot)": self._par("Key (Camelot)", self.key_chip),
            "Duracao": self._par("Duracao", self._valor(mono=True)),
            "Classe atual": self._par("Classe atual", self.classe),
            "Confianca": self._par("Confianca", self._valor(mono=True)),
        }

        #: A onda da track selecionada: e a MESMA WaveformView da Revisao --
        #: buckets por banda quando existem, curva mono quando nao, playhead e
        #: clique para posicionar. Reusar o widget e o que faz a onda daqui e a
        #: de la serem a mesma leitura, que e o que o mockup pede.
        self.wave = WaveformView()
        self.wave.seek_requested.connect(self._pede_seek)

        self.play = QPushButton("▶  Reproduzir")
        self.play.clicked.connect(self.play_requested)
        #: As acoes ficam acessiveis porque o estado vazio as desliga UMA a uma:
        #: desabilitar o painel inteiro pintaria de cinza tambem os rotulos da
        #: ficha, que continuam sendo a informacao do que vai aparecer.
        self.class_buttons: list[QPushButton] = []
        actions = QVBoxLayout()
        actions.setSpacing(SPACE_4)
        for digit, label in enumerate(("-1", "neutra", "+1"), 1):
            button = QPushButton(f"{digit}  Classificar como {label}")
            button.clicked.connect(
                lambda _checked=False, value=label: self.classify_requested.emit(value)
            )
            self.class_buttons.append(button)
            actions.addWidget(button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_5)
        layout.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.artist)
        # A ficha vem logo abaixo do titulo: e a mesma coisa (o que e esta
        # track), em outra densidade.
        for par in self.ficha.values():
            layout.addWidget(par.caixa)
        layout.addWidget(self.wave)
        layout.addWidget(self.play)
        layout.addWidget(QLabel("Acoes rapidas"))
        layout.addLayout(actions)
        layout.addStretch(1)
        self.set_track(None)

    # ---- montagem ---------------------------------------------------------

    def _valor(self, *, mono: bool = False) -> QLabel:
        """Um valor padrao da ficha.

        Os objectNames sao os do rodape tecnico (TechDetailLabel/Value) de
        proposito: o par da ficha e o MESMO par do TechDetail, e reusar o nome
        evita uma regra de QSS nova para a mesma coisa.
        """
        valor = QLabel("")
        valor.setObjectName("TechDetailValue")
        if mono:
            valor.setStyleSheet(_ESTILO_MONO)
        return valor

    def _par(self, nome: str, valor: QWidget) -> Par:
        """Monta um par e devolve (caixa, valor). Nome a esquerda, valor a
        direita: o valor e o dado, e o olho varre a coluna da direita."""
        caixa = QWidget()
        linha = QHBoxLayout(caixa)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(SPACE_3)

        rotulo = QLabel(nome)
        rotulo.setObjectName("TechDetailLabel")
        linha.addWidget(rotulo)
        linha.addStretch(1)
        linha.addWidget(valor)
        return Par(caixa, valor)

    # ---- estado -----------------------------------------------------------

    def set_track(self, row: TrackRow | None) -> None:
        if row is None:
            self._limpa()
            return
        self._row = row
        # set_row ja zera o playhead: a fracao da track anterior nao pode ficar
        # marcada na onda da nova.
        self.wave.set_row(row)
        self.title.setText(row.display_title)
        self.artist.setText(row.artist or "")
        self._habilita_acoes(True)
        self._pinta_capa(row)
        self.ficha["Genero"].valor.setText(row.genre or SEM_DADO)
        # BPM 0 vira travessao, como na coluna da tabela: um acervo com BPM
        # zerado quase sempre e um erro de extracao, e "0" finge ser dado.
        self.ficha["BPM"].valor.setText(f"{row.bpm:.0f}" if row.bpm else SEM_DADO)
        self.key_chip.set_key(row.key)
        self.ficha["Duracao"].valor.setText(format_duration(row.duration_s))
        self._pinta_classe(row)
        # Confianca SO quando existe. Na Biblioteca ela e None por construcao
        # (a track ja esta classificada, e a confianca do modelo sobre uma
        # decisao humana tomada nao muda acao): uma linha fixa mostraria um
        # travessao permanente, que e a diferenca entre "nao se aplica" e
        # "faltou dado".
        tem_confianca = row.confidence is not None
        self.ficha["Confianca"].caixa.setVisible(tem_confianca)
        if row.confidence is not None:
            self.ficha["Confianca"].valor.setText(f"{row.confidence:.0%}")

    def _limpa(self) -> None:
        """A anatomia sem selecao: capa fantasma, campos vazios, acoes
        desabilitadas. O painel NAO fica cinza inteiro -- ver o docstring."""
        self._habilita_acoes(False)
        self._row = None
        self.wave.set_row(None)
        self.cover.clear()
        self.cover.setStyleSheet(_ESTILO_CAPA_FANTASMA)
        self.title.setText("Selecione uma musica")
        self.artist.setText("")
        self.ficha["Genero"].valor.setText("")
        self.ficha["BPM"].valor.setText("")
        self.key_chip.set_key(None)
        self.ficha["Duracao"].valor.setText("")
        self.classe.setText("")
        self.classe.setStyleSheet("")
        self.ficha["Confianca"].caixa.setVisible(False)
        self.ficha["Confianca"].valor.setText("")

    def set_peaks_path(self, sha1: str, caminho: str) -> None:
        """Buckets da track, quando o computo em segundo plano termina.

        Quem ignora bucket de OUTRA track e o proprio WaveformView (compara o
        sha1 com o da linha dele): um computo lento que chega depois de o usuario
        trocar de linha nao repinta a onda errada.
        """
        self.wave.set_peaks_path(sha1, caminho)

    def set_wave_progress(self, fracao: float) -> None:
        """O playhead da onda. Quem decide a fracao -- e so quando a track que
        soa E a selecionada -- e a aba: ver LibraryTab._atualiza_onda_do_inspector.
        """
        self.wave.set_progress(fracao)

    def _pede_seek(self, fracao: float) -> None:
        """Clique na onda so vale com track selecionada.

        O WaveformView emite sempre, porque ele nao sabe o que esta desenhando --
        no estado vazio, um clique na area da onda pediria seek da posicao de
        musica nenhuma.
        """
        if self._row is None:
            return
        self.seek_requested.emit(fracao)

    def _habilita_acoes(self, habilitado: bool) -> None:
        """Liga/desliga as ACOES -- e nao o painel.

        Sao coisas diferentes: desabilitar o painel inteiro apaga a anatomia
        (rotulos e a ficha ficam cinzas) e ainda deixa o texto de placeholder
        aceso. A acao sem track e que nao faz sentido, entao so ela desliga.
        """
        self.play.setEnabled(habilitado)
        for button in self.class_buttons:
            button.setEnabled(habilitado)

    def _pinta_capa(self, row: TrackRow) -> None:
        imagem = QPixmap(row.cover_path) if row.cover_path else QPixmap()
        if not imagem.isNull():
            self.cover.setText("")
            self.cover.setStyleSheet("")
            self.cover.setPixmap(imagem)
            return
        # Sem capa e o caso comum (acervo de promo sem tag, e sem tag nao ha
        # capa embutida): a area vira a INICIAL do titulo, e nao um vazio que
        # pareceria falha de carregamento. A regra da inicial e a mesma da
        # coluna Capa -- importada de la para nao virar duas regras.
        self.cover.clear()
        self.cover.setStyleSheet(_ESTILO_CAPA_FANTASMA)
        self.cover.setText(_inicial(row))

    def _pinta_classe(self, row: TrackRow) -> None:
        rotulo = row.label
        self.classe.setText(rotulo or SEM_DADO)
        if rotulo is None:
            self.classe.setStyleSheet("")
            return
        # Chip pintado a mao, como o do KeyChip: sem objectName proprio no QSS,
        # o fundo tem que sair daqui. cor_base_do_rotulo e o mapa unico de
        # rotulo -> matiz da classe (class_tone.py), e nao um hex local.
        self.classe.setStyleSheet(
            f"background: {cor_base_do_rotulo(rotulo)}; color: {COLOR_TEXT_INVERSE}; "
            f"border-radius: {RADIUS_XS}px; padding: {SPACE_1}px {SPACE_3}px;"
        )
