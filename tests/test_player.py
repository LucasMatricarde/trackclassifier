from pathlib import Path

from trackclassifier.ui.widgets.player import SimulatedPlayer, create_player


def test_create_player_devolve_um_backend(qapp):
    assert create_player() is not None


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
