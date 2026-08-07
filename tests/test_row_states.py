"""O estado da linha e derivado num lugar so, e nao em cada delegate."""

from trackclassifier.ui.viewmodel import TrackRow
from trackclassifier.ui.widgets.row_states import EstadoDaLinha, estado_da_linha


def _linha(**mudancas) -> TrackRow:
    base = dict(
        sha1="abc",
        filename="a.wav",
        label="+1",
        predicted=None,
        score=None,
        confidence=None,
        bpm=128.0,
        duration_s=300.0,
        energy_curve=(0.1, 0.2),
        peak_offset_s=1.0,
        path_hint="/tmp/a.wav",
    )
    return TrackRow(**{**base, **mudancas})


def test_linha_com_analise_e_normal():
    estado = estado_da_linha(_linha(), sha1_tocando=None, motivo_da_falha=None)

    assert estado is EstadoDaLinha.NORMAL


def test_sem_bpm_e_sem_curva_e_pendente():
    linha = _linha(bpm=0.0, energy_curve=())

    estado = estado_da_linha(linha, sha1_tocando=None, motivo_da_falha=None)

    assert estado is EstadoDaLinha.PENDENTE


def test_curva_sem_bpm_ainda_e_pendente():
    # bpm 0 e o valor que uma analise interrompida deixa; a curva sozinha
    # vem do render mono e nao prova que a extracao terminou.
    linha = _linha(bpm=0.0)

    assert estado_da_linha(linha, sha1_tocando=None, motivo_da_falha=None) is (
        EstadoDaLinha.PENDENTE
    )


def test_motivo_de_falha_vence_pendente():
    linha = _linha(bpm=0.0, energy_curve=())

    # Falhou e mais especifico que pendente: a track nao esta esperando
    # analise, ela ja tentou e nao deu. Mostrar "pendente" esconderia isso
    # e o usuario esperaria por algo que nao vem.
    estado = estado_da_linha(
        linha, sha1_tocando=None, motivo_da_falha="ffmpeg nao encontrado"
    )

    assert estado is EstadoDaLinha.FALHOU


def test_tocando_vence_normal():
    estado = estado_da_linha(_linha(), sha1_tocando="abc", motivo_da_falha=None)

    assert estado is EstadoDaLinha.TOCANDO


def test_tocando_de_outra_track_nao_afeta():
    estado = estado_da_linha(_linha(), sha1_tocando="outra", motivo_da_falha=None)

    assert estado is EstadoDaLinha.NORMAL


def test_tocando_nao_vence_falhou():
    # Nao da para tocar o que nao decodifica. Se os dois aparecerem juntos
    # e bug em outro lugar, e esconder a falha atrasaria a descoberta.
    linha = _linha(bpm=0.0, energy_curve=())

    estado = estado_da_linha(linha, sha1_tocando="abc", motivo_da_falha="x")

    assert estado is EstadoDaLinha.FALHOU
