"""Tonalidade estimada pelo audio, para tracks sem tag TKEY.

A tag continua sendo a fonte preferida (Rekordbox e Mixed In Key ja gravam a
key na maioria dos acervos reais); isto so entra quando ela nao existe. Por
isso o resultado e marcado como "audio" em presentation.py e o front o exibe
com o aviso de que e uma estimativa.

Isto e dado de APRESENTACAO, nao de ML: nao entra em FEATURE_NAMES e nao muda
`extractor.name`. Fica fora de keys.py de proposito -- la e dominio puro, sem
librosa, e o viewmodel o importa.
"""

from pathlib import Path

import librosa
import numpy as np

from .audio_io import ANALYSIS_SR, decode
from .keys import Key, Mode

#: Perfis Krumhansl-Kessler (1982), indexados por grau a partir da tonica.
#: Sao a referencia classica para estimar tonalidade por correlacao do chroma;
#: nao foram recalibrados para musica eletronica.
_PERFIL_MAIOR = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_PERFIL_MENOR = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

#: Abaixo disto a melhor correlacao nao sustenta uma tonalidade. Sozinha NAO
#: separa ruido de musica: o chroma_cqt de ruido branco nao e plano (a CQT tem
#: vies por frequencia) e correlacionou ate 0.79 com algum perfil em 8 seeds
#: medidas, contra 0.91 (Am) e 0.85 (C) das triades sinteticas. Por isso existe
#: tambem _CONTRASTE_MINIMO.
#:
#: Medido no acervo real (`dj keys --calibrar`, 372 tracks com tag, 2026-10-26):
#: o acerto cresce com a correlacao -- [0.3,0.4) 41% exato, [0.4,0.5) 41%,
#: [0.5,0.6) 58%, [0.6,0.7) 59%, >=0.7 71%. Com 0.5 a estimativa cobre 45% das
#: tracks e acerta 61% exato / 72% vizinho (Camelot +-1 ou relativa); com 0.4
#: cobre 73% mas cai para 53% / 63%; sem limiar, 49% / 58%. Manteve-se 0.5: uma
#: key errada na hora de mixar custa mais que um "—". O teto e do metodo
#: (chroma medio da track inteira + perfis KK), nao do limiar: Temperley (34%
#: exato), Albrecht-Shanahan (41%) e Shaath/EDM (48%) ficaram abaixo do KK (49%).
LIMIAR_CORRELACAO = 0.5

#: Coeficiente de variacao (desvio / media) do chroma medio. Mede quao
#: "pontudo" ele e: ruido branco ficou em 0.016-0.026 nas mesmas 8 seeds e as
#: triades em ~1.6. No acervo real (372 tracks) a musica ficou entre 0.11 (p5)
#: e 0.36 (p95), mediana 0.21: so 7 tracks cairam abaixo de 0.1, que segue 4x
#: acima do maior ruido medido. O gargalo de cobertura e o LIMIAR_CORRELACAO,
#: nao este corte.
_CONTRASTE_MINIMO = 0.1

#: Energia media do chroma abaixo disto e silencio. Sem este corte, um arquivo
#: quase mudo (dithering, cauda de reverb) normaliza para um chroma plausivel
#: e devolve uma key inventada.
_ENERGIA_MINIMA = 1e-3


def _correlacao(chroma: np.ndarray, perfil: np.ndarray) -> np.ndarray:
    """Pearson do chroma com o perfil rotacionado para cada uma das 12 tonicas."""
    rotacoes = np.stack([np.roll(perfil, tonica) for tonica in range(12)])
    centrado = rotacoes - rotacoes.mean(axis=1, keepdims=True)
    alvo = chroma - chroma.mean()
    denominador = np.linalg.norm(centrado, axis=1) * np.linalg.norm(alvo)
    if denominador.min() == 0.0:
        # Chroma perfeitamente plano (desvio zero): correlacao indefinida.
        return np.zeros(12)
    return (centrado @ alvo) / denominador


def detect_key(path: Path) -> Key | None:
    """Estima a tonalidade pelo audio. None para silencio ou correlacao fraca.

    Levanta AudioDecodeError se o arquivo nao decodifica. A contencao e de
    quem chama: o servico precisa distinguir "esta track nao tem key" de
    "o arquivo nao abriu".
    """
    return detect_key_from_samples(decode(Path(path), sample_rate=ANALYSIS_SR))


def detect_key_from_samples(y: np.ndarray) -> Key | None:
    """Estima a tonalidade de um sinal mono em ANALYSIS_SR. None se nao houver.

    Separada de `detect_key` para o aquecimento do cache do numba (ver
    `service._aquece_cache_do_chroma`) acionar o chroma_cqt sem precisar de
    um arquivo em disco.
    """
    if y.size == 0:
        return None

    # chroma_cqt e robusto a harmonicos e a afinacao melhor que o chroma de
    # STFT, e o custo (alguns segundos por track) so e pago sob demanda.
    chroma = librosa.feature.chroma_cqt(y=y, sr=ANALYSIS_SR).mean(axis=1)
    if not np.all(np.isfinite(chroma)) or float(chroma.sum()) < _ENERGIA_MINIMA:
        return None
    if float(chroma.std() / chroma.mean()) < _CONTRASTE_MINIMO:
        # Chroma quase plano: energia espalhada nas 12 classes, sem tonica.
        return None

    maior = _correlacao(chroma, _PERFIL_MAIOR)
    menor = _correlacao(chroma, _PERFIL_MENOR)

    melhor_maior = int(np.argmax(maior))
    melhor_menor = int(np.argmax(menor))
    if maior[melhor_maior] >= menor[melhor_menor]:
        tonica, modo, correlacao = melhor_maior, Mode.MAJOR, float(maior[melhor_maior])
    else:
        tonica, modo, correlacao = melhor_menor, Mode.MINOR, float(menor[melhor_menor])

    if correlacao < LIMIAR_CORRELACAO:
        return None
    return Key(tonica, modo)
