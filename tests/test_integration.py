"""Teste de integracao ponta a ponta cruzando a costura
extractor -> cache -> service -> model -> queue -> decide -> apply.

Todo teste existente ou usa HandcraftedExtractor isolado (test_features.py)
ou usa TrackService com um extrator falso (ExtratorFalso, em
test_service.py). Nenhum teste manda um vetor de 44 features REAL pela
pipeline completa: extract -> cache.put -> round-trip em parquet ->
cache.get -> model.fit -> predict -> queue -> decide -> move. E exatamente
nessa costura que bugs como o do cache ignorando a coluna "extractor" (ja
corrigido) ficam invisiveis para qualquer revisor que só veja um diff de
cada vez.
"""

import numpy as np
import soundfile as sf

from trackclassifier.audio_io import ANALYSIS_SR
from trackclassifier.features import HandcraftedExtractor
from trackclassifier.labels import Label
from trackclassifier.service import TrackService

from tests.test_service import _config


def _sinal(duracao_s: float, amplitude: float, seed: int) -> np.ndarray:
    """Ruido branco sintetico com amplitude controlada -- rapido de gerar,
    real o suficiente para o ffmpeg decodificar e o librosa/pyloudnorm
    extraírem 44 features finitas, sem depender do acervo real do usuario.
    """
    gerador = np.random.default_rng(seed)
    return (amplitude * gerador.standard_normal(int(ANALYSIS_SR * duracao_s))).astype(np.float32)


def _escreve_wav(caminho, sinal, sr=ANALYSIS_SR):
    sf.write(caminho, sinal, sr)
    return caminho


def test_pipeline_completo_com_extrator_real_ate_a_movimentacao_do_arquivo(tmp_path):
    config = _config(tmp_path)

    # Tracks curtas (15s, acima de MIN_TRACK_SECONDS=10s) para o teste
    # rodar em segundos, nao nos 5-15s por track que o design espera para
    # tracks de tamanho normal. Amplitudes bem separadas por classe para
    # que a Ridge tenha algum sinal para aprender, embora a acuracia em si
    # nao seja o que este teste verifica.
    amostras = {
        Label.DOWN: (0.02, [11, 12]),
        Label.NEUTRAL: (0.15, [21, 22]),
        Label.UP: (0.6, [31, 32]),
    }
    for rotulo, (amplitude, seeds) in amostras.items():
        for indice, seed in enumerate(seeds):
            caminho = config.folders[rotulo] / f"t{indice}.wav"
            _escreve_wav(caminho, _sinal(15.0, amplitude, seed))

    inbox_path = config.inbox / "nova.wav"
    _escreve_wav(inbox_path, _sinal(15.0, 0.5, 99))

    servico = TrackService(config, extractor=HandcraftedExtractor(), max_workers=1)

    servico.analyze_all()
    assert servico.failures() == []

    metricas = servico.train()
    assert metricas.n_examples == 6

    fila = servico.queue()
    assert len(fila) == 1
    item = fila[0]
    assert item.filename == "nova.wav"

    moveu_e_retreinou = servico.decide(item.sha1, item.label)

    # O arquivo saiu da inbox e pousou em exatamente uma das tres pastas
    # rotuladas -- nunca em duas, nunca em nenhuma.
    assert not inbox_path.exists()
    pastas_com_arquivo = [
        pasta for pasta in config.folders.values() if (pasta / "nova.wav").is_file()
    ]
    assert len(pastas_com_arquivo) == 1
    assert pastas_com_arquivo[0] == config.folders[item.label]

    # A fila esta vazia depois da decisao, e o retreino automatico (a cada
    # config.retrain_every=2 decisoes) e um bool valido.
    assert servico.queue() == []
    assert moveu_e_retreinou in (True, False)
