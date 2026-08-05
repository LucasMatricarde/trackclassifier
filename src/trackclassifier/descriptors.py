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
