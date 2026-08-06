"""Reproducao. Encapsula QMediaPlayer para o resto da UI nao depender dele.

QtMultimedia NAO faz parte do PySide6-Essentials -- vive no PySide6-Addons.
Como o esqueleto roda com dados mockados, o import e opcional: sem o modulo,
entra um player simulado por QTimer que move o playhead e permite exercitar
toda a UI. Instale `PySide6-Addons` quando for tocar audio de verdade.
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

        self._player.positionChanged.connect(self.position_changed)
        self._player.durationChanged.connect(self.duration_changed)
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
        self._player.setSource(QUrl.fromLocalFile(str(path)))

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def seek(self, milliseconds: int) -> None:
        self._player.setPosition(max(0, milliseconds))

    def set_volume(self, volume: float) -> None:
        self._output.setVolume(min(1.0, max(0.0, volume)))

    @property
    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def duration_ms(self) -> int:
        return self._player.duration()

    @property
    def position_ms(self) -> int:
        return self._player.position()

    def _on_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.track_finished.emit()


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
