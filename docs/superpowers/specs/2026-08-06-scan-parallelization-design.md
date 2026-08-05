# Paralelização do scan e progresso — design

**Data:** 2026-08-06
**Status:** design aprovado, pronto para plano de implementação

## Problema

`dj train`/`dj scan` analisam o acervo do usuário de forma sequencial: um arquivo por vez, cada um passando por decodificação via ffmpeg e extração das 44 features. Em uso real, um scan de 341 tracks levou aproximadamente 40 minutos, sem nenhuma saída no terminal durante esse tempo — o usuário não tinha como distinguir progresso normal de travamento.

Cada análise de track é independente das demais (nenhum estado compartilhado durante a extração), o que torna o trabalho um candidato natural a paralelização entre núcleos de CPU.

## Decisões de design

### `ProcessPoolExecutor`, não threads

`librosa`/`numpy` seguram o GIL em boa parte dos cálculos internos (STFT, HPSS, detecção de onset). Paralelizar com threads não produziria ganho real de throughput para esse tipo de carga. Processos contornam o GIL — é a escolha correta para trabalho CPU-bound como este.

### Escritor único do cache permanece no processo principal

Os workers nunca escrevem no `AnalysisCache`. Uma função de topo de módulo roda em cada processo, decodifica e extrai, e devolve o resultado (`TrackAnalysis` ou mensagem de erro) para o processo principal. Só o processo principal chama `cache.put()`/`cache.save()`, preservando a invariante de escritor único que o cache já tem (parquet não é seguro para escrita concorrente de múltiplos processos).

### Threads internas de BLAS limitadas a 1 por worker

Sem essa limitação, cada processo tentaria abrir sua própria pool de threads para álgebra linear (via OpenBLAS/MKL, usado internamente por `librosa`/`numpy`). Com N processos rodando em paralelo, cada um abrindo M threads internas, a CPU satura por concorrência interna e o ganho do paralelismo entre arquivos se perde. Cada worker usa `threadpoolctl.threadpool_limits(limits=1)` (já é dependência transitiva via `scikit-learn`) ao redor da chamada de extração.

### As duas fases do scan são unificadas antes de submeter ao pool

Hoje `analyze_all()` chama `_analyze()` duas vezes — uma para as pastas rotuladas, outra para a inbox — cada chamada reiniciando a contagem do zero. O novo design junta `scan_labeled(config) + scan_inbox(config)` numa lista só antes de filtrar o que já está em cache e submeter o restante ao pool. Isso:

- Dá progresso combinado e consistente (um único contador `concluidas/total` para o scan inteiro, não dois contadores separados que resetam).
- Resolve de brinde um problema que ficou pendente da revisão final do projeto original: o cache era salvo periodicamente a cada 10 extrações novas, mas o contador resetava a cada fase — uma interrupção podia perder até 18 extrações (9 de cada fase) em vez das 9 pretendidas. Com um único contador sobre o lote combinado, o save periódico volta a valer o que sempre foi pretendido.
- A partição final entre `_labeled` e `_inbox` continua correta sem rastreamento extra: cada `TrackRef` já carrega seu próprio `label` (`None` para inbox, um `Label` para rotuladas), então depois de coletar os resultados aceitos basta filtrar por `ref.label is not None`.

### Pool só entra em cena quando há mais de 1 arquivo novo **e** `max_workers > 1`

Um `dj scan` do dia a dia normalmente encontra 0-2 arquivos novos (o resto já está em cache, indexado por SHA1). Subir um `ProcessPoolExecutor` para processar 1 arquivo custa mais do que economiza. Quando `len(pendentes) <= 1`, a extração roda direto no processo principal, sem overhead de pool.

A condição também verifica `max_workers > 1`, não só a contagem de pendentes — importante porque `max_workers=1` sozinho **não** evita o `ProcessPoolExecutor`; ele só limitaria a concorrência a um worker, mas ainda subiria um processo filho. No macOS (método `spawn`, padrão desde Python 3.8), o processo filho reimporta tudo do zero e não herda automaticamente o `sys.path` do processo pai — em particular, o `pythonpath = ["."]` que o pytest injeta para tornar `tests/` importável não chega ao filho. Um teste que usa `ExtratorFalso` (definido em `tests/test_service.py`, nunca instalado como pacote) falharia ao tentar despicklar a tarefa no processo filho. Com a condição checando `max_workers > 1` também, passar `max_workers=1` nos testes garante que a extração roda sempre no processo principal, sem nunca tocar em `ProcessPoolExecutor` — nenhum risco de import entre processos.

### Progresso via callback, não `print()` dentro do serviço

`TrackService.analyze_all()` ganha um parâmetro opcional `on_progress: Callable[[int, int, str], None] | None`, chamado a cada extração concluída com `(concluidas, total, nome_do_arquivo)`. `service.py` continua sem I/O de console embutido — é o `cli.py` que decide como apresentar o progresso, mantendo a separação de responsabilidade que o projeto já segue em todo o resto do código.

O CLI imprime uma linha por conclusão: `[42/341] nome.mp3`.

### Número de workers

`TrackService.__init__` ganha um parâmetro opcional `max_workers: int | None = None`, com padrão `os.cpu_count() or 1` quando não especificado (`os.cpu_count()` pode devolver `None` em ambientes onde a contagem de CPUs não é detectável). Isso permite que os testes passem `max_workers=1` para manter determinismo e velocidade na suíte, sem introduzir uma chave nova no `config.toml` que o usuário nunca pediu.

## Comportamento sob erro

Cada worker captura exceções da própria extração (`AudioDecodeError`, `TrackTooShortError`, qualquer outra) e devolve o erro como string, em vez de deixar a exceção propagar e derrubar o processo. O processo principal converte isso num `FailedItem`, exatamente como o comportamento sequencial atual — nenhuma mudança na semântica de falha contida por arquivo, só em como o trabalho é distribuído.

Timeout de subprocesso do `ffmpeg` (já em vigor desde a correção da revisão final, 120s) continua valendo dentro de cada worker, individualmente por arquivo — um ffmpeg travado num arquivo corrompido não trava os outros workers.

## Testes

- Testes existentes de `TrackService` passam `max_workers=1` explicitamente, preservando velocidade e determinismo (sem subir processos reais a cada teste, e sem o risco de import entre processos descrito acima).
- Um teste novo verifica paralelismo de fato: usa o `HandcraftedExtractor` real (não `ExtratorFalso`, que não é importável num processo filho) sobre 2+ WAVs sintéticos pequenos, com `max_workers=2`, e confirma que o resultado final está correto (cache populado, todas as tracks presentes) — sem depender de instrumentar qual processo rodou o quê, só do resultado.
- Teste do limiar "pool só com >1 pendente e max_workers>1": um único arquivo novo, mesmo com `max_workers>1`, não aciona `ProcessPoolExecutor` (verificável indiretamente por não exigir que a classe de extração seja picklable nesse caminho — usar `ExtratorFalso` com 1 pendente e `max_workers=4` deve funcionar sem erro de import, provando que o pool não foi usado).
- Teste do save periódico usando o contador unificado: interrompe simuladamente após N extrações do lote combinado (rotuladas + inbox misturadas) e confirma que o save ocorreu no ponto certo, cruzando as duas fontes.

## Fora de escopo

- Configuração de `max_workers` via `config.toml` — não pedido, YAGNI até haver necessidade real.
- Paralelizar o treino do modelo (`Ridge`/`RidgeCV` já é rápido, não é o gargalo).
- Barra de progresso visual (spinner, `tqdm`) — uma linha por arquivo concluído é suficiente e não adiciona dependência nova.
- Qualquer um dos outros itens deixados pendentes na revisão final do projeto original (consolidação de helper ffmpeg, `--port` configurável, limpeza de cache de transcodificação, aviso de otimismo do LOO, etc.) — fora do escopo desta rodada, que é especificamente velocidade de scan.
