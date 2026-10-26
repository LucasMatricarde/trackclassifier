---
name: trackclassifier-apresentacao
description: Use ao mexer em presentation.py, keys.py, peaks.py ou em metadado de exibicao (titulo, capa, tonalidade, thumbs). Gatilhos: "ler tag", "mutagen", "capa", "Camelot", "peaks", "thumbnail".
---

# Cache de apresentacao do trackclassifier

## Por que e separado do cache de ML

`presentation.parquet` e `covers/<sha1>.<ext>` guardam titulo, artista, album,
genero e capa embutida, lidos com `mutagen` durante o scan. Ele existe separado
do cache de ML por um motivo so: o de ML invalida tudo quando `extractor.name`
muda, entao acrescentar um campo de apresentacao la dispararia re-analise de
features da biblioteca inteira.

Aqui a versao e propria -- **bumpe `PRESENTATION_VERSION` quando mudar o que este
modulo produz**, e o custo e ~1ms por track, sem decodificar audio. A capa fica
em arquivo por track, nao em coluna de parquet, para o pandas nao carregar
centenas de MB de blob no boot do app.

## Tonalidade

Guardada em forma **canonica** (`key_pc` 0-11 mais `key_mode` "A"/"B"), nunca
como a string formatada. Gravar `"8A"` inviabilizaria o alternador
Camelot/classica, que so funciona porque `keys.Key` sobrevive ao round-trip do
parquet e e formatada na hora de exibir. `keys.py` e dominio puro -- sem mutagen,
sem librosa -- e por isso `viewmodel.py` pode importa-lo sem violar a fronteira
de tela.

A key vem **da tag** quando existe, lida no mesmo passe de apresentacao das outras
(~1ms, sem decodificar audio). Quando nao existe, `key_detect.detect_key` estima pelo
audio (`chroma_cqt` medio correlacionado com os perfis Krumhansl-Kessler nas 12
rotacoes) -- **sob demanda**, nunca no scan: o front pede
`POST /api/key/{sha1}/detect` para a track exibida na Revisao, e o resultado chega por
WebSocket (`key_ready` / `key_failed`). A decisao original era nao detectar (a estimativa
acerta ~60-70% em musica eletronica e key errada com a mesma confianca visual de uma
certa e pior que travessao); foi reaberta em 25/10/2026 e o historico esta em
`docs/superpowers/plans/2026-08-06-ui-desktop-fase-4.md`. A mitigacao e o `title`
"Tonalidade estimada pelo audio" no chip.

`PresentationRecord.key_source` diz de onde veio: `"tag"`, `"audio"`, `"none"` (a
deteccao foi tentada e nao achou) ou `None` (nunca tentada). **`None` e `"none"` sao
estados diferentes de proposito**: so o primeiro justifica pedir a deteccao, e
`service.ensure_key` nao retenta o segundo. `PresentationCache.set_key` grava preservando
tags e capa e **nao cria linha** para sha1 desconhecido (criaria tags vazias e o
`_preenche_apresentacao` nunca mais leria as de verdade). Falha de decode degrada para
`"none"` e nao entra em `failures()`. `detect_key` devolve `None` para silencio, chroma
plano ou correlacao fraca -- a correlacao sozinha NAO separa ruido de musica (ruido
branco chegou a 0.79), por isso `_CONTRASTE_MINIMO`; os dois limiares nao foram
calibrados contra o acervo real.

## Armadilhas do `mutagen`

- `mutagen.File(...)` devolve um objeto **falsy** para um arquivo sem tags, e
  `None` so quando nao reconhece o formato. Teste sempre com `is None` --
  `if arquivo:` descarta em silencio toda track sem metadado.
- A key mora em tres lugares incompativeis: vorbis comment (`initialkey`/`key`)
  no FLAC/OGG, frame `TKEY` no ID3 (mp3/aiff/wav), e o atom
  `----:com.apple.iTunes:initialkey` no MP4. E `MP4FreeForm` e **subclasse de
  bytes**, igual ao `MP4Cover`: precisa de `.decode()`, nao de `.text`. O caminho
  `easy=True` nao serve aqui -- ele nao expoe `TKEY` em mp3.

## Buckets de onda (`peaks/<sha1>.npy`)

`peaks.py` + `presentation.PeaksStore`: `(2000, 3)` float16 em `[0,1]`,
graves/medios/agudos, que alimentam a onda RGB. **Nao sao computados durante o
scan** -- a STFT da track inteira custa alguns segundos e dobraria o tempo de um
scan grande para dado que talvez nunca apareca na tela. Sao preguicosos: o front
pede os da track atual (Revisao) ou das linhas no viewport (Biblioteca) por
`POST /api/peaks/{sha1}/compute`, e o `serve.py` limita a 3 computos em voo
(`_peaks_semaphore`) para uma rolagem nao entupir o servidor. O contrato
`PEAKS_BUCKETS`/dtype/shape e lido a mao pelo `WaveformCanvas.tsx`
(`tests/test_peaks.py` confere o valor contra o JSON e o `tokens.css`). Enquanto nao existem, a onda cai no
render mono derivado de `energy_curve` -- **por isso `energy_curve` nao pode sair
de `TrackAnalysis` nem de `TrackRow`**, mesmo agora que o RGB existe.

Um `.npy` nao carrega a versao dentro dele, entao **bumpar `PRESENTATION_VERSION`
nao invalida os buckets sozinho**: apague `peaks/` a mao quando mudar o formato
ou o calculo em `peaks.py`.

## Thumb da capa

`covers/<sha1>.thumb.png` (96px) e PRE-EXISTENTE no acervo: foi gerado por
versoes antigas do app e nenhuma versao atual o gera. O `/api/thumb` serve o que
houver e cai na capa original (o caso comum num acervo novo). O thumb NAO tem
versao dentro dele, igual ao `.npy`: e `PresentationCache.put()` quem apaga o thumb obsoleto ao gravar uma capa nova,
porque nada mais o faria sozinho. `THUMB_SUFFIX` mora em `presentation.py`: quem
apaga e o dominio, e o sufixo composto (`.thumb.png`, nao `.png`) e o que impede
colidir com uma capa que ja seja PNG.
