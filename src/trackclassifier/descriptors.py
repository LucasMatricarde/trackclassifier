import librosa
import numpy as np

DESCRIPTOR_NAMES: list[str] = [
    "rms",
    "onset_rate",
    "spectral_flux",
    "spectral_centroid",
    "percussive_ratio",
    "low_band_ratio",
    "high_band_ratio",
    "spectral_rolloff",
    "spectral_bandwidth",
    "zero_crossing_rate",
]

_N_FFT = 2048
_HOP = 512
_EPS = 1e-9
_LOW_BAND = (20.0, 250.0)
_HIGH_BAND_FLOOR = 4000.0


def describe_window(y: np.ndarray, sr: int) -> dict[str, float]:
    y = np.asarray(y, dtype=np.float32)
    duracao = max(len(y) / sr, _EPS)

    espectro = np.abs(librosa.stft(y, n_fft=_N_FFT, hop_length=_HOP))
    frequencias = librosa.fft_frequencies(sr=sr, n_fft=_N_FFT)
    energia_total = float(espectro.sum()) + _EPS

    mascara_grave = (frequencias >= _LOW_BAND[0]) & (frequencias < _LOW_BAND[1])
    mascara_aguda = frequencias >= _HIGH_BAND_FLOOR

    if espectro.shape[1] > 1:
        fluxo = float(np.mean(np.maximum(np.diff(espectro, axis=1), 0.0)))
    else:
        fluxo = 0.0

    harmonico, percussivo = librosa.decompose.hpss(espectro)
    soma_percussiva = float(percussivo.sum())
    soma_harmonica = float(harmonico.sum())

    onsets = librosa.onset.onset_detect(y=y, sr=sr, hop_length=_HOP, units="time")

    return {
        "rms": float(np.sqrt(np.mean(np.square(y, dtype=np.float64)))),
        "onset_rate": float(len(onsets) / duracao),
        "spectral_flux": fluxo,
        "spectral_centroid": float(
            np.mean(librosa.feature.spectral_centroid(S=espectro, sr=sr))
        ),
        "percussive_ratio": float(
            soma_percussiva / (soma_percussiva + soma_harmonica + _EPS)
        ),
        "low_band_ratio": float(espectro[mascara_grave].sum() / energia_total),
        "high_band_ratio": float(espectro[mascara_aguda].sum() / energia_total),
        "spectral_rolloff": float(
            np.mean(librosa.feature.spectral_rolloff(S=espectro, sr=sr))
        ),
        "spectral_bandwidth": float(
            np.mean(librosa.feature.spectral_bandwidth(S=espectro, sr=sr))
        ),
        "zero_crossing_rate": float(
            np.mean(librosa.feature.zero_crossing_rate(y, hop_length=_HOP))
        ),
    }


def describe_slice(
    spectra: "TrackSpectra",  # noqa: F821 -- import tardio, ver nota abaixo
    f0: int,
    f1: int,
    a: int,
    b: int,
) -> dict[str, float]:
    """Os mesmos 10 descritores de describe_window, sem recomputar nada.

    `f0:f1` e o intervalo de frames da janela; `a:b`, o intervalo de amostras.
    Os dois existem porque `rms` e definido sobre as amostras cruas (e a
    energy_curve que a tela desenha sai dele), enquanto todo o resto e uma
    media ou soma sobre frames ja calculados em spectral.compute_spectra.

    Oito dos dez descritores sao numericamente identicos aos da v1 -- media de
    frames e media de frames, some-se antes ou depois. Os dois que mudam:

    - percussive_ratio: o HPSS agora roda em 128 bandas mel, nao em 1025 bins
      lineares. Desvio medido de ~0.03 numa razao que vive em [0,1].
    - onset_rate: os onsets sao detectados uma vez sobre a envoltoria da track
      inteira e contados por janela, em vez de um peak-picking independente
      dentro de cada janela. Mais estavel, mas nao o mesmo numero.

    Ambos alimentam um RidgeCV que e retreinado; o que importa e serem
    consistentes entre tracks, nao baterem com a v1. E o que o script de
    comparacao existe para verificar antes do commit.
    """
    y_janela = spectra.y[a:b]
    duracao = max(len(y_janela) / spectra.sr, _EPS)
    n_onsets = int(
        np.searchsorted(spectra.onset_frames, f1)
        - np.searchsorted(spectra.onset_frames, f0)
    )
    soma_p = float(spectra.percussive[f0:f1].sum())
    soma_h = float(spectra.harmonic[f0:f1].sum())
    # flux[f0] mede a transicao do frame ANTERIOR para f0, que e de fora da
    # janela. A v1 nao tinha esse frame disponivel (a STFT comecava na janela),
    # entao pular f0 mantem a definicao igual.
    fluxo = spectra.flux[f0 + 1 : f1]

    return {
        "rms": float(np.sqrt(np.mean(np.square(y_janela, dtype=np.float64))))
        if len(y_janela)
        else 0.0,
        "onset_rate": float(n_onsets / duracao),
        "spectral_flux": float(fluxo.mean()) if fluxo.size else 0.0,
        "spectral_centroid": float(spectra.centroid[f0:f1].mean()),
        "percussive_ratio": float(soma_p / (soma_p + soma_h + _EPS)),
        "low_band_ratio": float(
            spectra.low_energy[f0:f1].sum() / (spectra.total_energy[f0:f1].sum() + _EPS)
        ),
        "high_band_ratio": float(
            spectra.high_energy[f0:f1].sum() / (spectra.total_energy[f0:f1].sum() + _EPS)
        ),
        "spectral_rolloff": float(spectra.rolloff[f0:f1].mean()),
        "spectral_bandwidth": float(spectra.bandwidth[f0:f1].mean()),
        "zero_crossing_rate": float(spectra.zcr[f0:f1].mean()),
    }
