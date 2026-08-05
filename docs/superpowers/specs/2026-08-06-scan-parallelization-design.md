# Paralelização do scan e progresso — design

**Data:** 2026-08-06
**Status:** design aprovado, pronto para plano de implementação

## Problema

`dj train`/`dj scan` analisam o acervo do usuário de forma sequencial: um arquivo por vez, cada um passando por decodificação via ffmpeg e extração das 44 features. Em uso real, um scan de 341 tracks levou aproximadamente 40 minutos, sem nenhuma saída no terminal durante esse tempo — o usuário não tinha como distinguir progresso normal de travamento.

Cada análise de track é independente das demais (nenhum estado compartilhado durante a extração), o que torna o trabalho um candidato natural a paralelização entre núcleos de CPU.

## Decisões de design

### `ProcessPoolExecutor`, não threads

A carga por track tem duas partes: o `ffmpeg` (subprocesso, já paralelo por natureza — a thread Python só bloqueia esperando) e a extração em `librosa`/`numpy` (STFT, HPSS, detecção de onset). Threads dariam algum ganho, já que `numpy` libera o GIL dentro das rotinas de BLAS/FFT e o `ffmpeg` libera durante a espera — não é verdade que threads não ajudariam em nada.

A escolha por processos é por outra razão: entre as chamadas que liberam o GIL há bastante trabalho em nível Python (laço de janelas, agregação estatística, construção dos vetores) que permanece serializado sob threads. Processos removem esse teto de vez, e o custo — dados atravessando pickle — é irrisório aqui, já que cada worker devolve apenas um `TrackAnalysis` (44 floats mais a curva de energia), não o áudio decodificado.

### Escritor único do cache permanece no processo principal

Os workers nunca escrevem no `AnalysisCache`. Uma função de topo de módulo roda em cada processo, decodifica e extrai, e devolve o resultado (`TrackAnalysis` ou mensagem de erro) para o processo principal. Só o processo principal chama `cache.put()`/`cache.save()`, preservando a invariante de escritor único que o cache já tem (parquet não é seguro para escrita concorrente de múltiplos processos).

### Threads internas de BLAS limitadas a 1 por worker

Sem essa limitação, cada processo tentaria abrir sua própria pool de threads para álgebra linear (via OpenBLAS/MKL, usado internamente por `librosa`/`numpy`). Com N processos rodando em paralelo, cada um abrindo M threads internas, a CPU satura por concorrência interna e o ganho do paralelismo entre arquivos se perde. Cada worker usa `threadpoolctl.threadpool_limits(limits=1)` (dependência direta em `pyproject.toml` — deixou de ser apenas transitiva via `scikit-learn` quando essa chamada explícita foi adicionada) ao redor da chamada de extração.

### As duas fases do scan são unificadas antes de submeter ao pool

Hoje `analyze_all()` chama `_analyze()` duas vezes — uma para as pastas rotuladas, outra para a inbox — cada chamada reiniciando a contagem do zero. O novo design junta `scan_labeled(config) + scan_inbox(config)` numa lista só antes de filtrar o que já está em cache e submeter o restante ao pool. Isso:

- Dá progresso combinado e consistente (um único contador `concluidas/total` para o scan inteiro, não dois contadores separados que resetam).
- Resolve de brinde um problema que ficou pendente da revisão final do projeto original: o cache era salvo periodicamente a cada 10 extrações novas, mas o contador resetava a cada fase — uma interrupção podia perder até 18 extrações (9 de cada fase) em vez das 9 pretendidas. Com um único contador sobre o lote combinado, o save periódico volta a valer o que sempre foi pretendido.
- A partição final entre `_labeled` e `_inbox` continua correta sem rastreamento extra: cada `TrackRef` já carrega seu próprio `label` (`None` para inbox, um `Label` para rotuladas), então depois de coletar os resultados aceitos basta filtrar por `ref.label is not None`.

### Pool só entra em cena quando há mais de 1 arquivo novo **e** `max_workers > 1`

Um `dj scan` do dia a dia normalmente encontra 0-2 arquivos novos (o resto já está em cache, indexado por SHA1). Subir um `ProcessPoolExecutor` para processar 1 arquivo custa mais do que economiza. Quando `len(pendentes) <= 1`, a extração roda direto no processo principal, sem overhead de pool.

A condição também verifica `max_workers > 1`, não só a contagem de pendentes — importante porque `max_workers=1` sozinho **não** evita o `ProcessPoolExecutor`; ele só limitaria a concorrência a um worker, mas ainda subiria um processo filho. Subir um `ProcessPoolExecutor` tem custo real de tempo de parede mesmo antes de qualquer trabalho começar — spawnar o subprocesso e reimportar o módulo do zero nele —, medido em ~1.4s contra ~0.026s de uma carga trivial sequencial durante a revisão final. Pagar esse custo para processar 0-1 arquivo (o caso comum: um `dj scan` do dia a dia, a maior parte já em cache) não compensa. Com a condição checando `max_workers > 1` também, passar `max_workers=1` nos testes garante que a extração roda sempre no processo principal, evitando esse overhead de startup em toda a suíte de testes.

### Progresso via callback, não `print()` dentro do serviço

`TrackService.analyze_all()` ganha um parâmetro opcional `on_progress: Callable[[int, int, str], None] | None`, chamado a cada extração concluída com `(concluidas, total, nome_do_arquivo)`. `service.py` continua sem I/O de console embutido — é o `cli.py` que decide como apresentar o progresso, mantendo a separação de responsabilidade que o projeto já segue em todo o resto do código.

O CLI imprime uma linha por conclusão: `[42/341] nome.mp3`.

### Número de workers

`TrackService.__init__` ganha um parâmetro opcional `max_workers: int | None = None`, com padrão `os.cpu_count() or 1` quando não especificado (`os.cpu_count()` pode devolver `None` em ambientes onde a contagem de CPUs não é detectável). Isso permite que os testes passem `max_workers=1` para manter determinismo e velocidade na suíte, sem introduzir uma chave nova no `config.toml` que o usuário nunca pediu.

## Comportamento sob erro

Cada worker captura exceções da própria extração (`AudioDecodeError`, `TrackTooShortError`, qualquer outra) e devolve o erro como string, em vez de deixar a exceção propagar e derrubar o processo. O processo principal converte isso num `FailedItem`, exatamente como o comportamento sequencial atual — nenhuma mudança na semântica de falha contida por arquivo, só em como o trabalho é distribuído.

**Worker morto é um modo de falha novo que a versão sequencial não tinha.** Se um processo worker morre de verdade (segfault dentro de `ffmpeg`/`librosa`, OOM, `BrokenProcessPool`), a exceção não vem de dentro de `extract_one` — ela aparece ao chamar `futuro.result()` no processo principal. Sem tratamento, uma única track problemática derrubaria o scan inteiro, o que seria uma regressão de robustez frente ao comportamento sequencial atual, onde cada falha fica contida no seu arquivo. Por isso a coleta de cada resultado é envolvida em `try/except`: um worker morto vira um `FailedItem` como qualquer outra falha, o cache já salvo é preservado, e uma re-execução tenta de novo apenas o que não entrou no cache.

Timeout de subprocesso do `ffmpeg` (já em vigor desde a correção da revisão final, 120s) continua valendo dentro de cada worker, individualmente por arquivo — um ffmpeg travado num arquivo corrompido não trava os outros workers.

## Testes

- Testes existentes de `TrackService` passam `max_workers=1` explicitamente, preservando velocidade e determinismo (sem pagar o overhead de startup do `ProcessPoolExecutor` descrito acima a cada teste).
- Um teste novo verifica paralelismo de fato: usa o `HandcraftedExtractor` real (não `ExtratorFalso`, que não é importável num processo filho) sobre 2+ WAVs sintéticos pequenos, com `max_workers=2`, e confirma que o resultado final está correto (cache populado, todas as tracks presentes) — sem depender de instrumentar qual processo rodou o quê, só do resultado.
- Um teste cobre o modo de falha novo: com o `ProcessPoolExecutor` substituído por um dublê, um lote misto onde alguns futuros estouram em `.result()` (worker morto) e outros devolvem resultado válido — o scan deve completar marcando só os que estouraram como falha contida, preservando os demais no cache e na fila, em vez de propagar a exceção ou descartar o lote inteiro.
- Teste do limiar "pool só com >1 pendente e max_workers>1": um único arquivo novo, mesmo com `max_workers>1`, não aciona `ProcessPoolExecutor` (verificável indiretamente por não exigir que a classe de extração seja picklable nesse caminho — usar `ExtratorFalso` com 1 pendente e `max_workers=4` deve funcionar sem erro de import, provando que o pool não foi usado).
- Teste do save periódico usando o contador unificado: interrompe simuladamente após N extrações do lote combinado (rotuladas + inbox misturadas) e confirma que o save ocorreu no ponto certo, cruzando as duas fontes.

## Fora de escopo

- Configuração de `max_workers` via `config.toml` — não pedido, YAGNI até haver necessidade real.
- Paralelizar o treino do modelo (`Ridge`/`RidgeCV` já é rápido, não é o gargalo).
- Barra de progresso visual (spinner, `tqdm`) — uma linha por arquivo concluído é suficiente e não adiciona dependência nova.
- Qualquer um dos outros itens deixados pendentes na revisão final do projeto original (consolidação de helper ffmpeg, `--port` configurável, limpeza de cache de transcodificação, aviso de otimismo do LOO, etc.) — fora do escopo desta rodada, que é especificamente velocidade de scan.
