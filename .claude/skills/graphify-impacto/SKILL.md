---
name: graphify-impacto
description: Use quando a pergunta for de impacto no trackclassifier: "o que quebra se eu mudar X", "quem depende de Y", "o que este PR toca", "quem le esse formato". Lista consumidores com file:linha a partir do grafo graphify (get_node, graphify affected, explain). Nao use para onde mora um simbolo, quem chama X, por que uma decisao foi tomada, bug reproduzido ou teste falhando -- nesses casos use rg/read e a skill de area.
---

# Impacto de mudanca no trackclassifier

## Quando esta skill entra

Entra so na pergunta de **impacto**: o que quebra, quem depende, o que toca, quem le.

Nao entra em:

- "onde mora X" / "quem chama X" -- `rg` e um `get_node` pontual resolvem, sem varredura
- "por que foi assim" -- a skill de area tem o raciocinio (`trackclassifier-arquitetura`)
- bug reproduzido ou teste falhando -- leia o arquivo e rode o teste
- qualquer duvida que caiba numa skill de area (`-arquitetura`, `-audio-features`,
  `-apresentacao`, `-concorrencia`, `-empacotamento`, `-ui`): ela ja tem o mapa

## Fluxo (orcamento de 5 chamadas)

1. **Ache o no** -- `get_node("<alvo>")` devolve `file:linha`, comunidade e grau em cinco
   linhas. Se o nome nao casar, `query_graph` com `depth: 1` e `token_budget: 800`.
2. **Liste os consumidores** -- `graphify affected "<alvo>" --depth 2`: reverse traversal,
   e o passo que responde. Nao ha tool MCP equivalente, e CLI.
   Use `--relation calls` quando o alvo e uma funcao: o padrao tambem entra por
   `imports_from` e traz o modulo inteiro como ruido.
3. **Abra 2-3 suspeitos** -- `graphify explain "<no>"` mostra as conexoes com o tipo da
   aresta e a marca `[EXTRACTED]`/`[INFERRED]`. Pelo MCP, `get_neighbors("<no>",
   relation_filter="calls")` faz o mesmo com menos ruido.
4. **Leia as linhas citadas** -- sem ler, tudo o que vier do grafo e hipotese. Leia o trecho
   do consumidor antes de afirmar que ele quebra.
5. **Responda em tabela** -- `mudanca -> consumidor -> file:linha -> risco`.

## Confianca

`EXTRACTED` veio do AST (import, chamada, contains): e fato estrutural.
`INFERRED` e hipotese do extrator. "Vai quebrar" quase sempre e `INFERRED` -- confirme no
trecho antes de afirmar. Aresta `calls` entre arquivos e confiavel; `uses` e `references`,
menos.

## O que o grafo nao pega (os riscos silenciosos)

- **Consumidor fora do grafo**: o front web (`web/src/`), o `design/` e os docs nao entram
  como `imports` de Python. No caso dos buckets, o parser do `WaveformCanvas.tsx` le o
  `.npy` a mao e ignora o `descr` do header: com `float32` ele nao levanta erro, desenha
  errado. Procure o consumidor nao-Python.
- **Formato sem versao**: `PRESENTATION_VERSION` cobre tags/capa/key, nao os `.npy` de
  peaks. Arquivo velho continua aceito, entao a tela mistura formato antigo e novo.
- **Cache de render por chave frouxa**: caches de pixmap indexados por sha1/tamanho/modo nao
  invalidam quando o conteudo do arquivo muda.
- **Teste que fixa o valor**: quem fixa `PEAKS_BUCKETS`, dtype ou shape quebra junto, e e o
  sinal mais barato de que o contrato mudou.

## Como responder

Tabela `mudanca -> consumidor -> file:linha -> risco (erro visivel ou silencioso)`, mais
duas linhas de resumo. Do tamanho da pergunta: se o usuario pediu "o que quebra", nao
entregue o mapa inteiro do modulo. Cite `file:linha` sempre.

## Frescor

`graph.json` guarda `built_at_commit`; compare com `git rev-parse --short HEAD` quando a
pergunta tocar arquivo recente. Para atualizar: `graphify update .` (AST, sem LLM; docs
exigem `/graphify --update`). Nao rode update no Plan mode.

## Se as tools MCP nao estiverem disponiveis

O CLI tem a mesma semantica e o fluxo funciona igual pelo shell:

```bash
graphify affected "<alvo>" --depth 2
graphify explain "<no>"
graphify query "<pergunta>" --budget 1000
graphify path "A" "B"
```
