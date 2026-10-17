---
name: trackclassifier-apresentacao
description: Use ao mexer em presentation.py, keys.py, peaks.py ou em qualquer metadado de exibicao do trackclassifier - titulo, artista, album, genero, capa, tonalidade, buckets de onda, thumbs. Explica por que o cache de apresentacao e separado do de ML, quando bumpar PRESENTATION_VERSION, a forma canonica da key, as armadilhas do mutagen (objeto falsy, TKEY, MP4FreeForm) e como peaks/ e o thumb sao invalidados a mao. Gatilhos: "ler tag", "mutagen", "capa", "cover art", "Camelot", "key", "waveform", "peaks", "thumbnail".
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
centenas de MB de blob no boot da janela.

## Tonalidade

Guardada em forma **canonica** (`key_pc` 0-11 mais `key_mode` "A"/"B"), nunca
como a string formatada. Gravar `"8A"` inviabilizaria o alternador
Camelot/classica, que so funciona porque `keys.Key` sobrevive ao round-trip do
parquet e e formatada na hora de exibir. `keys.py` e dominio puro -- sem Qt, sem
mutagen, sem librosa -- e por isso `ui/viewmodel.py` pode importa-lo sem violar a
fronteira de tela.

A key vem **da tag**, lida no mesmo passe de apresentacao das outras (~1ms, sem
decodificar audio). Nao ha deteccao por audio: Rekordbox e Mixed In Key ja gravam
a key na maioria dos acervos reais, e uma estimativa propria por chroma acerta
~60-70% em musica eletronica -- key errada exibida com a mesma confianca de uma
certa e pior que travessao para quem mixa harmonicamente.

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
scan grande para dado que talvez nunca apareca na tela. Sao preguicosos: a aba
Revisao pede os da track atual, e a aba Biblioteca pede os das linhas que estao
no viewport (ver `trackclassifier-ui`). Enquanto nao existem, a onda cai no
render mono derivado de `energy_curve` -- **por isso `energy_curve` nao pode sair
de `TrackAnalysis` nem de `TrackRow`**, mesmo agora que o RGB existe.

Um `.npy` nao carrega a versao dentro dele, entao **bumpar `PRESENTATION_VERSION`
nao invalida os buckets sozinho**: apague `peaks/` a mao quando mudar o formato
ou o calculo em `peaks.py`.

## Thumb da capa

`covers/<sha1>.thumb.png` (96px) e gerado por `ui/widgets/thumbs.py` na primeira
pintura da linha. O thumb NAO tem versao dentro dele, igual ao `.npy`: e
`PresentationCache.put()` quem apaga o thumb obsoleto ao gravar uma capa nova,
porque nada mais o faria sozinho. `THUMB_SUFFIX` mora em `presentation.py`, nao
em `thumbs.py` -- quem apaga e o dominio, e o sufixo composto (`.thumb.png`, nao
`.png`) e o que impede colidir com uma capa que ja seja PNG. O porque da geracao
morar em `ui/` esta em `trackclassifier-ui`.
