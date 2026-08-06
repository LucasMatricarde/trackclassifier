"""Buckets de energia por banda, para o render RGB da onda.

Graves no vermelho, medios no verde, agudos no azul -- a cor de cada coluna
E a energia das tres bandas, nao um gradiente aplicado sobre uma envoltoria.

Isto e dado de APRESENTACAO, nao de ML: nao entra em FEATURE_NAMES e nao
influencia o modelo. Se entrasse, acrescentar uma banda mudaria
`extractor.name` e re-analisaria a biblioteca inteira.

Nao importa Qt.
"""

from pathlib import Path

import librosa
import numpy as np

from .audio_io import ANALYSIS_SR, decode
from .ui.tokens import SIZE_WAVE_BUCKETS

#: Quantas colunas o render tem disponiveis. Vem do design system.
PEAKS_BUCKETS: int = int(SIZE_WAVE_BUCKETS)

_N_FFT = 2048
_HOP = 512
_EPS = 1e-9

#: Cortes das tres bandas, em Hz. Os mesmos limites que descriptors.py ja usa
#: para low_band_ratio/high_band_ratio -- manter os dois alinhados evita que a
#: onda mostre uma coisa e o modelo enxergue outra.
_CORTE_GRAVE = 250.0
_CORTE_AGUDO = 4000.0


def _resample_max(bandas: np.ndarray, buckets: int) -> np.ndarray:
    """Reduz (N, 3) para (buckets, 3) pegando o maximo de cada balde.

    Maximo e nao media de proposito: media achata transientes, e a onda perde
    justamente a informacao de ataque que o DJ procura. Mesma regra do
    _resample mono em waveform_render.py.
    """
    if buckets <= 0:
        return np.zeros((0, 3), dtype=np.float32)
    if len(bandas) == 0:
        return np.zeros((buckets, 3), dtype=np.float32)
    if len(bandas) <= buckets:
        # Track curta: repete a ultima coluna ate encher. Um segundo de audio
        # da ~44 frames de STFT contra 2000 buckets, entao este ramo e o caso
        # comum de qualquer coisa abaixo de ~45s, nao uma borda rara.
        return np.pad(
            bandas, ((0, buckets - len(bandas)), (0, 0)), mode="edge"
        ).astype(np.float32)

    bordas = np.linspace(0, len(bandas), buckets + 1, dtype=int)
    return np.stack(
        [bandas[bordas[i] : bordas[i + 1]].max(axis=0) for i in range(buckets)]
    ).astype(np.float32)


def compute_bands(path: Path, buckets: int = PEAKS_BUCKETS) -> np.ndarray:
    """Devolve (buckets, 3) float16 em [0, 1]: energia de grave, medio, agudo.

    float16 porque sao 2000x3 valores por track que so alimentam cores de 8
    bits -- float32 dobraria o disco sem mudar um pixel.

    Levanta AudioDecodeError se o arquivo nao decodifica. A contencao e de
    quem chama: o servico precisa distinguir "esta track nao tem onda" de
    "o scan inteiro falhou".
    """
    y = decode(Path(path), sample_rate=ANALYSIS_SR)

    espectro = np.abs(librosa.stft(y, n_fft=_N_FFT, hop_length=_HOP))
    frequencias = librosa.fft_frequencies(sr=ANALYSIS_SR, n_fft=_N_FFT)

    grave = espectro[frequencias < _CORTE_GRAVE].sum(axis=0)
    medio = espectro[
        (frequencias >= _CORTE_GRAVE) & (frequencias < _CORTE_AGUDO)
    ].sum(axis=0)
    agudo = espectro[frequencias >= _CORTE_AGUDO].sum(axis=0)

    bandas = _resample_max(np.stack([grave, medio, agudo], axis=1), buckets)

    # Normaliza pelo maximo GLOBAL das tres bandas, nao por banda: normalizar
    # cada canal em separado faria toda track parecer ter agudo forte, porque
    # o canal mais fraco seria esticado ate 1.0 e a cor perderia o sentido.
    # O epsilon segura o caso do silencio absoluto, onde o maximo e zero e a
    # divisao produziria NaN em toda a onda, sem erro nenhum.
    pico = float(bandas.max()) + _EPS
    return np.clip(bandas / pico, 0.0, 1.0).astype(np.float16)
