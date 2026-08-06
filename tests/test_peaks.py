"""Buckets por banda. Sinais sinteticos com conteudo espectral conhecido.

Um seno de 80 Hz TEM que sair vermelho-dominante e um de 8 kHz azul-dominante
-- e o unico jeito de provar que as mascaras de frequencia estao nas bandas
certas, e nao trocadas entre si.
"""

import numpy as np
import pytest
import soundfile as sf

from trackclassifier.peaks import PEAKS_BUCKETS, compute_bands

SR = 22050
DURACAO = 12.0


def _tom(tmp_path, frequencias_e_amplitudes, nome="t.wav", duracao=DURACAO):
    t = np.linspace(0, duracao, int(SR * duracao), endpoint=False)
    sinal = np.zeros_like(t)
    for frequencia, amplitude in frequencias_e_amplitudes:
        sinal = sinal + amplitude * np.sin(2 * np.pi * frequencia * t)
    caminho = tmp_path / nome
    sf.write(caminho, sinal.astype(np.float32), SR)
    return caminho


def test_forma_e_tipo_do_resultado(tmp_path):
    caminho = _tom(tmp_path, [(440.0, 0.5)])

    bandas = compute_bands(caminho)

    assert bandas.shape == (PEAKS_BUCKETS, 3)
    assert bandas.dtype == np.float16


def test_valores_ficam_entre_zero_e_um(tmp_path):
    caminho = _tom(tmp_path, [(440.0, 0.9)])

    bandas = compute_bands(caminho)

    assert float(bandas.min()) >= 0.0
    assert float(bandas.max()) <= 1.0


def test_grave_domina_o_canal_vermelho(tmp_path):
    # 80 Hz forte + 8 kHz fraco. Se as mascaras estiverem trocadas, este
    # teste pega na hora.
    caminho = _tom(tmp_path, [(80.0, 0.8), (8000.0, 0.05)])

    medias = compute_bands(caminho).astype(np.float32).mean(axis=0)

    assert medias[0] > medias[1]
    assert medias[0] > medias[2]


def test_agudo_domina_o_canal_azul(tmp_path):
    caminho = _tom(tmp_path, [(8000.0, 0.8), (80.0, 0.05)])

    medias = compute_bands(caminho).astype(np.float32).mean(axis=0)

    assert medias[2] > medias[0]
    assert medias[2] > medias[1]


def test_track_curta_e_preenchida_ate_o_numero_de_buckets(tmp_path):
    # 1s de audio da ~44 frames de STFT, bem abaixo dos 2000 buckets. O
    # padding tem que completar sem quebrar a forma.
    caminho = _tom(tmp_path, [(440.0, 0.5)], duracao=1.0)

    bandas = compute_bands(caminho)

    assert bandas.shape == (PEAKS_BUCKETS, 3)


def test_numero_de_buckets_e_configuravel(tmp_path):
    caminho = _tom(tmp_path, [(440.0, 0.5)])

    bandas = compute_bands(caminho, buckets=64)

    assert bandas.shape == (64, 3)


def test_silencio_nao_gera_nan(tmp_path):
    # Divisao pelo maximo, que aqui e zero: sem o epsilon, tudo vira NaN e a
    # onda inteira some sem erro nenhum.
    caminho = tmp_path / "silencio.wav"
    sf.write(caminho, np.zeros(int(SR * DURACAO), dtype=np.float32), SR)

    bandas = compute_bands(caminho)

    assert np.isfinite(bandas.astype(np.float32)).all()
    assert float(bandas.max()) == 0.0


def test_arquivo_inexistente_propaga_audio_decode_error(tmp_path):
    # Contencao e responsabilidade de quem chama (service/worker), nao deste
    # modulo: aqui a falha precisa ser visivel.
    from trackclassifier.audio_io import AudioDecodeError

    with pytest.raises(AudioDecodeError):
        compute_bands(tmp_path / "nao_existe.wav")
