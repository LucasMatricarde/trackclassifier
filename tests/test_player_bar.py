"""A barra de transporte. Usa SimulatedPlayer -- sem dispositivo de audio."""

from trackclassifier.ui.widgets.player import SimulatedPlayer
from trackclassifier.ui.widgets.player_bar import PlayerBar


def test_tempo_comeca_zerado(qapp):
    barra = PlayerBar(SimulatedPlayer())

    assert barra.texto_do_tempo() == "0:00 / 0:00"


def test_tempo_acompanha_os_sinais_do_player(qapp):
    player = SimulatedPlayer()
    barra = PlayerBar(player)

    player.duration_changed.emit(185_000)
    player.position_changed.emit(65_000)

    assert barra.texto_do_tempo() == "1:05 / 3:05"


def test_botao_reflete_o_estado_do_player(qapp):
    """O Space em MainWindow chama player.toggle() sem passar por aqui --
    se o botao guardasse estado proprio, dessincronizaria na primeira vez
    que o usuario usasse o teclado."""
    player = SimulatedPlayer()
    barra = PlayerBar(player)
    inicial = barra.texto_do_botao()

    player.playing_changed.emit(True)

    assert barra.texto_do_botao() != inicial

    player.playing_changed.emit(False)

    assert barra.texto_do_botao() == inicial


def test_clique_no_play_chama_toggle(qapp):
    class _Espiao(SimulatedPlayer):
        def __init__(self):
            super().__init__()
            self.chamadas = 0

        def toggle(self):
            self.chamadas += 1

    player = _Espiao()
    barra = PlayerBar(player)

    barra.acionar_play()

    assert player.chamadas == 1
