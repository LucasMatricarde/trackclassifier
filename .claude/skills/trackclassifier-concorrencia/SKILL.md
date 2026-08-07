---
name: trackclassifier-concorrencia
description: Use ao mexer em service._analyze, no pool do scan, no cancelamento ou na thread do servico da UI do trackclassifier. Cobre as duas formas de concorrencia (ProcessPoolExecutor no scan, QThread unica dona do TrackService), o gate _empacotado() que forca pool no app, a causa raiz do SIGSEGV empacotado (corrida de escrita no cache de compilacao do numba/librosa apos rebuild) e o aquecimento serial que a resolve, o envio em blocos com retentativa item a item, o pinning de threads de BLAS e o cancelamento fora do Qt. Gatilhos: "BrokenProcessPool", "segfault", "EXC_BAD_ACCESS", "worker morreu", "max_workers", "paralelizar scan", "cancelar scan", "travou a janela", "numba", "cache corrompido".
---

# Concorrencia do trackclassifier

## Duas formas distintas

O scan usa **processos** (`ProcessPoolExecutor`, workers limitados a 8 por causa
do pico de memoria de ffmpeg+librosa por worker). Ja a UI usa uma **QThread
unica dona do `TrackService`** (`ui/worker.py`): a janela manda pedidos por slot
e recebe sinais, entao nao ha lock nem parquet escrito de dois lugares.
`apply._destino_livre` segue reservando o nome de destino atomicamente com
`os.open(O_CREAT|O_EXCL)` -- o desfazer e o scan podem disputar a mesma pasta.

`TRACKCLASSIFIER_MAX_WORKERS` sobrescreve o teto -- nao serve mais para
reproduzir o segfault (isolado abaixo), mas continua util para limitar memoria
numa biblioteca grande.

## `extract_one` nao pode rodar fora de subprocesso quando empacotado

`_empacotado()` em `service.py` garante isso. Historico: um worker do scan morria
no `.app` (nunca em `uv run`) com `EXC_BAD_ACCESS` no endereco 0, em
`generic_wrapped_legacy_loop` (`PyUFunc_GeneralizedFunctionInternal`). A hipotese
original era concorrencia ("pool de 8 morre, pool de 1 nunca morreu") e o
problema parecia intermitente. As duas coisas eram medicao incompleta: o "pool
de 1" que nunca morria era a *retentativa* do bloco quebrado -- ja um
subprocesso -- nunca a extracao **direta**. O gate
`usa_pool = max_workers > 1 and total > 1` (pensado so para poupar o overhead de
subir um subprocesso para 1 arquivo) nunca tinha sido testado isolado: com
`TRACKCLASSIFIER_MAX_WORKERS=1`, ou com qualquer teto quando so ha 1 pendente,
`extract_one` rodava direto na thread do CLI/janela -- fora de qualquer
`ProcessPoolExecutor`. Numa sessao esse caminho crashou 5/5 vezes (SIGSEGV em
~11s, numa track real de 320kbps, sem pool algum envolvido) enquanto o pool
rodava limpo no mesmo bundle.

O fix em `_analyze`:
`usa_pool = _empacotado() or (max_workers > 1 and total > 1)` -- empacotado forca
pool sempre, mesmo para 1 pendente e mesmo com `max_workers=1`. Fora do bundle o
atalho sequencial segue valendo, e e o que os testes usam com `ExtratorFalso` sem
pagar overhead de subprocesso. Continua valendo mesmo depois da causa raiz
fechada (proxima secao): um segfault num filho descartavel custa uma track, no
processo principal custa a janela inteira -- e outras bibliotecas com o mesmo
padrao (`cache=True` do numba) podem existir sem ter sido auditadas.

## Causa raiz fechada: corrida de escrita no cache de compilacao do numba

`librosa/util/utils.py` tem varios `@numba.guvectorize(cache=True)`
(`_localmax`, `_localmin`, `__peak_pick`) que `track_bpm`
([spectral.py](../../../src/trackclassifier/spectral.py)) aciona a cada track
via `librosa.beat.beat_track`. `cache=True` grava o codigo compilado (LLVM) em
disco, num `__pycache__` ao lado do `.py` de origem -- dentro do bundle, isso e
`Contents/Resources/librosa/util/__pycache__`.

Isolado com `faulthandler.enable()` em `packaging/entry_point.py` (ver
docstring de `_ativa_faulthandler`): o traceback Python real, nunca visto antes
porque so existia um `.ips` do sistema sem frames Python, mostrou

```
File "numba/np/ufunc/gufunc.py", line 263 in __call__
File "librosa/util/utils.py", line 1122 in localmax
File "librosa/beat.py", line 651 in __last_beat
...
File "trackclassifier/spectral.py", line 163 in track_bpm
```

Nao e o numpy -- e um gufunc **compilado pelo numba**, que se registra no
dispatcher de ufunc do numpy (por isso a stack em C do `.ips` sempre apontou
para `_multiarray_umath`/`generic_wrapped_legacy_loop`: e o numpy despachando
para o codigo de maquina que o numba gerou).

Mecanismo confirmado por medicao (nao so inferido): todo `rm -rf dist build` +
rebuild do PyInstaller reinicia esse cache do zero (o `__pycache__` do bundle
nao sobrevive). No primeiro scan depois de um build novo, o pool sobe **8
processos simultaneos**, todos com cache frio, e todos tentam compilar via LLVM
e escrever no mesmo arquivo de cache ao mesmo tempo. Essa escrita concorrente
corrompe o arquivo -- e todo processo que depois **le** esse cache corrompido
segfaulta executando o gufunc, nao so quem escreveu. E por isso que o crash e
sistematico (nao intermitente) uma vez que comeca: 235/235 crashes num scan de
377 tracks contra cache recem-zerado, **0/377** rodando a mesma extracao com o
cache ja aquecido por uma chamada serial antes -- dois testes, mesma maquina,
mesmo binario, unica variavel foi o estado do cache.

Isso tambem explica por que nunca aparece em `uv run dj`: sem rebuild de bundle
apagando o cache, a primeira execucao de sempre ja compila sem concorrencia
nenhuma (um so processo, ou pool com cache ja quente de uma sessao anterior).

**Fix**: `service._aquece_cache_numba()`, chamada no processo PAI logo antes de
criar o `ProcessPoolExecutor`, roda `track_bpm(compute_spectra(...))` sobre
ruido sintetico uma unica vez, sem concorrencia. Isso compila e grava o cache
uma vez so; todo worker spawnado depois so **le** um arquivo ja valido --
leitura concorrente e segura, so a escrita concorrente nao e. Falha ali nunca
derruba o scan (`except Exception: pass`): na pior hipotese, sem aquecer, o
comportamento volta a ser o de antes do fix, nunca pior.

Verificado life-cycle completo: cache zerado (build fresco) + pool de 8 sem
aquecimento previo = 235 crashes em ~65 tracks antes do teste ser interrompido.
Mesmo cache zerado + `_aquece_cache_numba()` antes do pool = 372 tracks, 8
workers do inicio ao fim, **0 crashes**. Repetido apos rebase e rebuild
limpo (build seguinte, PR de outra sessao mesclada no meio) com o mesmo
resultado.

## O que ficou provisoriamente descartado e depois se revelou correto

Duas hipoteses anteriores (volume/carga real, e concorrencia do pool de 8)
foram descartadas por evidencia sintetica insuficiente e depois voltaram a
fazer sentido: um scan real de 377 tracks tinha reproduzido o segfault dentro
de worker, virando **~12s/track** em vez de 1.6s/track -- exatamente o efeito
esperado de um bloco caindo pra pool-de-1 apos `BrokenProcessPool`. A causa nao
era volume nem o TAMANHO do pool; era o pool de 8 rodando **uma unica vez**
contra cache frio, no comeco do scan -- e depois de corromper o cache, cada
retry subsequente (mesmo em pool de 1) tambem lia o arquivo corrompido e
crashava, ate uma escrita eventualmente limpa reverter o estado. Serve de
licao: sintomas medidos sob carga real (ETA inflado, retries em cascata) sao
dado, mesmo quando o experimento sintetico que tentou isola-los falhou em
reproduzir.

Tentativa de varrer o teto (`TRACKCLASSIFIER_MAX_WORKERS=4`) ficou
**contaminada**: a rodada anterior (W=8) foi interrompida a mao no meio com
`pkill`, deixando avisos de "leaked semaphore objects" no log, e a rodada de
W=4 seguinte falhou 60/60 com `BrokenProcessPool` -- um padrao diferente do
segfault isolado (falha total e imediata, nao worker ocasional), mais coerente
com semaforo POSIX orfao do processo morto a mao do que com o bug do numba.
Nao ha dado limpo comparando tetos menores; **nao mude o default de 8 sem
antes rodar essa comparacao sem interromper nenhuma rodada no meio.**

## Pinning de threads dos workers

`service._fixa_threads_dos_workers` poe `VECLIB_MAXIMUM_THREADS=1` e companhia no
`os.environ` do PAI antes de criar o pool (unico canal que o Accelerate respeita;
com spawn o filho herda antes de importar numpy -- um `initializer=` rodaria
tarde demais). Isso corrige uma intencao que estava quebrada:
`threadpool_limits(limits=1)` em `extract_one` funciona no Linux (OpenBLAS) mas e
no-op no macOS, onde o BLAS e o Accelerate e `threadpool_info()` devolve lista
vazia. Medido: 16 threads por worker sem o pinning, 2 com. Nao ha mais motivo
para achar que isso cura algo -- fica porque a intencao original era essa.

## Um worker morto nao custa mais o lote

`ProcessPoolExecutor` nao isola a morte de um filho: o executor inteiro quebra e
todo future pendente levanta `BrokenProcessPool`, mesmo os que nem comecaram --
um unico segfault virava ~370 falhas identicas (6 tracks analisadas de 377). Por
isso `_analyze` manda o lote em **blocos** de `max_workers * 4`, cada um no
proprio pool: a morte so alcanca o bloco em voo. O que sobra do bloco e
reprocessado **item a item, num pool de 1 worker** -- onde o segfault custa
exatamente a track que o causou. A retentativa usa pool, e nao `extract_one`
direto, porque nesta thread um segfault levaria a janela junto. Medido, para nao
reinventar os desenhos descartados: retentar o lote inteiro num pool novo repete
a cascata; mandar tudo item a item custa ~140 min contra ~10 min do pool cheio.

`_analyze` reordena o resultado pela ordem original de entrada -- `as_completed`
devolve fora de ordem e a estabilidade entre execucoes e garantida.

## O cancelamento do scan atravessa as threads fora do Qt, de proposito

`analyze_all(should_cancel=...)` consulta o flag entre extracoes, e
`ServiceWorker.request_cancel()` e um metodo **normal, nao um `@Slot`**: durante
um scan o loop de eventos da thread do worker esta parado dentro de
`analyze_all`, entao um slot enfileirado so rodaria depois do scan acabar -- o
oposto do que se quer. Um `threading.Event` e o unico estado compartilhado entre
as duas threads. Cancelar nao e falhar: o que nao foi extraido continua pendente
para o proximo scan e **nao** entra em `failures()`. O teto de latencia e uma
extracao em voo (`shutdown(cancel_futures=True)` descarta so o que nao comecou),
porque matar um worker no meio de ffmpeg/librosa nao e opcao.
