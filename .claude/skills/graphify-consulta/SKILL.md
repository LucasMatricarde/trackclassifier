---
name: graphify-consulta
description: Use antes de grep ou de abrir arquivos quando a duvida for estrutural no trackclassifier: onde mora um simbolo, quem chama X, como A chega em B, quais arquivos andam juntos, por que uma decisao foi tomada, o que um PR afeta. Consulta o grafo graphify via MCP (get_node, query_graph, shortest_path, get_pr_impact) e responde com file:line gastando menos tokens que varrer o repo. Nao use para bug com arquivo ja identificado ou erro de teste.
---

# Consultar o grafo do trackclassifier

## Regra de bolso

Se voce ia precisar de dois ou mais greps para se orientar, consulte o grafo
primeiro. Se ja sabe o arquivo -- bug reproduzido, teste falhando, linha citada
--, leia o arquivo: o grafo nao substitui o codigo, ele evita a varredura.

`graphify-out/` e local e gitignored. Sem `graph.json`, nada aqui se aplica --
construir o grafo e o pipeline `/graphify`, nao esta skill.

## Ordem de custo (do mais barato para o mais caro)

1. `get_node(label)`: cinco linhas -- `file:line`, comunidade, grau. Use como
   sonda para saber se o nome existe e onde mora. Quase de graca.
2. `get_neighbors(label, relation_filter, token_budget)`: arestas diretas. Em
   hub (grau acima de ~40, ex. `TrackService`) sem `relation_filter` a resposta
   trunca: filtre por `calls`, `imports_from`, `references`, `uses` ou
   `rationale_for`, ou va direto ao `get_node` do vizinho.
3. `query_graph(question, mode, depth, token_budget)`: BFS para "o que envolve
   X", DFS para "traco um caminho". `depth: 1` responde "onde fica"; `depth: 2`
   so quando a amplitude e a pergunta -- a partir de um arquivo ele puxa
   centenas de nos e trunca.
4. `shortest_path(source, target, undirected: true)`: como A chega em B. **Passe
   `undirected: true`**: o grafo e undirected, mas o default confere direcao e
   devolve "No directed path" em pares que existem.
5. `graph_stats`, `god_nodes`, `get_community(id)` e o resource
   `graphify://report`: orientacao -- tamanho do repo, abstracoes centrais, o
   que vive junto.

Comece com 600-1000 tokens de saida. Se vier truncado ("showing N of M"), suba
o budget ou estreite (filtro, depth 1, um no) -- nao presuma que o que faltou
nao importa.

## Pergunta -> tool

| pergunta | comeco |
|---|---|
| "onde mora X?" / "existe X?" | `get_node` |
| "quem chama X?" / "o que usa X?" | `get_neighbors` com `relation_filter` |
| "o que envolve o fluxo X?" | `query_graph` BFS depth 1, budget 800 |
| "como A chega em B?" | `shortest_path` com `undirected: true` |
| "quais sao as abstracoes centrais?" | `god_nodes` |
| "o que vive na camada X?" | `get_community` ou `query_graph` |
| "por que foi decidido X?" | `query_graph` -- `rationale_for` liga doc a codigo |
| "o que o PR #N afeta?" | `get_pr_impact`; varios PRs: `triage_prs` |

## Vocabulario: os labels nao sao o que voce digita

Labels sao identificadores em ingles (`TrackService`, `HandcraftedExtractor`) e
nomes de teste/UI em portugues sem acento (`test_cancelar_no_pool...`,
`_preenche_apresentacao`). `query_graph` casa substring, sem sinonimo, sem
stemming e sem traducao. Se a primeira pergunta nao trouxer no relevante:

1. tente o outro idioma (a mesma ideia em ingles costuma achar o simbolo);
2. tente o identificador exato (`peaks`, `append_analysis`), nao a frase;
3. `get_node` nos candidatos para confirmar qual e o no certo;
4. se ainda nao houver no, caia para `rg` -- e diga que caiu. Nunca invente uma
   aresta ou um no que o grafo nao devolveu.

## Confianca: ~80% EXTRACTED, ~20% INFERRED

`EXTRACTED` veio do AST (import, chamada, contains) e e fato estrutural.
`INFERRED` e hipotese do extrator (ex.: `main() --uses--> MainWindow`). Antes de
afirmar comportamento -- "o scan chama X" --, leia o trecho citado. `INFERRED`
serve para achar o lugar; nao serve como prova.

## Frescor

`graph.json` guarda `built_at_commit`. Compare com `git rev-parse --short HEAD`:
se divergir, o grafo pode nao ter o codigo de agora. Diga isso quando a pergunta
tocar arquivo recente. Para atualizar:

```bash
graphify update .     # AST, sem LLM; doc/imagem exigem /graphify --update
```

Nao rode update no Plan mode (o deny de `edit` nao bloqueia shell) nem por
reflexo no meio da consulta: a resposta de agora sai do grafo de agora.

## Depois de consultar

1. responda citando o `file:line` que o no deu;
2. leia so as linhas citadas antes de editar -- o grafo economiza a orientacao,
   nao a verificacao;
3. se o grafo nao bastou, diga o que faltou e use `rg`/`read`; esticar a consulta
   ate ela virar varredura manual e o pior dos dois mundos.

## Se as tools MCP nao estiverem disponiveis

CLI equivalente, mesma semantica:

```bash
graphify query "pergunta" [--dfs] [--budget 1000]
graphify path "A" "B"
graphify explain "Simbolo"
graphify update .
```

Nao rode o pipeline `/graphify` (detect, extracao semantica, cluster) para
responder uma pergunta: ele carrega ~40 KB de instrucoes e reconstroi o grafo.
