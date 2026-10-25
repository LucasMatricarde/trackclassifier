# AGENTS.md

Guia do repositorio para agentes de codigo (OpenCode, Kimi Code, Claude Code). O
detalhe de cada area mora numa skill em `.claude/skills/` -- invoque a skill antes
de mexer na area, em vez de deduzir do codigo.

## Fluxo de trabalho

### 1. Worktree por tarefa -- sempre, sem excecao

Toda tarefa nova roda numa git worktree dedicada:

- Uma tarefa = uma worktree = uma branch, com base na `main` atual. Nunca duas
  tarefas na mesma worktree; nunca duas worktrees na mesma tarefa.
- Se o Orca ja criou a worktree/branch da tarefa (`LucasMatricarde/<nome>`), use
  essa. Worktree criada a mao segue `<tipo>/<resumo>` (`feat/perfis`,
  `fix/scan-status`, `chore/qt-residues`).
- A worktree so e removida depois do merge do PR.

### 2. /orchestration para multi-tarefas

Pedido com mais de uma tarefa independente e decomposto via `/orchestration`.
Cada subtarefa segue a regra 1: worktree propria, branch propria, verificacao
propria.

### 3. Push e PR so com ordem explicita

Commits sao LOCAIS por padrao. Nunca dar push, rebase em origin nem abrir PR sem
instrucao direta -- mesmo que "seja o proximo passo obvio". Ao terminar, reporte
o estado (branch, commits, verificacoes) e pergunte se pode subir.

### 4. Um agente por branch (workers paralelos)

Cada worker opera so na sua worktree. Nao toque na branch de outro worker nem
rebaseie trabalho alheio. Conflito de historia = PARAR e reportar.

## Comandos

```bash
uv sync --extra dev            # instala deps (roda antes de qualquer coisa)
uv run pytest                  # suite completa (~35s, usa ffmpeg de verdade)
uv run pytest tests/test_service.py::test_treina_e_reporta_metricas   # um teste
uv run pytest -k paralelo      # filtra por substring do nome
uv run ruff check .            # lint (gate do CI); --fix para corrigir
```

CLI (precisa de `config.toml`, copiado de `config.example.toml`, gitignored):

```bash
uv run dj scan     # extrai features das tracks ainda nao analisadas
uv run dj train    # retreina e imprime metricas
uv run dj serve    # sobe API + WebSocket para o front React (8765)
uv run python design/build_tokens.py   # regenera web/src/styles/tokens.css
```

Front web (`web/`, spike da migracao; precisa de `dj serve` no ar):

```bash
cd web && npm ci
npm run dev                  # Vite em 5173, proxy de /api e /ws para 8765
npm run build                # gate do TS (tsc -b) + build; npx tsc --noEmit NAO segue as references
npx playwright test          # specs; TC_WEB_URL aponta para o build servido em 8765
```

Shell desktop (`shell/`, Electron; decisao em `docs/superpowers/specs/2026-10-20-shell-desktop-decisao.md`):

```bash
cd shell && npm ci
npm run start    # sobe o backend (dev via uv) e abre a janela
npm run smoke    # esconde a janela; falha sem Revisao/setup ou sem o preload
npm run pack     # .app em shell/out (precisa de ../dist/TrackClassifier)
npm run dist     # zip de release em shell/out
```

Para empacotar, nesta ordem: `cd web && npm run build` → `uv run --extra
build pyinstaller packaging/trackclassifier.spec` → `cd shell && npm run
pack`. Sem o primeiro passo o `.app` abre vazio; sem o segundo o
`extraResources` nao encontra o backend.

`ffmpeg`/`ffprobe` no PATH (`brew install ffmpeg`) -- sem eles a maioria dos testes
falha com `AudioDecodeError` e nao ha fallback puro-Python. Python `>=3.11,<3.14`;
CI (`.github/workflows/ci.yml`) roda ruff + pytest em push/PR para `main`.

## Grafo de conhecimento

`graphify-out/graph.json` e local e gitignored. Sem ele, nada aqui se aplica.

**Quando usar**: pergunta de **impacto** -- "o que quebra se eu mudar X", "quem
depende de Y", "o que este PR toca", "quem le esse formato".

**Teste antes de usar**: a resposta muda se eu trocar X? Se a pergunta e sobre o
que o codigo FAZ hoje -- onde mora, quem chama, que teste cobre, por que foi
assim -- o grafo nao entra: va de `rg`/`read` e da skill de area
correspondente. Em bug reproduzido ou teste falhando, **nao** consulte o grafo:
nem para checar frescor nem para localizar a classe; o arquivo e a linha ja
estao no relato.

**Fluxo (orcamento de 5 chamadas)**:

1. `get_node("<alvo>")` -- confirma o no e da o `file:linha` de origem.
2. `graphify affected "<id>" --depth 2` -- reverse traversal: e o passo que
   responde quem usa o alvo. Use o **id** que o `get_node` devolveu (ex.:
   `src_trackclassifier_service_trackservice_analyze_all`): um nome curto como
   `analyze_all` responde "No unique node match". Com `--relation calls` quando
   o alvo e uma funcao (o padrao entra tambem por `imports_from` e traz o
   modulo inteiro como ruido).
3. `graphify explain "<no>"` -- abre 2-3 suspeitos, com o tipo da aresta e a
   marca `[EXTRACTED]`/`[INFERRED]`. Pelo MCP, `get_neighbors` com
   `relation_filter` faz o mesmo com menos ruido.
4. Leia as linhas citadas: sem ler, tudo o que vier do grafo e hipotese.
5. Responda em tabela `mudanca -> consumidor -> file:linha -> risco`, do tamanho
   da pergunta.

**Confianca**: `EXTRACTED` veio do AST (import, chamada, contains) e e fato
estrutural; `INFERRED` e hipotese do extrator. "Vai quebrar" quase sempre e
`INFERRED` -- confirme no trecho antes de afirmar.

**O que o grafo nao pega (os riscos silenciosos)**: consumidor fora do grafo (o
front web, o `design/`, os docs -- no caso dos buckets, o parser do
`WaveformCanvas.tsx` le o `.npy` a mao e ignora o `descr` do header, entao um
`float32` quebra em silencio); formato sem versao (`PRESENTATION_VERSION` cobre
tags/capa/key, nao os `.npy` de peaks, entao o acervo velho continua aceito);
cache de render indexado por sha1/tamanho/modo, que nao invalida quando o
conteudo do arquivo muda; e o teste que fixa `PEAKS_BUCKETS`/dtype/shape, que e
o sinal mais barato de que o contrato mudou.

No Plan mode, use o grafo so para consulta; nao rode `extract`/`--update` -- o
deny de `edit` do plan nao bloqueia escrita via shell.

## Invariantes (valem sempre, o porque esta na skill)

- Mudou o calculo de features: **bumpe `HandcraftedExtractor.name`**
  (`features.py`). Mudou o que `presentation.py` produz: **bumpe
  `PRESENTATION_VERSION`** -- e apague `peaks/` a mao se o formato dos buckets
  mudou.
- Criou outro caminho que move um arquivo: chame `sha1_cache.rename(origem,
  destino)` junto.
- Erro numa borda **degrada e reporta** em `service.failures()`; nunca derruba o
  comando.
- Os handlers de `serve.py` sao os unicos a falar com `TrackService`; o front
  web so conhece a API. O scan e a unica chamada longa e roda fora do event
  loop (`asyncio.to_thread`), com a flag `_scan_running` impedindo dois
  `analyze_all` concorrentes.
- `viewmodel.py` nao importa toolkit de UI (ha teste que falha se importar
  PySide6/Qt).
- Nenhum hex em `web/src` fora de `design/design-tokens.json` (ha teste que
  varre o web).

## Documentacao viva

### 5. Tela mexeu, ficha acompanha

Toda alteracao visual ou estrutural numa tela aprovada exige, no mesmo PR:

- `docs/ui/ficha-tecnica-<tela>.md` atualizada (cores, geometrias, componentes,
  rulings) com o valor **medido no render** (regra 1 de `docs/ui/fidelidade.md`),
  nao o copiado do mockup;
- baseline visual regenerado (`web/tests/screenshot.spec.ts-snapshots/`) quando o
  layout mudar de proposito;
- diferenca conhecida entre mockup e render registrada na secao de diferencas da
  ficha -- nunca corrigida em silencio, nunca apagada.

Regras de fidelidade visual: `docs/ui/fidelidade.md` (leia antes de mexer em
UI). Indice das fichas e da infraestrutura de teste: `docs/ui/README.md`.

## Gate de qualidade (definition of done)

### 6. Suite verde e obrigatoria, nao elogio

A tarefa so termina com: `ruff` limpo + `uv run pytest` + Playwright verdes +
`npm run build` limpo. Falha flaky conhecida != falha nova: flaky vai para issue,
nao e ignorada.

### 7. Correcao de bug exige prova RED/GREEN

Teste novo que FALHA sem a correcao e PASSA com ela. Sem isso nao e correcao, e
edicao.

### 8. Teste novo e deterministico

Fixtures mockadas (`mockApi`, `fakeWebSocket`, `mockRevisaoCompleta`, todas em
`web/tests/review-fixtures.ts`). Nunca dependa de estado vivo: fila de revisao,
biblioteca real, timing de render. A fila e a biblioteca reais ficam vazias ou
mudam e o teste vira sorte -- foi assim que o `fidelity.spec` ficou vermelho
quando o acervo acabou. Teste que "pula" a assercao quando o elemento nao existe
e falso-positivo: prove o RED (remova o insumo e veja falhar) antes de aceitar.

### 9. Dados reais intocaveis em teste

Teste que decide ou move arquivo roda com backend descartavel:
`tests/e2e_backend.py` sobe a API real sobre pastas e `data_dir` temporarios
(porta 8799, `ExtratorFalso`) e o spec o inicia e apaga tudo no `afterAll`
(`decide-flow.spec.ts` e os fluxos de perfis/scan). Nunca a inbox, o
`config.toml` nem o `data_dir` do app: o E2E antigo deixava linhas `TESTFLOW` em
`analyses.parquet`, `sha1.json`, peaks e capas do acervo real.

Isolamento se prova com hash: antes e depois da suite completa, `shasum` de
`analyses.parquet`, `analyses.parquet.prev`, `presentation.parquet`, `sha1.json`,
`model.joblib`, `model_history.json` e de `~/.trackclassifier/config.toml`, mais
a contagem de `peaks/` e `covers/` do `data_dir` do app, devem ser identicos.
Diferenca = teste escrevendo no acervo; pare e investigue.

## Divida e refactor

### 10. Item deferido vira issue antes de fechar a tarefa

Divida registrada so no relatorio e divida perdida. GitHub issue, ou nao foi
deferido: foi esquecido.

### 11. Remocao de codigo: commit separado + consumidores verificados

Antes de apagar: `rg` pelos consumidores; logica compartilhada migra primeiro;
commit isolado (`chore: remove X`) para o revert ser trivial. Remover elemento de
UI NAO remove endpoint/backend sem checar quem usa.

### 12. Commits atomicos

Um concern por commit: feat, fix, refactor, chore e docs nao se misturam.

## Regras de fidelidade visual

O mockup e a unica fonte de verdade: nao interprete, nao "melhore", replique. A
evidencia de pronto e o render (valor computado ou pixels medidos), nunca o CSS
escrito. As sete regras visuais -- evidencia de render, higiene de build
(`rm -rf web/dist web/.vite`), tokens em vez de valores locais, escopo por
iteracao, sem elementos inventados, overlays e validacao numerica -- estao em
[`docs/ui/fidelidade.md`](docs/ui/fidelidade.md). Leia antes de mexer em UI.

## Convencoes

- **Portugues sem acentos** em tudo: nomes de variaveis locais, funcoes internas,
  comentarios, docstrings, mensagens de erro e nomes de teste. Todo `src/` esta
  livre de acentos (ha tres escapes isolados em comentarios de teste) -- escreva
  sem acento.
- API publica (dataclasses, metodos de classe, campos JSON, nomes de features) em
  ingles; o interior das funcoes, em portugues.
- Comentarios explicam **por que**, nao o que -- e sao longos quando a decisao nao
  e obvia (qual excecao, qual race, qual limite). Siga esse tom.
- Commits: conventional commits com escopo (`fix(trackclassifier):`, `feat(ci):`),
  um concern por commit (regra 12).
- ruff: `line-length = 100`, regras `E,F,I,UP,B`.
- Resposta do tamanho da pergunta, e a evidencia vem do repo. A semantica de
  biblioteca (stdlib) vem do seu conhecimento: leia o codigo-fonte da lib ou
  monte experimento end-to-end so quando a duvida for exatamente sobre a lib ou
  o usuario pedir prova -- senao o custo (3M tokens num run de 14 min) nao
  paga o que entrega.

## Documentacao de design

`docs/superpowers/specs/` e `docs/superpowers/plans/` guardam os designs e planos
das mudancas maiores. Consulte antes de reescrever essas areas.
