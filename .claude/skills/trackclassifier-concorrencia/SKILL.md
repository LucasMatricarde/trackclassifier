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
`ProcessPoolExecutor`. Numa sessao esse caminho crashou 5/5 vezes (SIGSEGV em
~11s, numa track real de 320kbps, sem pool algum envolvido) enquanto o pool
rodava limpo no mesmo bundle.

O fix em `_analyze`:
`usa_pool = _empacotado() or (max_workers > 1 and total > 1)` -- empacotado forca
pool sempre, mesmo para 1 pendente e mesmo com `max_workers=1`. Fora do bundle o
atalho sequencial segue valendo, e e o que os testes usam com `ExtratorFalso` sem
pagar overhead de subprocesso.

**CUIDADO ao ler o paragrafo acima: o fix e contencao, nao cura, e a causa raiz
continua ABERTA.** Uma versao anterior deste texto afirmava que o gatilho tinha
sido isolado e que o crash era "deterministico, nao intermitente". Isso foi
**falsificado** por medicao posterior e nao deve ser repetido:

- O binario do numpy e **byte-identico** entre o bundle que crashou e os que nao
  crasham -- mesmo UUID (`5C58E205-AB5A-32C6-B646-414E5D10AD6D`) no crash report,
  no `.app` reconstruido e na venv. Nao e build envenenado.
- Um bundle reconstruido do **mesmo commit pre-fix** nao reproduz nada: 5/5
  limpo com 1 track sequencial; 3/3 limpo com 20 tracks sequenciais e sem
  pinning; 12 execucoes concorrentes de 20 tracks sob carga (240 extracoes no
  processo principal) sem um unico crash.
- Um bundle-sonda isolando cada camada (matmul puro, filtro mel, STFT, HPSS,
  `compute_spectra`, `decode`, `extract`, `extract_one`, caminho completo do
  `TrackService`, com e sem PySide6, console e windowed `.app`) nunca crashou em
  ~15 execucoes.

Ou seja: o crash e **intermitente e dependente de estado do ambiente**, e a
condicao que o dispara nao foi identificada. O que se sabe com seguranca e so
que a stack e sempre a mesma (chamada para o endereco 0 a partir de
`generic_wrapped_legacy_loop`, sob `PyUFunc_GeneralizedFunctionInternal`, ou
seja um gufunc -- `matmul` e o candidato obvio no caminho do mel) e que **nao e
OOM** (24 GB com 65% livre, `SIGNAL code 11`, nao jetsam).
`KMP_DUPLICATE_LIB_OK=TRUE` nao mudou nada, o que afasta a explicacao classica
de duas copias de `libomp.dylib` (o bundle carrega tres: `sklearn`,
`Frameworks/` e `Resources/`).

O fix se justifica mesmo assim, e pelo mesmo motivo que a retentativa em pool ja
existia: um segfault num filho descartavel custa uma track, no processo
principal custa a janela inteira. Nao o trate como prova de que a causa foi
entendida -- se o crash voltar, ele pode voltar **dentro** de um worker.

## O aviso acima se confirmou: reproduzido dentro de worker sob carga real

Scan completo da biblioteca real do usuario (377 tracks, pool de 8, sem
interrupcao) reproduziu o segfault dentro de um worker -- mesma stack de
sempre (`EXC_BAD_ACCESS` em `generic_wrapped_legacy_loop`). A retentativa item
a item absorveu o dano (zero falhas em `service.failures()`), mas a **1.6s/track**
medidos com pool limpo viraram **~12s/track** -- ETA de ~72min para as 377, contra
os 10min19 medidos antes. E o que explicava as ~2h que o usuario reportou: nao
e lentidao, e segfault sendo escondido pela contencao.

Isso e evidencia real, sob carga real, a favor da hipotese original de
concorrencia ("pool de 8 morre") que o paragrafo acima descartou com base em
testes sinteticos (matmul isolado, extract_one repetido em loop curto) que
nunca sustentaram carga por tempo suficiente para disparar o bug. Os dois
achados nao se contradizem: o bug parece precisar de volume real (centenas de
extracoes, horas de CPU) para aparecer, nao de uma condicao isolavel num
experimento de minutos.

Tentativa de varrer o teto (`TRACKCLASSIFIER_MAX_WORKERS=4`) ficou
**contaminada**: a rodada anterior (W=8) foi interrompida a mao no meio com
`pkill`, deixando avisos de "leaked semaphore objects" no log, e a rodada de
W=4 seguinte falhou 60/60 com `BrokenProcessPool` -- um padrao diferente do
segfault isolado (falha total e imediata, nao worker ocasional), mais coerente
com semaforo POSIX orfao do processo morto a mao do que com o bug do numpy.
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
