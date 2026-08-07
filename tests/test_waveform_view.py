"""A onda grande marca o pico -- dado que existia e nunca chegava a tela."""

from dataclasses import replace

from trackclassifier.ui.viewmodel import TrackRow
from trackclassifier.ui.widgets.waveform_view import WaveformView

LARGURA = 400
ALTURA = 96


def _linha(**mudancas) -> TrackRow:
    base = dict(
        sha1="abc",
        filename="a.wav",
        label=None,
        predicted="+1",
        score=0.8,
        confidence=0.8,
        bpm=128.0,
        duration_s=300.0,
        energy_curve=tuple(abs((i % 20) / 20 - 0.5) + 0.1 for i in range(200)),
        peak_offset_s=150.0,
        path_hint="/tmp/a.wav",
    )
    return TrackRow(**{**base, **mudancas})


def _pinta(linha: TrackRow | None, progresso: float = 0.0):
    vista = WaveformView()
    vista.resize(LARGURA, ALTURA)
    vista.set_row(linha)
    vista.set_progress(progresso)
    return vista.grab().toImage()


def test_marca_do_pico_muda_com_a_posicao(qapp):
    inicio = _pinta(_linha(peak_offset_s=10.0))
    meio = _pinta(_linha(peak_offset_s=150.0))

    assert inicio != meio


def test_pico_em_zero_nao_quebra(qapp):
    # Track cuja analise nao achou pico: o offset fica em 0.0 e a marca
    # cai na borda esquerda, sem sair do widget.
    assert _pinta(_linha(peak_offset_s=0.0)) is not None


def test_pico_maior_que_a_duracao_fica_dentro(qapp):
    # Cache antigo inconsistente. Sem o clamp, a linha seria desenhada
    # fora do widget e o rotulo sumiria sem nenhum aviso.
    fora = _pinta(_linha(peak_offset_s=9000.0))
    fim = _pinta(_linha(peak_offset_s=300.0))

    assert fora == fim


def test_pico_negativo_fica_dentro(qapp):
    negativo = _pinta(_linha(peak_offset_s=-30.0))
    inicio = _pinta(_linha(peak_offset_s=0.0))

    assert negativo == inicio


def test_duracao_zero_nao_divide_por_zero(qapp):
    assert _pinta(_linha(duration_s=0.0)) is not None


def test_playhead_move_com_o_progresso(qapp):
    parado = _pinta(_linha(), progresso=0.0)
    andando = _pinta(_linha(), progresso=0.5)

    assert parado != andando


def test_sem_linha_pinta_so_o_fundo(qapp):
    # Fila vazia: nao ha o que desenhar, mas a caixa continua reservada
    # para o layout nao pular quando a proxima track chega.
    assert _pinta(None) is not None


def test_sem_curva_e_sem_peaks_nao_quebra(qapp):
    assert _pinta(_linha(energy_curve=())) is not None


def test_widget_estreito_nao_quebra_a_grade(qapp):
    vista = WaveformView()
    vista.resize(1, ALTURA)
    vista.set_row(_linha())

    # Largura menor que um passo da grade: o range() nao pode gerar
    # nenhuma linha, e nao pode levantar.
    assert vista.grab().toImage() is not None
