"""Deteccao de tonalidade por audio. Sinais sinteticos com a key conhecida.

Uma triade de La menor (A-C-E) TEM que sair Key(9, minor), e uma de Do maior
(C-E-G) Key(0, major): sao a prova mais barata de que as rotacoes do perfil
estao alinhadas com o pitch class certo (0 = C) e de que maior/menor nao
estao trocados.
"""

import numpy as np
import pytest
import soundfile as sf

from trackclassifier.audio_io import AudioDecodeError
from trackclassifier.key_detect import detect_key
from trackclassifier.keys import Key, Mode

SR = 22050
DURACAO = 8.0

# Frequencias (Hz) da oitava central; harmonicos sao somados no helper.
_LA, _DO, _MI, _SOL = 220.0, 261.63, 329.63, 392.0


def _acorde(tmp_path, frequencias, nome="t.wav", duracao=DURACAO):
    t = np.linspace(0, duracao, int(SR * duracao), endpoint=False)
    sinal = np.zeros_like(t)
    for frequencia in frequencias:
        # Dois harmonicos: um seno puro funciona, mas o audio real sempre tem
        # parciais, e o chroma precisa continuar certo com eles.
        sinal += np.sin(2 * np.pi * frequencia * t)
        sinal += 0.4 * np.sin(2 * np.pi * 2 * frequencia * t)
    sinal = 0.3 * sinal / np.abs(sinal).max()
    caminho = tmp_path / nome
    sf.write(caminho, sinal.astype(np.float32), SR)
    return caminho


def test_triade_de_la_menor_vira_la_menor(tmp_path):
    caminho = _acorde(tmp_path, [_LA, _DO, _MI])

    assert detect_key(caminho) == Key(9, Mode.MINOR)


def test_triade_de_do_maior_vira_do_maior(tmp_path):
    caminho = _acorde(tmp_path, [_DO, _MI, _SOL])

    assert detect_key(caminho) == Key(0, Mode.MAJOR)


def test_silencio_devolve_none(tmp_path):
    # Silencio absoluto produz chroma zerado: a correlacao seria NaN, e uma
    # key "vencedora" sairia de ruido numerico. Tem que ser None.
    caminho = tmp_path / "mudo.wav"
    sf.write(caminho, np.zeros(int(SR * DURACAO), dtype=np.float32), SR)

    assert detect_key(caminho) is None


@pytest.mark.parametrize("seed", range(8))
def test_ruido_branco_devolve_none(tmp_path, seed):
    # Ruido espalha energia nas 12 classes. Varias seeds de proposito: so a
    # correlacao com os perfis chegou a 0.79 em ruido (o chroma_cqt tem vies
    # por frequencia), entao uma seed unica passaria por sorte mesmo com o
    # limiar errado. Exibir uma key aqui seria inventar confianca.
    rng = np.random.default_rng(seed)
    caminho = tmp_path / "ruido.wav"
    sf.write(caminho, (0.3 * rng.standard_normal(int(SR * DURACAO))).astype(np.float32), SR)

    assert detect_key(caminho) is None


def test_arquivo_ilegivel_levanta_audio_decode_error(tmp_path):
    # A contencao e de quem chama (service.ensure_key), como em compute_bands.
    caminho = tmp_path / "quebrado.wav"
    caminho.write_bytes(b"isto nao e audio")

    with pytest.raises(AudioDecodeError):
        detect_key(caminho)
