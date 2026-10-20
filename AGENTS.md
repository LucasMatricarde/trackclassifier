# AGENTS.md

Guia do repositorio para agentes de codigo (OpenCode, Kimi Code, Claude Code). O
detalhe de cada area mora numa skill em `.claude/skills/` -- invoque a skill antes
de mexer na area, em vez de deduzir do codigo.

## Comandos

```bash
uv sync --extra dev            # instala deps (roda antes de qualquer coisa)
uv run pytest                  # suite completa (~70s, usa ffmpeg de verdade)
uv run pytest tests/test_service.py::test_treina_e_reporta_metricas   # um teste
uv run pytest -k paralelo      # filtra por substring do nome
uv run ruff check .            # lint (gate do CI); --fix para corrigir
```

CLI (precisa de `config.toml`, copiado de `config.example.toml`, gitignored):

```bash
uv run dj scan     # extrai features das tracks ainda nao analisadas
uv run dj train    # retreina e imprime metricas
uv run dj review   # abre a janela de revisao PySide6
uv run dj serve    # sobe API + WebSocket para o front React (8765)
uv run python design/build_tokens.py   # regenera ui/tokens.py, ui/app.qss e web/src/styles/tokens.css
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
- So a thread do `ServiceWorker` fala com `TrackService`. Widget nao chama
  servico direto.
- `ui/viewmodel.py` nao importa Qt (ha teste que falha se importar).
- Nenhum hex fora de `design/design-tokens.json` (ha teste que varre `ui/`).

## Convencoes

- **Portugues sem acentos** em tudo: nomes de variaveis locais, funcoes internas,
  comentarios, docstrings, mensagens de erro e nomes de teste. Todo `src/` esta
  livre de acentos (ha tres escapes isolados em comentarios de teste) -- escreva
  sem acento.
- API publica (dataclasses, metodos de classe, campos JSON, nomes de features) em
  ingles; o interior das funcoes, em portugues.
- Comentarios explicam **por que**, nao o que -- e sao longos quando a decisao nao
  e obvia (qual excecao, qual race, qual limite). Siga esse tom.
- Commits: conventional commits com escopo (`fix(trackclassifier):`, `feat(ci):`).
- ruff: `line-length = 100`, regras `E,F,I,UP,B`.
- Resposta do tamanho da pergunta, e a evidencia vem do repo. A semantica de
  biblioteca (stdlib) vem do seu conhecimento: leia o codigo-fonte da lib ou
  monte experimento end-to-end so quando a duvida for exatamente sobre a lib ou
  o usuario pedir prova -- senao o custo (3M tokens num run de 14 min) nao
  paga o que entrega.

## Documentacao de design

`docs/superpowers/specs/` e `docs/superpowers/plans/` guardam os designs e planos
das mudancas maiores. Consulte antes de reescrever essas areas.
