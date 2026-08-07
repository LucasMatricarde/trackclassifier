---
name: trackclassifier-audio-features
description: Use ao mexer em audio_io.py, spectral.py, descriptors.py ou features.py do trackclassifier - decodificacao, STFT, HPSS, descritores por janela, vetor de features. Explica por que todo audio passa por subprocesso ffmpeg, por que a extracao e um passe unico com janela como fatia, por que o HPSS roda em 1025 bins lineares e nao no mel-128, e como comparar contra a referencia v1 (describe_window). Gatilhos: "adicionar descritor", "acelerar extracao", "librosa", "HPSS", "onset", "centroide", "mel", "decodificar audio".
---

# Audio e features do trackclassifier

## Todo audio passa por subprocesso ffmpeg

`audio_io.decode`, nao `librosa.load`. `librosa` so e usado sobre arrays ja
decodificados (`spectral.py`, `descriptors.py`). Toda chamada de subprocesso tem
timeout. `ffmpeg`/`ffprobe` precisam estar no PATH -- nao ha fallback
puro-Python; sem eles a maioria dos testes falha com `AudioDecodeError`.

## A extracao e um passe unico por track, e a janela e uma fatia

`spectral.compute_spectra` percorre a track UMA vez e devolve vetores por frame
(centroide, rolloff, fluxo, energia por banda, somas do HPSS, envoltoria de
onset); `descriptors.describe_slice` responde por uma janela indexando esses
vetores.

A v1 refazia STFT, HPSS e `onset_detect` DENTRO de cada janela, e com 50% de
sobreposicao cada amostra passava pelo HPSS duas vezes -- medido numa track de
188s, o HPSS era 94% do custo da janela para produzir um unico float. Medido
ponta a ponta: 9.2s -> 4.8s por track.

## HPSS em 1025 bins lineares e decisao medida

O HPSS roda nos **1025 bins lineares**, nao no mel-128, e isso e uma decisao
medida, nao um descuido: na biblioteca real (354 exemplos, leave-one-out),
mel-128 da 69.5% de acuracia contra 72.9% em resolucao cheia, com a v1 em 72.6%.
Reduzir para mel seria ~4x mais rapido e custaria 3 pontos -- a redundancia era
o problema, nao a resolucao.

## Como validar uma mudanca aqui

`descriptors.describe_window` sobrevive como referencia da v1: e com ela que se
compara descritor a descritor ao mexer aqui. 8 dos 10 devem bater com correlacao
`>= 0.9999`; `onset_rate` diverge de proposito, porque os onsets passaram a ser
detectados uma vez sobre a track inteira.

**Mudou o calculo de features? Bumpe `HandcraftedExtractor.name`** em
`features.py` -- o cache e chaveado por `(sha1, extractor.name)` e sem o bump
vetores velhos e novos se misturam em silencio (ver
`trackclassifier-arquitetura`).
