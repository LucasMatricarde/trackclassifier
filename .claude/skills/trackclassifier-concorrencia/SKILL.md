---
name: trackclassifier-concorrencia
description: Use ao mexer em service._analyze, no pool do scan, no cancelamento ou na thread do servico da UI do trackclassifier. Cobre as duas formas de concorrencia (ProcessPoolExecutor no scan, QThread unica dona do TrackService), o gate _empacotado() que forca pool no app (historico do SIGSEGV do numpy), o envio em blocos com retentativa item a item, o pinning de threads de BLAS e o cancelamento fora do Qt. Gatilhos: "BrokenProcessPool", "segfault", "EXC_BAD_ACCESS", "worker morreu", "max_workers", "paralelizar scan", "cancelar scan", "travou a janela".
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
`generic_wrapped_legacy_loop` (`PyUFunc_GeneralizedFunctionInternal`) -- familia
do numpy#27709. A hipotese original era concorrencia ("pool de 8 morre, pool de 1
nunca morreu") e o problema parecia intermitente. As duas coisas eram medicao
incompleta: o "pool de 1" que nunca morria era a *retentativa* do bloco quebrado
-- ja um subprocesso -- nunca a extracao **direta**. O gate
`usa_pool = max_workers > 1 and total > 1` (pensado so para poupar o overhead de
subir um subprocesso para 1 arquivo) nunca tinha sido testado isolado: com
`TRACKCLASSIFIER_MAX_WORKERS=1`, ou com qualquer teto quando so ha 1 pendente,
`extract_one` rodava direto na thread do CLI/janela -- fora de qualquer
`ProcessPoolExecutor`. Reproduzido de forma **deterministica**, nao intermitente:
SIGSEGV em ~11s, sempre, numa track real de 320kbps, sem pool algum envolvido. A
mesma chamada dentro de um `ProcessPoolExecutor(max_workers=1)` (ainda um unico
subprocesso) nunca falhou. A mesma chamada fora do bundle (`uv run dj scan`)
tambem nunca falhou -- numpy e codigo identicos, so o lancamento via bootloader
do PyInstaller difere. A "intermitencia" relatada antes era este mesmo bug
escondido atras de testes que sempre passavam por pool (>1 pendente, >1 worker):
cada subprocesso corre o risco uma vez, e com centenas de tracks uma morte rara
ja bastava para a cascata de `BrokenProcessPool` descrita abaixo.

O fix em `_analyze`:
`usa_pool = _empacotado() or (max_workers > 1 and total > 1)` -- empacotado forca
pool sempre, mesmo para 1 pendente e mesmo com `max_workers=1`. Fora do bundle o
atalho sequencial segue valendo, e e o que os testes usam com `ExtratorFalso` sem
pagar overhead de subprocesso. Verificado no bundle real, reconstruido apos o
fix: os dois cenarios que antes derrubavam 100% das vezes (1 pendente com teto
default; qualquer total com `TRACKCLASSIFIER_MAX_WORKERS=1`) rodaram limpos, e a
biblioteca de 20 tracks completa com `MAX_WORKERS=1` (o pior caso, que antes
zerava tudo) terminou 20/20 sem nenhum crash report novo.

**Causa raiz de *por que* rodar fora de subprocesso crasha continua aberta** --
nao e OOM (24 GB, 65% livre, `SIGNAL code 11`, nao jetsam). Suspeita, nao
confirmada: dispatch de SIMD do numpy colidindo com o bootstrap da thread pool
interna do scipy/ducc0 (visto no backtrace: 16 threads ociosas em
`ducc_thread_pool::worker_main`, provavelmente do primeiro `librosa.stft`) na
primeira chamada do processo. `KMP_DUPLICATE_LIB_OK=TRUE` nao mudou nada, o que
afasta a explicacao classica de duas copias de `libomp.dylib` carregadas (o
bundle carrega tres: `sklearn`, `Frameworks/` e `Resources/`, mas essa nao e a
causa). Nao vale mais investigar: o gatilho determinista foi isolado e contido
sem depender de entender o numpy.

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
