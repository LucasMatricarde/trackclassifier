# Aba Modelo web -- dashboard do mockup

Data: 2026-10-21
Sessao: Reescrever o front - 3 (Modelo)
Status: aprovado pelo usuario ("Quero o PNG como ja pedido desde o começo")

## Objetivo

Substituir a aba Modelo web atual (paridade com o painel PySide6) pelo
dashboard do mockup `design/mockup/TrackClassifier Model Dashboard.png`.
O pedido do usuario supera a exclusao de escopo do spec
2026-08-07 ("histórico de métricas ao longo do tempo"): o historico passa a
existir, com persistencia propria. O desktop (`ui/model_tab.py`) NAO muda --
o mockup e pedido do front web.

Regra de traducao (a mesma do port original): **estrutura e conteudo
seguem o PNG; cores seguem os tokens do produto**, nao os pixels do PNG.
Os tokens ja cobrem todo o mockup (violeta accent, success verde, lento
azul, warning ambar, animada coral) -- zero tokens novos, zero hex em
`web/src`.

## O que o mockup pede e de onde vem o dado

| Bloco do mockup | Dado | Fonte |
|---|---|---|
| 4 cards: Exemplos / Acuracia LOO / Erro ordinal / F1 ponderado, com sparkline + chip de delta | n_examples, accuracy, ordinal_mae, f1 ponderado; serie historica; delta vs treino anterior | `Metrics` + historico (novo) |
| Desempenho por classe (Precisao/Recall/F1 com barra) | precision/recall/f1 por classe | **derivavel da confusion** (linhas=real, cols=prevista) |
| Matriz de confusao com intensidade | confusion | existe |
| Distribuicao das classes + painel de recomendacao + "Ver recomendacoes" | class_counts | existe |
| Historico de treinamentos (tabela) | data, versao, exemplos, acuracia, erro, status | **novo estado persistido** |
| Configuracoes do modelo (steppers + RETREINAR AGORA + Opcoes avancadas) | retrain_every, min_examples, alpha/thresholds/extractor | existe (config + TechDetail) |
| Header: ultimo treinamento, Modelo ativo vX | ts do treino, versao | historico |
| Banner informativo | texto estatico | texto real do spec |

Mapeamentos que o mockup nao define e o spec real decide:

- **F1 ponderado**: weighted-averaged F1, pesos = suporte real (rowsums da
  confusion) -- mesmo estimador do sklearn (`f1_score(..., average="weighted")`,
  que pesa por suporte verdadeiro). Derivado da confusion; `model.py` nao muda,
  o calculo mora no viewmodel (mascara de apresentacao).
- **Precisao/recall por classe**: `C[j][j]/colsum(j)` e `C[j][j]/rowsum(j)`
  (linhas = real, como `_evaluate` grava). Classe sem previstos tem
  precisao 0 por definicao (e sem reais tem recall 0) -- front mostra
  `--` so quando a classe nao existe no conjunto (zero reais e zero
  previstos).
- **Versao do modelo** (`v2.1.0`): `v{era}.{indice}.0`. Major = numero da
  era do extractor (`handcrafted-v2` -> 2). Minor = contador de treinos
  dentro da era (primeiro treino da era = 0). Patch fixo em 0.
- **Chip de delta**: metrica atual vs treino imediatamente anterior NA MESMA
  era. Eras diferentes tem vetores de feature diferentes -- comparar seria
  enganoso, sem chip.
- **Status da tabela de historico**: `Ativo` = entrada mais recente (o
  modelo joblib carregado hoje); antigas = `--`. Nao ha conceito de
  "arquivado" no produto.
- **"Opcoes avancadas"**: disclosure com o TechDetail (alpha, cortes,
  extractor) -- o dado real que existe, em vez de modal ficticio.
- **"Ver recomendacoes"**: nao ha servico de recomendacoes no produto --
  sem botao fake; o painel de recomendacao aparece so com o texto.
- **"Saiba mais" do banner**: sem alvo real, sai.
- **Falhas de analise**: o mockup nao as mostra, mas a invariante do
  desktop (falhas visiveis mesmo sem treino) prevalece -- painel
  adicionado apos as linhas do mockup.

## Historico (novo estado persistido)

`data_dir/model_history.json`, append em `service.train()`:

```json
{"entries": [
  {"ts": "2026-10-21T13:24:00", "extractor": "handcrafted-v2",
   "n_examples": 461, "accuracy": 0.738, "ordinal_mae": 0.282,
   "weighted_f1": 0.71}
]}
```

- Cap de 50 entradas (o mais antigo sai; grafico de sparkline usa as
  ultimas 12).
- Escrita apos o `save` do joblib (mesmo ponto do fluxo deterministico
  `train()`); falha de disco degrada: treino nao falha e a falha nao entra
  em `failures()` -- log no stderr (nao e item de biblioteca; `failures()`
  e para tracks).
- **Backfill deterministico**: no boot, se `model.is_fitted` e o historico
  esta vazio (model.joblib antigo de antes deste spec), o service adiciona
  UMA entrada com `ts` = mtime do joblib e as metricas que o artefato
  carrega. O usuario com modelo antigo nao fica com dashboard "nunca
  treinado" ate o proximo treino.
- Retreino automatico (apos N decisoes) passa pelo mesmo `train()` e marca
  novo treino -- a tabela registra isso naturalmente.

## Settings (PUT)

`POST /api/model/settings` `{retrain_every, min_examples}`:

- Valores inteiros >= 1 (isValidacao de duplo clique no front e o endpoint
  revalida).
- Persiste com `save_config` (toml) e troca `service.config` in-memory com
  `dataclasses.replace` -- o padrao de `set_active_profile`.
- `GET` nao muda: `ModelState` ja carrega os dois valores hoje.

## ModelState (extensao do payload JSON)

Novos campos (opcionais no type TS para compat com o teste flagado? NAO --
fixture atualiza junto; campos novos sao obrigatorios no contrato pois o
servidor os emite sempre):

```ts
weighted_f1: number | null
per_class: [[precision, recall, f1]] | null  // uma linha por classe, na
           // ordem (-1, neutra, +1) — mesma forma da confusion
version: string | null            // "v2.1.0"; null sem treino
last_trained_at: string | null
history: { ts: string; version: string; n_examples: number
           accuracy: number; ordinal_mae: number; weighted_f1: number }[]  // <=12
deltas: { accuracy: number | null; ordinal_mae: number | null; weighted_f1: number | null }
min_examples: number              // novo no payload (config)
```

`served` pelo `_model_state_to_dict`; `states_changed` reintegra WS de
graca (o evento ja carrega `model`).

## Front

Layout (ordem do PNG):

1. Titulo + banner informativo.
2. 4 MetricCards com sparkline (SVG polyline + gradient) e chips de delta.
3. Desempenho por classe | Matriz de confusao | Distribuicao das classes
   (linhas tintadas, azul = diagonal; contagem escurece via color-mix).
4. Historico de treinamentos | Configuracoes do modelo.
5. Falhas de analise (invariante, fora do mockup).
6. Header ganha bloco do modelo: "Ultimo treinamento {ts}" + "Modelo ativo
   {version}" + RETREINAR (os dois gatilhos de treino compartilham
   `treinando`/guard do hook -- dois botoes, um POST).

Componentes novos: `MetricCard` (com sparkline), `PerClassPanel`,
`ClassDistribution` (com recomendacao), `HistoryPanel`,
`ModelSettingsPanel`; `ConfusionMatrix`/`TechDetail` reusados com
intensidade/disclosure. Estados vazios: sem treino -> cards com `--`,
sparkline a zero, painel por classe/nao-recomendacao ocultos, historico com
empty-state "Ainda sem treinamentos.", matriz/com por classe ocultos.

## Testes

- Backend: weighted F1 + per-class derivados (confusion conhecida), historico
  append em train(), backfill no boot, tick de versao por treino na era,
  PUT /settings persiste toml + troca config viva, cap de 50.
- Web: fixture `modelo.ts` com historia/deltas/per-class; `model.spec` /
  fidelity reescritos para os ids do novo layout; NOVO baseline de
  screenshot.

## Fora de escopo

- Desktop PySide6 e o cargo v2.1.0 semantico de artefato (nao existe
  versionamento de artefato no produto).
- Exportar/comparar treinos (a linha "..." do mockup) -- sem acao real.
