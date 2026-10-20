# Grafo de conhecimento como ferramenta de impacto — decisão

Data: 2026-10-20

## Objetivo

Definir, com medição, **quando** um agente deve consultar o grafo de
conhecimento do trackclassifier (`graphify-out/graph.json`) e **o que isso
custa**. A hipótese inicial era "consultar o grafo economiza tokens". A
medição disse outra coisa, e este documento registra o resultado para que a
decisão não seja rediscutida sem evidência nova.

## O que foi medido

Bateria de evals com agentes reais (subagentes), 3 perguntas × 2 condições ×
3 runs = 18 execuções, com o mesmo grafo e o mesmo `AGENTS.md`:

| pergunta | condição | acerto | tokens (média) | tempo |
|---|---|---|---|---|
| impacto: trocar o dtype dos buckets | com skill | 100% | 692k | 136s |
| impacto: trocar o dtype dos buckets | sem skill | 100% | 723k | 137s |
| não-impacto: como o cancelamento funciona | com skill | 93% | 587k | 99s |
| não-impacto: como o cancelamento funciona | sem skill | 100% | 334k | 95s |
| negativo: teste falhando, arquivo e linha conhecidos | com skill | 75% | 868k | 239s |
| negativo: teste falhando, arquivo e linha conhecidos | sem skill | 92% | 452k | 186s |
| **agregado** | com skill | **89%** | 716k | 158s |
| **agregado** | sem skill | **97%** | 503k | 140s |

A skill **custava 42% mais tokens e piorava o acerto** — o oposto do
objetivo. E a causa não era a receita, era o **gatilho**: com uma skill de
grafo anunciada, os agentes consultavam o grafo justamente no caso em que a
política manda não consultar (3 de 3 runs do caso negativo tocaram o grafo
com a skill, contra 1 de 3 sem ela). Ter a skill no ambiente encoraja o uso
do grafo; a política sozinha, roteia melhor.

## Decisão

**A receita de impacto vive no `AGENTS.md`; não existe skill de grafo no
repositório.**

- `AGENTS.md` (sempre carregado, custo zero de announce) traz: quando usar,
  quando não usar, o fluxo de 5 chamadas, a regra de confiança e os riscos
  que o grafo não pega.
- A skill `graphify-consulta`/`graphify-impacto` foi removida do
  `.opencode/opencode.jsonc` e do repositório. A `graphify` (pipeline de
  build, ~40 KB) continua disponível, para construir e atualizar o grafo.
- A skill hub `trackclassifier` aponta para a seção do `AGENTS.md`, para
  quem entra pelo repositório.

O motivo de a receita não ser uma skill: ela só é útil **depois** que a
decisão de consultar o grafo já foi tomada — e é justamente essa decisão
que a skill estava atrapalhando, ao se anunciar como candidata em perguntas
onde não cabe.

## O que o grafo entrega de valor (o que justify manter a política)

O grafo **não economiza token**: o gargalo é a exploração do modelo, não o
custo de Orientação. O que ele entrega é **cobertura e estrutura**:

- **Consumidor fora do Python.** O grafo só enxerga `imports`/`calls` de
  Python. O consumidor que mais dói no trackclassifier — o parser do
  `web/src/components/WaveformCanvas.tsx`, que lê o `.npy` à mão, ignora o
  `descr` do header e quebra **em silêncio** com `float32` — não aparece.
  A política do `AGENTS.md` lista esse risco explicitamente.
- **Estrutura da resposta.** A tabela `mudança → consumidor → file:linha →
  risco` sai mais barata de montar a partir de `graphify affected` do que de
  varredura manual.
- **Custo previsível.** `get_node` devolve cinco linhas; `affected` dá o
  alcance em uma chamada.

Sem a política, os runs de baseline ainda usaram o grafo (4, 7 e 13 chamadas
nos três runs de impacto) e acertaram 100%: a rota é viável, só precisa estar
escrita em algum lugar que não seja uma skill concorrente.

## Verificação depois do refactor (iteration-5)

Com a receita no `AGENTS.md` e sem skill de grafo no ambiente:

| pergunta | acerto | tokens | tempo | chamadas ao grafo |
|---|---|---|---|---|
| impacto | 100% | 5,13M (outlier de profundidade) | 987s | 8 |
| não-impacto | 80% | 795k | 146s | **0** (run-2) |
| não-impacto | 80% | 788k | 318s | 3 (run-3, nenhuma como base da resposta) |
| negativo | 100% | 557k | 231s | **0** |

O caso negativo voltou ao comportamento do baseline (zero chamadas), que era o
alvo. O caso não-impacto ainda registra sondas (0 e 3), e o primeiro run — com
a redação antiga do gate — fazia 6; por isso o gate virou um teste sim ou não
("a resposta muda se eu trocar X?"), que vem antes do fluxo.

Duas lições de usabilidade que a própria bateria deu:

- `graphify affected` exige o **id** do nó (o que `get_node` devolve): um nome
  curto como `analyze_all` responde "No unique node match". A receita
  documenta isso.
- O custo é dominado pelo **modo de profundidade** do modelo, não pela
  ferramenta: o run de impacto gastou 5,13M tokens reproduzindo o parser do
  front em node fora do repo. Medir tokens sem fixar a profundidade compara
  coisas diferentes.

## Achado no caminho: a tese do cancelamento está errada

Enquanto a bateria rodava, um agente levantou que o `shutdown(cancel_futures=True)`
é neutralizado pelo `__exit__` do `with`. **Confirmado por medição**, em 3.11.15,
3.12.13 e 3.13.14 (toda a faixa suportada, `>=3.11,<3.14`):

| | o pai volta em | tarefas do bloco que executaram |
|---|---|---|
| código atual (`wait=False`) | 1,0s | **12/12 — todas** |
| com `wait=True` | 3,1s | 10/12 (as pendentes foram descartadas) |

Mecanismo: `shutdown(wait=False, cancel_futures=True)` marca
`_cancel_pending_futures=True` e acorda o *manager thread*; em seguida o
`__exit__` chama `shutdown(wait=True)`, que **zera o flag** antes do manager
lê-lo. Os futures pendentes nunca viram `CANCELLED` e o manager continua
despachando. No 3.13, `shutdown` ainda zera `_executor_manager_thread`,
`_processes` e `_call_queue` mesmo com `wait=False`, então o `__exit__` já
não tem o que joinar.

Consequência: hoje o cancelamento **não descarta nada** — o bloco inteiro
(até `max_workers * 4` = 32 faixas) continua rodando em background, com o
resultado descartado (o pai largou a *result queue*). Três textos repetem a
tese errada: `src/trackclassifier/service.py:470-479`,
`.claude/skills/trackclassifier/concorrencia/SKILL.md:163-165` e
`src/trackclassifier/ui/worker.py:282-286`.

E o teste que "cobre" isso (`tests/test_service.py:834`) usa um executor falso
e só afirma a **chamada** `shutdown(cancel_futures=True)` — nunca exercita o
executor real, então não pode pegar nada disso.

A medição foi replicada de forma independente por três agentes diferentes
(iteration-4 e os runs 2 e 3 da iteration-5), com o mesmo resultado: 12/12
tarefas executam com `wait=False`, e o bloco continua em background.

**Decisão: B — os textos passam a descrever o comportamento atual.** O
cancelamento volta na hora (a latência é de *detecção*, de até uma extração,
porque a checagem vive no laço de `as_completed`), **não descarta o bloco** e
deixa as faixas já submetidas terminando em background, com o resultado
descartado. Corrigidos: `src/trackclassifier/service.py` (o comentário do
`shutdown`), `.claude/skills/trackclassifier/concorrencia/SKILL.md` e
`src/trackclassifier/ui/worker.py` (o fechamento da janela).

A opção A continua sendo a alternativa se um dia o cancelamento precisar
**parar** o trabalho: `wait=False` → `wait=True` faz o descarte valer de
vez e o pai passa a esperar a extração em voo (5-15s). O teste existente
(`tests/test_service.py:834`) continua válido nos dois casos, porque só
afirma a *chamada* — um teste que exercitasse o executor real seria o que
pegaria a diferença.

> Um detalhe de medição que vale registrar: o `cancel_futures=True` atual
> **não tem efeito nenhum** (zero futures `CANCELLED`, 12/12 tarefas
> executando). Ele ficou no código por causa do que o comentário dizia. Se
> alguém mexer na linha, remeça antes de confiar no argumento.

## Mudança fora do repositório

A skill global `graphify` (`~/.claude/skills/graphify/SKILL.md`, gerenciada
por `graphify install`) anunciava "use for any question about a codebase",
o que fazia dela candidata em qualquer pergunta de código. A description foi
estreitada para build/update. **Atenção:** `graphify install` sobrescreve o
arquivo — se o comportamento voltar, é essa linha.

## Como revalidar

O harness de evals (skill-creator) com subagentes, workspace em
`/private/var/folders/.../opencode/graphify-consulta-workspace`:
`iteration-1` (skill de consulta, 4 evals), `iteration-2` (escopo de impacto),
`iteration-3` (pós-fix da description global), `iteration-4` (n=3, 18 runs) e
`iteration-5` (pós-refactor, receita no `AGENTS.md`). Cada iteração tem
`benchmark.md`/`benchmark.json` e um viewer estático.
