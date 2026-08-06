"""Reproducao. Encapsula QMediaPlayer para o resto da UI nao depender dele.

QtMultimedia NAO faz parte do PySide6-Essentials -- vive no PySide6-Addons,
que e dependencia obrigatoria do projeto (todo `uv sync` instala os dois).
O try/except no import continua existindo so como degradacao defensiva --
mesma politica do resto do codebase (service.py, cache.py): um ambiente
com o pacote corrompido ou faltando por fora do fluxo normal de instalacao
cai num player simulado por QTimer em vez de derrubar a janela inteira.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

    MULTIMEDIA_AVAILABLE = True
except ImportError:  # pragma: no cover - depende do ambiente
    MULTIMEDIA_AVAILABLE = False


class BasePlayer(QObject):
    """Contrato de reproducao que a UI consome.

    A janela liga nos sinais daqui e nunca toca em QMediaPlayer direto --
    e isso que permite trocar o backend (ou nao ter nenhum) sem mexer na UI.
    """

    position_changed = Signal(int)   # ms
    duration_changed = Signal(int)   # ms
    playing_changed = Signal(bool)
    track_finished = Signal()
    error_occurred = Signal(str)

    def load(self, path: Path, duration_ms: int | None = None) -> None:
        raise NotImplementedError

    def play(self) -> None:
        raise NotImplementedError

    def pause(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def seek(self, milliseconds: int) -> None:
        raise NotImplementedError

    def set_volume(self, volume: float) -> None:
        raise NotImplementedError

    @property
    def is_playing(self) -> bool:
        raise NotImplementedError

    @property
    def duration_ms(self) -> int:
        raise NotImplementedError

    @property
    def position_ms(self) -> int:
        raise NotImplementedError

    # ---- conveniencias comuns aos dois backends -----------------------

    def toggle(self) -> None:
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def seek_fraction(self, fraction: float) -> None:
        """Seek por proporcao -- e o que a onda emite ao ser clicada."""
        duration = self.duration_ms
        if duration > 0:
            self.seek(int(min(1.0, max(0.0, fraction)) * duration))


class QtAudioPlayer(BasePlayer):
    """Backend real. QMediaPlayer ja decodifica fora da thread da UI."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._output)
        #: Duracao vinda da analise, valida ate o QMediaPlayer descobrir a
        #: dele. Ver load() e a property duration_ms.
        self._duracao_estimada = 0
        #: Posicao pedida antes de a midia terminar de abrir, reaplicada em
        #: _on_status. None quando nao ha nada pendente. Ver seek().
        self._posicao_pendente: int | None = None
        # No corpo de __init__, nao no corpo da classe: QMediaPlayer so
        # existe quando o import no topo do arquivo teve sucesso, e
        # QtAudioPlayer so e instanciada nesse caso (ver create_player()) --
        # um frozenset no corpo da classe rodaria na IMPORTACAO do modulo,
        # incondicionalmente, e quebraria a coleta de teste inteira em
        # qualquer maquina sem o extra `audio` instalado.
        self._status_terminais = frozenset(
            {
                QMediaPlayer.MediaStatus.LoadedMedia,
                QMediaPlayer.MediaStatus.InvalidMedia,
                QMediaPlayer.MediaStatus.NoMedia,
            }
        )

        # Conexao direta signal-pra-signal (sem lambda) falha em runtime com
        # PySide6-Addons 6.11.1, dentro OU fora do .app empacotado:
        # positionChanged e durationChanged do QMediaPlayer sao qlonglong, e
        # o PySide6 recusa conectar isso direto num Signal(int) (RuntimeError:
        # "Failed to connect signal positionChanged(qlonglong)"). Reproduz com
        # `uv run python`, sem PyInstaller no meio. Passar por uma lambda
        # troca a conversao pelo despacho Python do PySide6, que aceita.
        self._player.positionChanged.connect(lambda ms: self.position_changed.emit(ms))
        self._player.durationChanged.connect(lambda ms: self.duration_changed.emit(ms))
        self._player.playbackStateChanged.connect(
            lambda state: self.playing_changed.emit(
                state == QMediaPlayer.PlaybackState.PlayingState
            )
        )
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.errorOccurred.connect(
            lambda _error, message: self.error_occurred.emit(message)
        )

    def load(self, path: Path, duration_ms: int | None = None) -> None:
        # setSource nao e sincrono: o QMediaPlayer so conhece a duracao real
        # depois de abrir a midia e emitir durationChanged, e ate la
        # duration() devolve 0. Quem chama ja tem a duracao da analise em
        # maos, e sem guarda-la aqui o playhead da onda fica travado em x=0
        # durante todo o inicio da reproducao (_atualiza_progresso divide
        # pela duracao e desiste quando ela e 0).
        self._duracao_estimada = max(0, duration_ms or 0)
        self._posicao_pendente = None
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        if self._duracao_estimada:
            self.duration_changed.emit(self._duracao_estimada)

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def seek(self, milliseconds: int) -> None:
        alvo = max(0, milliseconds)
        # setPosition antes de a midia abrir e descartado em silencio, sem
        # emitir positionChanged. Quem chama e _atualiza_exibicao (que
        # posiciona no trecho mais energetico logo apos load) e o clique na
        # onda -- os dois ficariam sem efeito. Guardamos o alvo para
        # reaplicar em _on_status e emitimos ja, para o playhead responder.
        self._posicao_pendente = alvo
        self._player.setPosition(alvo)
        self.position_changed.emit(alvo)

    def set_volume(self, volume: float) -> None:
        self._output.setVolume(min(1.0, max(0.0, volume)))

    @property
    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def duration_ms(self) -> int:
        # A do QMediaPlayer prevalece assim que existe: e a duracao real do
        # arquivo, enquanto a estimada vem da analise e pode divergir por
        # alguns ms em formatos com header impreciso.
        return self._player.duration() or self._duracao_estimada

    @property
    def position_ms(self) -> int:
        if self._posicao_pendente is not None:
            return self._posicao_pendente
        return self._player.position()

    def _on_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.track_finished.emit()
            return
        if status not in self._status_terminais or self._posicao_pendente is None:
            return
        # `is None`, nunca truthiness: seek(0) e um pedido legitimo, e
        # `if self._posicao_pendente` nunca reaplicaria nem limparia esse
        # caso, deixando position_ms preso em 0 pro resto da track. Limpa em
        # QUALQUER status terminal (nao so LoadedMedia) -- sem isso um
        # InvalidMedia (arquivo corrompido) trava position_ms na ultima
        # posicao pedida para sempre, porque nenhum LoadedMedia futuro vem
        # zera-la.
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._player.setPosition(self._posicao_pendente)
        self._posicao_pendente = None


class SimulatedPlayer(BasePlayer):
    """Toca nada, mas anda no tempo. Serve ao esqueleto e aos testes.

    Emite posicao a ~60 fps para o playhead se mover com a mesma cadencia
    que teria com audio real -- se a onda engasgar aqui, engasga la.
    """

    TICK_MS = 16

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._duration = 0
        self._position = 0
        self._playing = False

        self._timer = QTimer(self)
        self._timer.setInterval(self.TICK_MS)
        self._timer.timeout.connect(self._tick)

    def load(self, path: Path, duration_ms: int | None = None) -> None:
        self.stop()
        self._duration = max(0, duration_ms or 0)
        self._position = 0
        self.duration_changed.emit(self._duration)
        self.position_changed.emit(0)

    def play(self) -> None:
        if self._duration <= 0 or self._playing:
            return
        self._playing = True
        self._timer.start()
        self.playing_changed.emit(True)

    def pause(self) -> None:
        if not self._playing:
            return
        self._playing = False
        self._timer.stop()
        self.playing_changed.emit(False)

    def stop(self) -> None:
        self.pause()
        self._position = 0
        self.position_changed.emit(0)

    def seek(self, milliseconds: int) -> None:
        self._position = max(0, min(self._duration, milliseconds))
        self.position_changed.emit(self._position)

    def set_volume(self, volume: float) -> None:
        pass

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def duration_ms(self) -> int:
        return self._duration

    @property
    def position_ms(self) -> int:
        return self._position

    def _tick(self) -> None:
        self._position += self.TICK_MS
        if self._position >= self._duration:
            self._position = self._duration
            self.pause()
            self.position_changed.emit(self._position)
            self.track_finished.emit()
            return
        self.position_changed.emit(self._position)


def create_player(parent: QObject | None = None) -> BasePlayer:
    """Devolve o backend disponivel. A UI nao precisa saber qual e."""
    return QtAudioPlayer(parent) if MULTIMEDIA_AVAILABLE else SimulatedPlayer(parent)
