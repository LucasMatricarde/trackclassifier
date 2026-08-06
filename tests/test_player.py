from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtTest import QTest

from trackclassifier.ui.widgets.player import (
    MULTIMEDIA_AVAILABLE,
    SimulatedPlayer,
    create_player,
)

#: PySide6-Addons e dependencia obrigatoria (ver pyproject.toml) -- isto so
#: pula num ambiente com o pacote quebrado ou instalado por fora do uv sync
#: normal, o mesmo caso defensivo que o try/except em player.py cobre.
so_com_audio = pytest.mark.skipif(
    not MULTIMEDIA_AVAILABLE, reason="PySide6-Addons ausente ou quebrado no ambiente"
)


def test_create_player_devolve_um_backend(qapp):
    assert create_player() is not None


@so_com_audio
def test_player_real_conhece_a_duracao_logo_apos_load(qapp, tmp_path):
    """QMediaPlayer abre a midia de forma assincrona: duration() e 0 ate ele
    emitir durationChanged. Sem a duracao da analise guardada em load(), o
    playhead da onda ficaria travado em x=0 o inicio inteiro da reproducao,
    porque _atualiza_progresso divide pela duracao e desiste quando ela e 0.
    """
    from trackclassifier.ui.widgets.player import QtAudioPlayer

    caminho = tmp_path / "track.wav"
    sf.write(caminho, np.zeros(22050), 22050)

    player = QtAudioPlayer()
    player.load(caminho, duration_ms=1_000)

    assert player.duration_ms == 1_000


@so_com_audio
def test_player_real_guarda_o_seek_pedido_antes_de_a_midia_abrir(qapp, tmp_path):
    """setPosition antes de a midia abrir e descartado em silencio pelo Qt.
    A Revisao posiciona no trecho mais energetico logo apos load, entao sem
    a posicao pendente esse seek se perderia em toda track.
    """
    from trackclassifier.ui.widgets.player import QtAudioPlayer

    caminho = tmp_path / "track.wav"
    sf.write(caminho, np.zeros(22050), 22050)

    player = QtAudioPlayer()
    player.load(caminho, duration_ms=1_000)
    player.seek(400)

    assert player.position_ms == 400


@so_com_audio
def test_player_real_emite_posicao_no_seek(qapp, tmp_path):
    """O playhead da onda anda por position_changed. Se o seek nao emitir
    enquanto a midia ainda abre, o clique na onda nao move nada.
    """
    from trackclassifier.ui.widgets.player import QtAudioPlayer

    caminho = tmp_path / "track.wav"
    sf.write(caminho, np.zeros(22050), 22050)

    player = QtAudioPlayer()
    player.load(caminho, duration_ms=1_000)

    recebidas = []
    player.position_changed.connect(recebidas.append)
    player.seek(250)

    assert recebidas == [250]


def _espera_status(player, status, timeout_ms=5_000):
    for _ in range(timeout_ms // 10):
        if player._player.mediaStatus() == status:
            return True
        QTest.qWait(10)
    return False


@so_com_audio
def test_player_real_aplica_a_posicao_pendente_de_verdade_no_qmediaplayer(qapp, tmp_path):
    """O caching em _posicao_pendente e so o meio -- o que importa e o
    QMediaPlayer real acabar posicionado la. Sem isto, um bug que faz
    _on_status nunca chamar setPosition passaria despercebido: os outros
    testes so olham o valor em cache, nunca o backend de verdade.
    """
    from PySide6.QtMultimedia import QMediaPlayer

    from trackclassifier.ui.widgets.player import QtAudioPlayer

    caminho = tmp_path / "track.wav"
    sf.write(caminho, np.zeros(22050 * 2), 22050)

    player = QtAudioPlayer()
    player.load(caminho, duration_ms=2_000)
    player.seek(500)

    assert _espera_status(player, QMediaPlayer.MediaStatus.LoadedMedia), (
        "QMediaPlayer nunca chegou a LoadedMedia -- teste nao provou nada"
    )
    # A tolerancia existe porque QMediaPlayer.position() arredonda pro frame
    # de audio mais proximo, nao pro milissegundo exato pedido.
    assert abs(player._player.position() - 500) < 50
    assert player._posicao_pendente is None


@so_com_audio
def test_player_real_nao_prende_position_ms_em_seek_zero(qapp, tmp_path):
    """seek(0) e um pedido legitimo (e o caso comum: peak_offset_s == 0.0
    quando o trecho mais energetico e o inicio da track). _posicao_pendente
    e falsy nesse caso -- se _on_status checar truthiness em vez de
    `is not None`, o seek nunca e reaplicado nem limpo, e position_ms fica
    preso em 0 pelo resto da track inteira, mesmo com audio tocando.
    """
    from PySide6.QtMultimedia import QMediaPlayer

    from trackclassifier.ui.widgets.player import QtAudioPlayer

    caminho = tmp_path / "track.wav"
    sf.write(caminho, np.zeros(22050 * 2), 22050)

    player = QtAudioPlayer()
    player.load(caminho, duration_ms=2_000)
    player.seek(0)

    assert _espera_status(player, QMediaPlayer.MediaStatus.LoadedMedia)
    assert player._posicao_pendente is None


def test_simulated_player_comeca_parado_no_zero(qapp):
    player = SimulatedPlayer()
    player.load(Path("qualquer.wav"), duration_ms=10_000)

    assert player.is_playing is False
    assert player.position_ms == 0
    assert player.duration_ms == 10_000


def test_simulated_player_nao_toca_sem_duracao(qapp):
    player = SimulatedPlayer()
    player.load(Path("qualquer.wav"), duration_ms=0)
    player.play()

    assert player.is_playing is False


def test_seek_fraction_converte_proporcao_em_milissegundos(qapp):
    player = SimulatedPlayer()
    player.load(Path("qualquer.wav"), duration_ms=10_000)

    player.seek_fraction(0.25)
    assert player.position_ms == 2_500

    # Fora de [0,1] satura em vez de estourar -- a onda emite a proporcao
    # do clique, e um clique na borda pode passar de 1 por um pixel.
    player.seek_fraction(1.5)
    assert player.position_ms == 10_000
    player.seek_fraction(-0.5)
    assert player.position_ms == 0


def test_toggle_alterna_play_e_pause(qapp):
    player = SimulatedPlayer()
    player.load(Path("qualquer.wav"), duration_ms=10_000)

    player.toggle()
    assert player.is_playing is True
    player.toggle()
    assert player.is_playing is False


def test_stop_volta_para_o_inicio(qapp):
    player = SimulatedPlayer()
    player.load(Path("qualquer.wav"), duration_ms=10_000)
    player.seek(5_000)

    player.stop()

    assert player.position_ms == 0
    assert player.is_playing is False
