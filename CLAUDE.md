# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Comandos

```bash
uv sync --extra dev            # instala deps (roda antes de qualquer coisa)
uv run pytest                  # suite completa (~70s, usa ffmpeg de verdade)
uv run pytest tests/test_service.py::test_treina_e_reporta_metricas   # um teste
uv run pytest -k paralelo      # por substring do nome
uv run ruff check .            # lint (gate do CI)
uv run ruff check --fix .
```

`ffmpeg` e `ffprobe` precisam estar no PATH (`brew install ffmpeg`) — nao ha
fallback puro-Python. Sem eles a maioria dos testes falha com `AudioDecodeError`.

CLI (precisa de `config.toml`, copiado de `config.example.toml`, gitignored):

```bash
uv run dj scan     # extrai features das tracks ainda nao analisadas
uv run dj train    # retreina e imprime metricas
uv run dj review   # abre a janela de revisao PySide6
uv run python design/build_tokens.py   # regenera ui/tokens.py e ui/app.qss
```

Python `>=3.11,<3.14`. CI (`.github/workflows/ci.yml`) roda ruff + pytest em
push/PR para `main`.

## Executavel do macOS

```bash
uv sync --extra dev --extra build
uv run pyinstaller packaging/trackclassifier.spec --noconfirm   # gera dist/TrackClassifier.app
```

Nao ha workflow de release: runner macOS hospedado no GitHub conta minuto a
10x, e um build (~15min) estoura a cota gratis rapido. O build e sempre
local, rodado a mao quando quiser uma versao nova.

Quatro coisas so quebram no app empacotado, nunca em `uv run dj` — e todas
ja mordram uma vez:

- **`multiprocessing.freeze_support()` em `packaging/entry_point.py`.** O pool
  do scan cria workers relancando o proprio executavel; sem a chamada, cada
  worker cai no argparse com os argumentos internos do multiprocessing e o
  pool inteiro morre.
- **`ffmpeg`/`ffprobe` vao dentro do bundle** (via `binaries` no spec, que faz
  o PyInstaller reescrever os install_name das dylibs do homebrew).
  App aberto pelo Finder nao herda o PATH do shell: sem eles embutidos,
  `/opt/homebrew/bin` fica invisivel e toda track falha.
  `audio_io._ffmpeg_embutido` prefere o do bundle e cai no PATH fora dele.
- **Config nao pode ser relativo ao cwd.** Empacotado (`sys.frozen`), o
  default vira `~/.trackclassifier/config.toml`. Quando ele nao existe -- ou
  existe apontando para uma pasta que sumiu -- a janela abre o
  `FirstRunDialog` (`ui/first_run.py`), que grava o arquivo pela primeira
  vez. Nao ha mais copia do `config.example.toml` para o home: ela
  transformava "nao tem config" em "config apontando para
  /Users/SEU_USUARIO", escondendo do app a unica condicao que dispara o
  dialogo. `dj scan` e `dj train` seguem headless, com `ConfigError` no
  stderr e sem importar Qt.
- **Teste o bundle com `env -i ... PATH=/usr/bin:/bin:/usr/sbin:/sbin`**
  depois de qualquer mudanca no spec ou em `audio_io.py`/`cli.py`: e o que
  reproduz o PATH minimo que o Finder da, e e onde a classe de bug acima
  aparece. Rodar com o PATH normal do shell mascara justamente isso.

## Arquitetura

Pipeline de um comando `dj`: `library` varre as pastas → `cache` decide o que ja
foi analisado → `extraction` roda em `ProcessPoolExecutor` → `cache` persiste em
parquet → `model` treina/prediz → `service.queue()` ordena por confianca → `ui`
serve a revisao numa janela PySide6 → `apply` move o arquivo → retreino
automatico.

**Identidade e invalidacao de cache.** Uma track e identificada pelo SHA-1 do
conteudo (`cache.file_sha1`), nunca pelo caminho — renomear ou mover nao
reprocessa. O cache e chaveado por `(sha1, extractor.name)`: **mudou o calculo de
features, bumpe `HandcraftedExtractor.name`** (`"handcrafted-v2"` em
`features.py`). Sem o bump, vetores velhos e novos se misturam silenciosamente.

**O modelo e regressao ordinal, nao classificacao.** `LABEL_TARGET` mapeia
`-1/neutra/+1` para `0.0/0.5/1.0`; `RidgeCV` prediz um escore continuo em
`[0,1]`; dois limiares (`thresholds_`) fatiam o escore de volta em rotulos. Os
limiares sao calibrados por busca exaustiva sobre predicoes leave-one-out — e a
mesma passada LOO que produz `Metrics`, entao acuracia relatada e fora de
amostra. Confianca = distancia ao limiar mais proximo, cortada pela metade
enquanto `low_confidence_mode` (menos de `min_examples` exemplos).

**Todo audio passa por subprocesso ffmpeg** (`audio_io.decode`), nao por
`librosa.load`. `librosa` so e usado sobre arrays ja decodificados
(`spectral.py`, `descriptors.py`). Toda chamada de subprocesso tem timeout.

**A extracao e um passe unico por track, e a janela e uma fatia.**
`spectral.compute_spectra` percorre a track UMA vez e devolve vetores por
frame (centroide, rolloff, fluxo, energia por banda, somas do HPSS,
envoltoria de onset); `descriptors.describe_slice` responde por uma janela
indexando esses vetores. A v1 refazia STFT, HPSS e `onset_detect` DENTRO de
cada janela, e com 50% de sobreposicao cada amostra passava pelo HPSS duas
vezes -- medido numa track de 188s, o HPSS era 94% do custo da janela para
produzir um unico float. Medido ponta a ponta: 9.2s -> 4.8s por track.

O HPSS roda nos **1025 bins lineares**, nao no mel-128, e isso e uma decisao
medida, nao um descuido: na biblioteca real (354 exemplos, leave-one-out),
mel-128 da 69.5% de acuracia contra 72.9% em resolucao cheia, com a v1 em
72.6%. Reduzir para mel seria ~4x mais rapido e custaria 3 pontos -- a
redundancia era o problema, nao a resolucao. `descriptors.describe_window`
sobrevive como referencia da v1: e com ela que se compara descritor a
descritor ao mexer aqui (8 dos 10 devem bater com correlacao >= 0.9999;
`onset_rate` diverge de proposito, porque os onsets passaram a ser
detectados uma vez sobre a track inteira).

**Os erros sao contidos por design, em cada camada.** Parquet corrompido → cache
vazio; `model.joblib` ilegivel (drift de versao do pickle) → modelo novo; worker
morto ou pool que nem construiu → `FailedItem` para os pendentes, scan segue;
extracao que falha → `extract_one` devolve `(None, mensagem)`. O padrao e sempre
degradar e reportar em `service.failures()`, nunca derrubar o comando. Preserve
isso ao mexer nessas bordas — os comentarios longos no codigo explicam qual
excecao especifica cada bloco cobre.

**Concorrencia tem duas formas distintas.** O scan usa processos
(`ProcessPoolExecutor`, workers limitados a 8 por causa do pico de memoria de
ffmpeg+librosa por worker). Ja a UI usa uma QThread unica
dona do `TrackService` (`ui/worker.py`): a janela manda pedidos por slot e
recebe sinais, entao nao ha lock nem parquet escrito de dois lugares.
`apply._destino_livre` segue reservando o nome de destino atomicamente com
`os.open(O_CREAT|O_EXCL)` — o desfazer e o scan podem disputar a mesma pasta.

**Workers empacotados morrem com SIGSEGV dentro do numpy, e a causa raiz nao
esta resolvida.** No `.app` (nunca em `uv run`), um worker do scan morre com
`EXC_BAD_ACCESS` no endereco 0, em `generic_wrapped_legacy_loop`
(`PyUFunc_GeneralizedFunctionInternal`) — bug de dentro do numpy, na familia
do numpy#27709. **Nao e OOM**: a maquina tem 24 GB com 65% livre, e o
`Termination Reason` e `SIGNAL, code 11`, nao jetsam. O que foi medido:

- correlaciona com **concorrencia** — pool de 8 morre; pool de 1 nunca morreu
  em nenhuma execucao;
- e **intermitente** — o mesmo bundle rodou a biblioteca inteira limpo tres
  vezes e falhou logo nas primeiras tracks em outras duas;
- **nao** e uma track especifica, nem o bundle em si, nem escala.

`service._fixa_threads_dos_workers` poe `VECLIB_MAXIMUM_THREADS=1` e companhia
no `os.environ` do PAI antes de criar o pool (unico canal que o Accelerate
respeita; com spawn o filho herda antes de importar numpy — um `initializer=`
rodaria tarde demais). Isso corrige uma intencao que estava quebrada:
`threadpool_limits(limits=1)` em `extract_one` funciona no Linux (OpenBLAS)
mas e no-op no macOS, onde o BLAS e o Accelerate e `threadpool_info()` devolve
lista vazia. Medido: 16 threads por worker sem o pinning, 2 com. **Mas isso
NAO evita o segfault** — ele foi reproduzido com 2 threads e a mesma stack.
O pinning fica porque a intencao original era essa; nao porque cura.

`TRACKCLASSIFIER_MAX_WORKERS` sobrescreve o teto, para investigar isso sem
pagar ~15 min de rebuild por tentativa.

**Um worker morto nao custa mais o lote.** `ProcessPoolExecutor` nao isola a
morte de um filho: o executor inteiro quebra e todo future pendente levanta
`BrokenProcessPool`, mesmo os que nem comecaram — um unico segfault virava
~370 falhas identicas (6 tracks analisadas de 377). Por isso `_analyze` manda
o lote em **blocos** de `max_workers * 4`, cada um no proprio pool: a morte so
alcanca o bloco em voo. O que sobra do bloco e reprocessado **item a item, num
pool de 1 worker** — onde o segfault custa exatamente a track que o causou.
A retentativa usa pool, e nao `extract_one` direto, porque nesta thread um
segfault levaria a janela junto. Medido, para nao reinventar os desenhos
descartados: retentar o lote inteiro num pool novo repete a cascata; mandar
tudo item a item custa ~140 min contra ~10 min do pool cheio.

`_analyze` reordena o resultado pela ordem original de entrada — `as_completed`
devolve fora de ordem e a estabilidade entre execucoes e garantida.

**O cancelamento do scan atravessa as threads fora do Qt, de proposito.**
`analyze_all(should_cancel=...)` consulta o flag entre extracoes, e
`ServiceWorker.request_cancel()` e um metodo **normal, nao um `@Slot`**: durante
um scan o loop de eventos da thread do worker esta parado dentro de
`analyze_all`, entao um slot enfileirado so rodaria depois do scan acabar — o
oposto do que se quer. Um `threading.Event` e o unico estado compartilhado entre
as duas threads. Cancelar nao e falhar: o que nao foi extraido continua pendente
para o proximo scan e **nao** entra em `failures()`. O teto de latencia e uma
extracao em voo (`shutdown(cancel_futures=True)` descarta so o que nao comecou),
porque matar um worker no meio de ffmpeg/librosa nao e opcao.

**Estado em disco** fica em `data_dir` (default `.trackclassifier/`, gitignored):
`analyses.parquet` (escrita atomica via `os.replace`, salvo a cada 10 extracoes),
`model.joblib`, `sha1.json` (`library.Sha1Cache` — evita reler o arquivo inteiro
a cada scan quando `(mtime, size)` nao mudou). A chave do `Sha1Cache` e o
caminho, e toda decisao move o arquivo de pasta: por isso `decide`, `reclassify`
e `undo_last` chamam `sha1_cache.rename(origem, destino)`. **Se voce criar outro
caminho que mova um arquivo, chame `rename` tambem** — sem isso a track vira
cache-miss garantido no scan seguinte, relendo o arquivo inteiro por nada. A
poda em `save()` e so a rede para o que foi movido por fora.

`presentation.parquet` e `covers/<sha1>.<ext>` sao o cache de **apresentacao**
(`presentation.py`): titulo, artista, album, genero e capa embutida, lidos com
`mutagen` durante o scan. Ele existe separado do cache de ML por um motivo so:
o de ML invalida tudo quando `extractor.name` muda, entao acrescentar um campo
de apresentacao la dispararia re-analise de features da biblioteca inteira.
Aqui a versao e propria — **bumpe `PRESENTATION_VERSION` quando mudar o que
este modulo produz**, e o custo e ~1ms por track, sem decodificar audio. A capa
fica em arquivo por track, nao em coluna de parquet, para o pandas nao carregar
centenas de MB de blob no boot da janela.

A tonalidade e guardada em forma **canonica** (`key_pc` 0-11 mais `key_mode`
"A"/"B"), nunca como a string formatada. Gravar `"8A"` inviabilizaria o
alternador Camelot/classica, que so funciona porque `keys.Key` sobrevive ao
round-trip do parquet e e formatada na hora de exibir. `keys.py` e dominio
puro -- sem Qt, sem mutagen, sem librosa -- e por isso `ui/viewmodel.py` pode
importa-lo sem violar a fronteira de tela.

A key vem **da tag**, lida no mesmo passe de apresentacao das outras (~1ms,
sem decodificar audio). Nao ha deteccao por audio: Rekordbox e Mixed In Key
ja gravam a key na maioria dos acervos reais, e uma estimativa propria por
chroma acerta ~60-70% em musica eletronica -- key errada exibida com a mesma
confianca de uma certa e pior que travessao para quem mixa harmonicamente.

Armadilha do `mutagen`, segunda parte: a key mora em tres lugares
incompativeis -- vorbis comment (`initialkey`/`key`) no FLAC/OGG, frame
`TKEY` no ID3 (mp3/aiff/wav), e o atom `----:com.apple.iTunes:initialkey` no
MP4. E `MP4FreeForm` e **subclasse de bytes**, igual ao `MP4Cover`: precisa
de `.decode()`, nao de `.text`. O caminho `easy=True` nao serve aqui -- ele
nao expoe `TKEY` em mp3.

`peaks/<sha1>.npy` guarda os buckets de energia por banda (`peaks.py`,
`presentation.PeaksStore`): `(2000, 3)` float16 em `[0,1]`, graves/medios/agudos,
que alimentam a onda RGB. **Nao sao computados durante o scan** — a STFT da
track inteira custa alguns segundos e dobraria o tempo de um scan grande para
dado que talvez nunca apareca na tela. Sao preguicosos: a aba Revisao pede os
da track atual, e a aba Biblioteca pede os das linhas que estao no viewport.
Enquanto nao existem, a onda cai no render mono derivado de `energy_curve` —
**por isso `energy_curve` nao pode sair de `TrackAnalysis` nem de
`TrackRow`**, mesmo agora que o RGB existe.

Um `.npy` nao carrega a versao dentro dele, entao **bumpar
`PRESENTATION_VERSION` nao invalida os buckets sozinho**: apague `peaks/` a mao
quando mudar o formato ou o calculo em `peaks.py`.

**Quem pede o computo de uma onda e a aba, olhando o viewport — nunca o
delegate.** `WaveformDelegate.paint()` so desenha; ele nao tem sinal
`peaks_requested` nenhum. A versao anterior emitia dali, com dedup por sha1 —
parecia suficiente e nao era: `paint()` nao sabe o que mais esta na tela, so a
celula que esta pintando naquele instante. Rolar a biblioteca real (354
tracks, a maioria sem buckets ainda) pintava ~300 linhas sem onda colorida uma
vez cada e enfileirava ~300 computos de `ensure_peaks` (~0,4 s cada) na MESMA
thread que atende `decide`/`undo`/`train` — depois de um scroll ate o fim,
teclar 1/2/3 ficava sem resposta por ~2 minutos, porque os slots dessa thread
sao servidos em ordem de chegada.
`LibraryTab._pede_peaks_visiveis` corrige isso perguntando ao `QTableView`
quais linhas o viewport cobre AGORA: um `QTimer` de `ATRASO_PEAKS_MS` (250ms),
reiniciado a cada rolagem, absorve o arrasto (so a parada final vira pedido),
e `MAX_PEAKS_EM_VOO` (3) limita quantos `compute_peaks` ficam pendentes na
thread do servico ao mesmo tempo — e o que garante que uma decisao pelo
teclado nunca espere mais que ~1s atras da fila. `ServiceWorker.peaks_failed`
existe so por causa desse teto: sem avisar uma falha, a vaga dela nunca
seria liberada e a aba pararia de pedir qualquer onda depois de tres falhas.

**A miniatura da capa na tabela vem de um thumb reduzido em disco, nao da
capa original.** `ui/widgets/thumbs.py` grava `covers/<sha1>.thumb.png` (96px)
na primeira vez que a linha e pintada, e toda pintura seguinte le esse
arquivo pequeno em vez de decodificar o jpeg embutido inteiro (720x720 a
1280x720 numa biblioteca real) so para reduzi-lo a 34px. Medido: decodificar
a capa cheia e escalar custava 4,25 ms; ler o thumb, 0,22 ms. Era 72% do
tempo de paint da aba Biblioteca — o primeiro paint caia de 482 ms para
~60 ms so com isso, e para ~30 ms depois que o thumb ja existe em disco (toda
abertura a partir da segunda). O thumb NAO tem versao dentro dele, igual ao
`.npy` de peaks: e `PresentationCache.put()` quem apaga o thumb obsoleto ao
gravar uma capa nova, porque nada mais o faria sozinho. `THUMB_SUFFIX` mora em
`presentation.py`, nao em `thumbs.py` — quem apaga e o dominio, e o sufixo
composto (`.thumb.png`, nao `.png`) e o que impede colidir com uma capa que ja
seja PNG. A geracao em si mora em `ui/` e nao em `presentation.py`: `dj scan`
e `dj train` rodam headless e nao importam Qt (ver a secao do executavel), e
reduzir um jpeg precisa de um decodificador de imagem — a tela e a unica
camada que tem um.

Armadilha do `mutagen`: `mutagen.File(...)` devolve um objeto **falsy** para um
arquivo sem tags, e `None` so quando nao reconhece o formato. Teste sempre com
`is None` — `if arquivo:` descarta em silencio toda track sem metadado.

**`ui/viewmodel.py` nao importa Qt.** E a fronteira entre o dominio e a tela:
`viewmodel.py` traduz `TrackService` em dataclasses puras (`TrackRow`,
`ReviewState`, `LibraryState`, `ModelState`) que os widgets consomem, e nada
nele sabe o que e um `QWidget`. Isso e o que permite testar a logica de tela —
o que aparece, quantas faltam, quando a fila esvazia — com pytest puro, sem
`QApplication`. Ha um teste (`tests/test_viewmodel.py`) que garante isso
gramaticalmente, lendo o modulo e falhando se aparecer um import de PySide6 —
nao adicione um import de Qt aqui, mesmo que pareca inofensivo.

**Camadas de `ui/`.** `viewmodel.py` (sem Qt, dados puros) → `worker.py`
(`ServiceWorker`, os slots que rodam na thread do servico, so fala com
`TrackService` e com o viewmodel) → `window.py`/`review_tab.py`/
`library_tab.py`/`model_tab.py`/`widgets/` (widgets Qt, so falam com o worker
por sinal/slot, nunca com `TrackService` direto). Cada camada so conhece a de
baixo; um widget que chamasse `TrackService` direto quebraria a regra de "uma
so thread dona do servico" da secao de concorrencia acima.

`config.py` cresceu para servir a tela: alem de `load_config`, ele expoe
`read_raw` (parse sem validar, para preencher o formulario quando o config
esta quebrado), `SettingsDraft` (o texto cru dos campos), `validate_settings`
(puro, roda a cada tecla) e `apply_draft` (cria as pastas, roda uma vez ao
salvar). A separacao entre validar e aplicar e o que permite validar a cada
tecla sem criar uma pasta a cada tecla -- e o que mantem toda a regra
testavel sem `QApplication`.

**Testes** injetam um extrator falso (`ExtratorFalso`, que deriva o vetor do nome
do arquivo) pelo parametro `extractor` de `TrackService`, e passam
`max_workers=1` para evitar o pool. Os testes que exercitam o pool ou o extrator
real sao explicitos sobre isso no nome.

## Convencoes

- **Portugues sem acentos** em tudo: nomes de variaveis locais, funcoes internas,
  comentarios, docstrings, mensagens de erro e nomes de teste. Todo `src/` esta
  livre de acentos (ha tres escapes isolados em comentarios de teste) — escreva
  sem acento.
- API publica (dataclasses, metodos de classe, campos JSON, nomes de features)
  em ingles; o interior das funcoes, em portugues.
- Comentarios explicam **por que**, nao o que — e sao longos quando a decisao nao
  e obvia (qual excecao, qual race, qual limite). Siga esse tom.
- **Nenhum hex fora de `design/design-tokens.json`.** E a fonte unica de cor,
  tipografia, espaco, raio e tamanho. `ui/tokens.py` e `ui/app.qss` sao gerados
  a partir dele por `design/build_tokens.py` — nunca escreva um literal de cor
  direto num widget ou no QSS; edite o JSON e rode
  `uv run python design/build_tokens.py`. Ha um teste
  (`tests/test_tokens.py::test_nenhum_hex_fora_do_json`) que varre `ui/` atras
  de hex literal e falha se achar um fora dos dois arquivos gerados.
- Commits: conventional commits com escopo (`fix(trackclassifier):`, `feat(ci):`).
- ruff: `line-length = 100`, regras `E,F,I,UP,B`.

## Documentacao de design

`docs/superpowers/specs/` e `docs/superpowers/plans/` guardam os designs e planos
das mudancas maiores (o design original e a paralelizacao do scan). Consulte
antes de reescrever essas areas.
