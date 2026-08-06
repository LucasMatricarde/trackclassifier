from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from trackclassifier.ui.widgets.player import (
    MULTIMEDIA_AVAILABLE,
    SimulatedPlayer,
    create_player,
)

#: O backend real so existe com o extra `audio` (PySide6-Addons). Sem ele
#: todo o resto do arquivo continua exercitando o SimulatedPlayer.
so_com_audio = pytest.mark.skipif(
    not MULTIMEDIA_AVAILABLE, reason="requer o extra audio (PySide6-Addons)"
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
