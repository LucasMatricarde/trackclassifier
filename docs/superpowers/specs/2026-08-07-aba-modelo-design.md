# Aba Modelo e vocabulário de botão — design

Data: 2026-08-07

## Objetivo

A aba Modelo tem o melhor dado do app e a pior apresentação: acurácia
leave-one-out, erro ordinal, matriz de confusão calibrada e falhas de análise,
tudo despejado em dois `QLabel` com alinhamento por `f"{valor:>8}"`.

Redesenhar sobre os tokens v0.2, expondo três coisas que já existem no serviço
e nunca chegaram à tela: o **balanço de classes do treino**, o **progresso até
o retreino automático** e o **motivo** pelo qual o retreino pode estar
indisponível.

Esta spec também fecha uma decisão de **sistema**, não só desta aba: o
vocabulário tipográfico dos rótulos de botão. Ver a seção final.

Referência visual: `design/mockups/modelo-instrumento.html` e
`design/mockups/botoes-tratamentos.html`.

Depende de: `docs/superpowers/specs/2026-08-07-linha-instrumento-e-tokens-v02-design.md`
(fases 1 e 2 — tokens e gerador).

## O que já existe e este trabalho não pode quebrar

- `ui/model_tab.py` — `ModelTab` com o sinal `train_requested()`. **O sinal não
  muda.**
- `ui/viewmodel.py` — `ModelState(accuracy, ordinal_mae, confusion, n_examples,
  failures)` e `model_state(service)`. Dataclasses puras, **não importam Qt**.
- `model.py` — `Metrics(accuracy, ordinal_mae, confusion, n_examples)`,
  `TrackModel.alpha_`, `.thresholds_`, `.low_confidence_mode`, e
  `NotEnoughClassesError` levantada por `fit()` quando falta exemplo de alguma
  das três classes.
- `labels.py` — `LABEL_ORDER` define a ordem ordinal (-1, neutra, +1). A matriz
  e o balanço seguem essa ordem, sempre.
- `service.py` — `failures() -> list[FailedItem]` (`filename`, `reason`),
  `_labeled`, `_decisions_since_train`, `config.retrain_every`,
  `config.min_examples`, `extractor.name`.

## Decisões de design

### A matriz é colorida por severidade ordinal, não por contagem

As três classes são **ordenadas**. Confundir neutra com animada é um deslize;
confundir lento com animada é um erro grave. `ordinal_mae` já pesa isso, mas a
matriz atual trata toda célula fora da diagonal igual.

| Distância `|i - j|` | Fundo | Texto |
|---|---|---|
| 0 (acerto) | `surface.2` + borda `border.default` | `text.primary` |
| 1 (erro leve) | `classification.neutro.bg` | `classification.neutro.text` |
| 2 (erro grave) | tinta de `state.danger` a ~12% | `state.danger` |

Célula com zero usa `text.disabled` — presente, mas sem chamar atenção.

Rótulos de linha e coluna coloridos pela classe (`classification.<x>.base`),
em mono. Cabeçalho `REAL × PREVISTO`, com a mesma convenção de hoje (linha =
real).

Legenda de três itens abaixo. Sem ela, a escala de cor é adivinhação.

### Balanço do treino — dado novo, e o mais acionável da tela

Três barras horizontais com a contagem de exemplos por classe, normalizadas
pela maior. Abaixo, uma linha de texto derivada: qual classe está sub-representada
e a recomendação de rotular mais dela.

Motivo: nenhuma métrica atual revela que a biblioteca tem 51 animadas contra 89
neutras — mas é isso que explica os erros. A aba deve terminar em "o que faço
agora", e a resposta quase sempre é a classe minoritária.

O texto é **derivado, não fixo**: só aparece quando a menor classe tem menos de
~70% da maior. Com o treino equilibrado, some.

### Progresso até o retreino automático

`config.retrain_every` e `service._decisions_since_train` existem e nenhum
aparece. Barra de 3px + `n / m ATÉ O RETREINO AUTOMÁTICO`, ao lado do botão.

Fecha o loop: classificar tem consequência agendada, não mágica.

### Retreinar desabilita com motivo visível

Hoje o botão está sempre ativo e o `NotEnoughClassesError` só aparece na status
bar depois do clique. Deve desabilitar quando falta exemplo de alguma classe, com
o motivo ao lado — mesmo padrão que `SettingsTab` já usa com `_MOTIVO_SCAN`
durante o scan.

Para isso o `ModelState` precisa carregar se é possível treinar e por quê não.
**Não** duplicar a regra na UI: ela vive em `model.fit()` e o viewmodel a
consulta.

### Falhas agrupadas por motivo

Hoje é `QListWidget` plano de `f"{nome}: {motivo}"`. Quarenta arquivos com
"ffmpeg nao encontrado" é **um** problema, não quarenta.

Agrupar por `reason`: motivo em destaque com a contagem num badge
`state.danger`, arquivos como detalhe em mono `text.muted` abaixo. Cabeçalho da
seção com o total: `N ARQUIVOS · M MOTIVOS`.

`reason` hoje é a string da exceção e varia por arquivo em alguns casos
(`"Falha ao decodificar X: <stderr do ffmpeg>"`). Agrupar pelo **tipo**, não
pela string completa — o agrupamento é por prefixo até os dois-pontos, ou
`FailedItem` ganha um campo de categoria. A segunda opção é mais limpa e é a
recomendada.

### Detalhe técnico recolhido

`alpha_`, `thresholds_` e `extractor.name` num rodapé recolhível, com um resumo
de uma linha visível quando fechado. Mesmo padrão do painel "por que este
palpite" da Revisão — reais e úteis depurando, inúteis usando.

## Decisão de sistema: rótulo de botão fala mono/caixa alta

O botão primário atual é o único elemento da tela em `font.family.sans`, caixa
mista, preenchimento sólido. Ele parece de outro aplicativo.

**Tratamento escolhido: contorno.** Borda e texto em `accent.base`, fundo
transparente; no hover, fundo `accent.bg` e texto `accent.hover`;
desabilitado, borda `border.subtle` e texto `text.disabled`.

Não é preferência estética. `accent.base` e `classification.animada.base` são a
mesma cor por decisão da v0.2 — um bloco laranja sólido compete com os chips de
classificação e com a barra de seleção, três elementos no mesmo tom por motivos
diferentes. Em contorno, o acento identifica a ação principal sem virar a maior
mancha de cor da tela.

**Mudança no token:** `font.case.label` na v0.2 cobre "label de coluna, nome de
seção, badge de estado". Passa a cobrir também **rótulo de botão**, sempre com
`font.family.mono` e `font.tracking.widest`.

Isso vale para o app inteiro: `Salvar` na Configuração e as ações do primeiro
uso viram `SALVAR` em mono. Aplicar no `app.qss` de uma vez, não aba por aba —
metade dos botões em mono e metade em sans é pior que qualquer uma das duas.

## Dados novos no `ModelState`

| Campo | Origem | Para |
|---|---|---|
| `class_counts: tuple[int, ...]` | `service._labeled` na ordem de `LABEL_ORDER` | Balanço do treino |
| `decisions_since_train: int` | `service._decisions_since_train` | Contador |
| `retrain_every: int` | `service.config.retrain_every` | Contador |
| `train_blocked_reason: str \| None` | classes ausentes em `_labeled` | Botão desabilitado |
| `alpha: float \| None` | `service.model.alpha_` | Detalhe técnico |
| `thresholds: tuple[float, float] \| None` | `service.model.thresholds_` | Detalhe técnico |
| `extractor_name: str` | `service.extractor.name` | Detalhe técnico |

`failures` continua plano — o agrupamento é apresentação e mora no
`ModelTab`, não no viewmodel.

## Estados

| Estado | Tratamento |
|---|---|
| Modelo não treinado | Métricas e matriz ausentes; balanço, contador e falhas continuam visíveis. É o estado normal no início, não um erro |
| Falta classe | Retreinar desabilitado, motivo ao lado, balanço mostrando a barra em zero |
| `low_confidence_mode` | Menos de `min_examples`: aviso discreto de que a acurácia LOO ainda é ruidosa |
| Sem falhas | Seção some inteira. Não mostrar lista vazia com "nenhuma falha" |
| Biblioteca vazia | `empty_state`, mesma linguagem das outras abas |

## Fora de escopo

- Importância das features (peso de cada uma das 44 no Ridge). Informativo,
  mas não muda nenhuma ação do usuário e empurra a aba para painel de ML.
- Histórico de métricas ao longo do tempo. Exigiria persistir treinos passados,
  que hoje não existe.
- Qualquer coisa do scan v2 / `handcrafted-v2` — a aba só exibe
  `extractor.name`, não muda com ele.

## Testes

- `viewmodel` continua sem importar Qt.
- `model_state()` com modelo não treinado devolve `class_counts` real (não
  zeros) e `train_blocked_reason` preenchido quando falta classe.
- Matriz: contagens zero em toda a diagonal e em toda a antidiagonal não
  quebram a coloração nem a legenda.
- Balanço: com as três classes iguais, a linha de recomendação não aparece.
- Agrupamento de falhas: dez arquivos com o mesmo tipo de erro viram um grupo
  com badge 10.
- `train_requested` não é emitido quando o botão está desabilitado.
- Rótulos de botão saem em mono/caixa alta em todas as abas, não só nesta.
