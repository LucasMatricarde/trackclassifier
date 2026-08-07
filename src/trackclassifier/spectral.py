"""Passe unico sobre a track: um decode, um espectrograma, todos os agregados.

A v1 recomputava STFT, HPSS e deteccao de onset dentro de cada janela, com
50% de overlap -- ou seja, cada amostra do audio passava por tudo duas vezes,
e o HPSS sozinho respondia por ~92% do tempo de scan.

Aqui a track e percorrida UMA vez e o que sai sao vetores por frame. A janela
deixa de ser um recomputo e vira um intervalo de indices: `centroid[f0:f1]`,
`low_energy[f0:f1].sum()`. E a mesma inversao que Mixxx e Essentia fazem --
o decode e o espectro sao o recurso caro, e todo analisador le do mesmo.

Nao importa Qt e nao toca disco: e chamado de dentro dos workers do pool.
"""

from dataclasses import dataclass

import librosa
import numpy as np

N_FFT = 2048
HOP = 512

#: Bandas mel usadas SO para a envoltoria de onset (onset_strength espera um
#: espectrograma log-potencia perceptual). O HPSS NAO usa isto -- ver a nota
#: em compute_spectra sobre a medicao de acuracia.
N_MELS = 128

#: Frames processados por vez no laco de agregacao. O espectro inteiro de uma
#: track de 6 min ja ocupa ~64 MB; materializar `S**2` ou `np.diff(S)` de uma
#: vez dobraria ou triplicaria isso DENTRO de cada worker, multiplicado pelo
#: numero de workers. Em blocos, o pico extra fica em ~16 MB fixos.
_CHUNK_FRAMES = 4096

_EPS = 1e-9
_LOW_BAND = (20.0, 250.0)
_HIGH_BAND_FLOOR = 4000.0


@dataclass(frozen=True)
class TrackSpectra:
    """Tudo que a track produz por frame. Janela = fatia destes vetores."""

    sr: int
    y: np.ndarray
    #: (bins, frames), magnitude. Mantido porque `rms` e as razoes de banda
    #: precisam da resolucao linear cheia, igual a v1.
    S: np.ndarray
    centroid: np.ndarray
    rolloff: np.ndarray
    bandwidth: np.ndarray
    zcr: np.ndarray
    #: Media (sobre os bins) do diff positivo em relacao ao frame anterior.
    #: flux[0] e 0 por definicao -- nao ha frame anterior.
    flux: np.ndarray
    low_energy: np.ndarray
    high_energy: np.ndarray
    total_energy: np.ndarray
    #: Somas por frame das componentes percussiva e harmonica no dominio mel.
    percussive: np.ndarray
    harmonic: np.ndarray
    #: Indices de frame onde houve onset, ordenados. Detectados uma vez sobre
    #: a envoltoria global, nao janela a janela.
    onset_frames: np.ndarray
    onset_env: np.ndarray

    @property
    def n_frames(self) -> int:
        return int(self.S.shape[1])

    def frame_bounds(self, inicio_amostra: int, fim_amostra: int) -> tuple[int, int]:
        """Converte um intervalo de amostras no intervalo de frames coberto.

        Sempre devolve pelo menos um frame: uma janela mais curta que o hop
        existe (tracks de ~10s com janela de 3.3s ainda tem varios frames, mas
        o guarda evita fatia vazia em qualquer borda) e uma fatia vazia
        propagaria NaN pelo vetor de features inteiro.
        """
        f0 = max(0, inicio_amostra // HOP)
        f1 = min(self.n_frames, max(f0 + 1, fim_amostra // HOP))
        return f0, f1


def compute_spectra(y: np.ndarray, sr: int) -> TrackSpectra:
    y = np.asarray(y, dtype=np.float32)
    S = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP))
    frequencias = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    mascara_grave = (frequencias >= _LOW_BAND[0]) & (frequencias < _LOW_BAND[1])
    mascara_aguda = frequencias >= _HIGH_BAND_FLOOR

    n = S.shape[1]
    filtros_mel = librosa.filters.mel(sr=sr, n_fft=N_FFT, n_mels=N_MELS)
    mel_pot = np.empty((N_MELS, n), dtype=np.float32)
    fluxo = np.zeros(n, dtype=np.float32)
    energia_grave = np.empty(n, dtype=np.float32)
    energia_aguda = np.empty(n, dtype=np.float32)
    energia_total = np.empty(n, dtype=np.float32)

    for a in range(0, n, _CHUNK_FRAMES):
        b = min(a + _CHUNK_FRAMES, n)
        bloco = S[:, a:b]
        mel_pot[:, a:b] = filtros_mel @ np.square(bloco)
        energia_grave[a:b] = bloco[mascara_grave].sum(axis=0)
        energia_aguda[a:b] = bloco[mascara_aguda].sum(axis=0)
        energia_total[a:b] = bloco.sum(axis=0)
        # O diff precisa do frame anterior ao bloco; por isso o inicio recua 1
        # quando existe, e o resultado e escrito a partir de max(a, 1).
        inicio_diff = max(a - 1, 0)
        janela = S[:, inicio_diff:b]
        if janela.shape[1] > 1:
            positivo = np.maximum(np.diff(janela, axis=1), 0.0)
            fluxo[max(a, 1) : b] = positivo.mean(axis=0)[-(b - max(a, 1)) :]

    # HPSS uma unica vez, nos 1025 bins LINEARES -- nao no mel.
    #
    # Rodar no mel-128 seria ~4x mais rapido, mas foi medido na biblioteca
    # real (354 exemplos rotulados, leave-one-out): mel-128 da 69.5% de
    # acuracia contra 72.9% em resolucao cheia, com a v1 em 72.6%. Ou seja, o
    # passe unico em resolucao cheia empata com a v1 pela metade do tempo,
    # enquanto a reducao para mel custa 3 pontos. A redundancia era o
    # problema, nao a resolucao.
    #
    # So as SOMAS por frame sobrevivem -- percussive_ratio e uma razao, nao
    # precisa das matrizes separadas, e descarta-las devolve ~65 MB por
    # worker antes do proximo passo.
    harmonico_bins, percussivo_bins = librosa.decompose.hpss(S)
    percussivo = percussivo_bins.sum(axis=0).astype(np.float32)
    harmonico = harmonico_bins.sum(axis=0).astype(np.float32)
    del harmonico_bins, percussivo_bins

    envoltoria = librosa.onset.onset_strength(
        S=librosa.power_to_db(mel_pot), sr=sr, hop_length=HOP
    )
    onsets = librosa.onset.onset_detect(
        onset_envelope=envoltoria, sr=sr, hop_length=HOP, units="frames"
    )
    del mel_pot

    return TrackSpectra(
        sr=sr,
        y=y,
        S=S,
        centroid=librosa.feature.spectral_centroid(S=S, sr=sr)[0],
        rolloff=librosa.feature.spectral_rolloff(S=S, sr=sr)[0],
        bandwidth=librosa.feature.spectral_bandwidth(S=S, sr=sr)[0],
        zcr=librosa.feature.zero_crossing_rate(y, frame_length=N_FFT, hop_length=HOP)[0],
        flux=fluxo,
        low_energy=energia_grave,
        high_energy=energia_aguda,
        total_energy=energia_total,
        percussive=percussivo,
        harmonic=harmonico,
        onset_frames=np.asarray(onsets, dtype=np.int64),
        onset_env=envoltoria,
    )


def track_bpm(spectra: TrackSpectra) -> float:
    """BPM reaproveitando a envoltoria de onset ja calculada.

    `beat_track(y=...)` refaz melspectrograma e envoltoria do zero -- 11.9s
    contra 2.6s na medicao, para chegar no mesmo lugar.
    """
    tempo = librosa.beat.beat_track(
        onset_envelope=spectra.onset_env, sr=spectra.sr, hop_length=HOP
    )[0]
    return float(np.atleast_1d(tempo)[0])


def band_ratio(parcial: np.ndarray, total: np.ndarray) -> float:
    return float(parcial.sum() / (total.sum() + _EPS))
