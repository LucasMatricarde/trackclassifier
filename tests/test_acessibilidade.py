"""Widget pintado a mao nao tem texto: o valor existe so como pixel.

Sem nome e descricao acessiveis, um leitor de tela anuncia a classe do
widget e nada mais. Um teste por widget, e nao uma varredura do pacote: a
heuristica "e QWidget, tem paintEvent, logo precisa de nome" da falso
positivo em todo container.
"""

from tests.test_viewmodel import _config, _servico
from trackclassifier.keys import Key, KeyNotation, Mode
from trackclassifier.ui.viewmodel import library_state
from trackclassifier.ui.widgets.class_balance import ClassBalance
from trackclassifier.ui.widgets.guess_bar import GuessBar
from trackclassifier.ui.widgets.key_chip import KeyChip
from trackclassifier.ui.widgets.metric_block import MetricBlock
from trackclassifier.ui.widgets.upcoming_list import UpcomingList
from trackclassifier.ui.widgets.waveform_view import WaveformView


def test_a_onda_grande_diz_de_que_track_ela_e(qapp, tmp_path):
    servico = _servico(_config(tmp_path))
    linha = library_state(servico).rows[0]
    onda = WaveformView()

    onda.set_row(linha)

    assert onda.accessibleName() == "Onda"
    assert linha.display_title in onda.accessibleDescription()


def test_a_onda_sem_track_nao_promete_track(qapp):
    onda = WaveformView()

    onda.set_row(None)

    assert onda.accessibleDescription() == "sem track"


def test_a_fila_diz_quantas_vem_a_seguir(qapp, tmp_path):
    servico = _servico(_config(tmp_path))
    lista = UpcomingList()

    lista.set_rows(library_state(servico).rows[:3])

    assert lista.accessibleName() == "Proximas da fila"
    assert "3" in lista.accessibleDescription()


def test_o_chip_diz_que_e_tonalidade(qapp):
    chip = KeyChip()

    chip.set_key(Key(11, Mode.MINOR))
    chip.set_notation(KeyNotation.CAMELOT)

    assert chip.accessibleName() == "Tonalidade"


def test_o_bloco_de_metrica_leva_o_proprio_rotulo(qapp):
    bloco = MetricBlock("BPM")

    bloco.set_value("138")

    assert bloco.accessibleName() == "BPM"
    assert bloco.accessibleDescription() == "138"


def test_cada_barra_do_balanco_diz_de_que_classe_e(qapp):
    balanco = ClassBalance()

    balanco.set_counts((5, 9, 2))

    nomes = [barra.accessibleName() for barra in balanco._barras]
    assert nomes == ["Balanco -1", "Balanco neutra", "Balanco +1"]


def test_o_medidor_do_palpite_diz_que_e_confianca(qapp):
    faixa = GuessBar()

    faixa.set_guess("+1", 0.82, low_confidence=False)

    assert faixa.medidor.accessibleName() == "Confianca do palpite"
